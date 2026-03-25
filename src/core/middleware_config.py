import logging
import os

from langchain_core.tools import StructuredTool
from middleware_py import Middleware, InMemoryAuditor, ToolResult as MWResult
from middleware_py.middleware import with_auditor
from middleware_py.policy_loader import load_policy_from_file

logger = logging.getLogger(__name__)

_POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "policy.yaml")


def build_middleware() -> tuple[Middleware, InMemoryAuditor]:
    """Load policy.yaml and return a configured Middleware + auditor."""
    policy = load_policy_from_file(_POLICY_PATH)
    auditor = InMemoryAuditor()
    mw = Middleware(policy=policy, options=[with_auditor(auditor)])
    return mw, auditor


def apply_middleware(tools: list, middleware: Middleware) -> list:
    """Wrap LangChain tools with policy enforcement, preserving their schemas."""
    wrapped = []
    for tool in tools:
        wrapped.append(_wrap_one(tool, middleware))
    return wrapped


def _wrap_one(tool, middleware: Middleware):
    """Wrap a single LangChain tool (or plain function) through middleware."""
    # Convert plain functions to StructuredTool first to get name/schema
    if not hasattr(tool, "name"):
        tool = StructuredTool.from_function(func=tool)

    tool_name = tool.name
    tool_description = tool.description
    tool_schema = getattr(tool, "args_schema", None)

    def make_executor(t):
        def executor(name: str, args: dict) -> MWResult:
            try:
                result = t.invoke(args)
                return MWResult(tool_name=name, success=True, result=result)
            except Exception as e:
                return MWResult(tool_name=name, success=False, error=str(e))
        return executor

    executor = make_executor(tool)

    def wrapped_fn(**kwargs):
        call_mw = Middleware(executor=executor, policy=middleware._policy)
        call_mw._auditor = middleware._auditor
        call_mw._history = middleware._history
        result = call_mw.call(tool_name, kwargs)
        if not result.success:
            logger.warning("Middleware blocked %s: %s", tool_name, result.error)
            return f"Policy denied: {result.error}"
        return result.result

    create_kwargs = dict(func=wrapped_fn, name=tool_name, description=tool_description)
    if tool_schema:
        create_kwargs["args_schema"] = tool_schema
    return StructuredTool.from_function(**create_kwargs)


def log_audit_summary(auditor: InMemoryAuditor) -> None:
    """Log a summary of all tool calls recorded this run."""
    entries = auditor.get_all()
    if not entries:
        return
    logger.info("Middleware audit — %d tool calls this run:", len(entries))
    for e in entries:
        logger.info(
            "  [%s] %s → %s",
            e.timestamp.strftime("%H:%M:%S"),
            e.tool_call.tool_name,
            e.decision.action.value,
        )
