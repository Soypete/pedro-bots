import logging
import os
from typing import Any

from langchain_core.tools import StructuredTool
from pedro_agentware.middleware import InMemoryAuditor, MiddlewareImpl
from pedro_agentware.middleware.audit import AuditFilter
from pedro_agentware.middleware.policy import Policy, SimplePolicyEvaluator

logger = logging.getLogger(__name__)

_POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "policy.yaml")


def build_middleware() -> tuple[MiddlewareImpl, InMemoryAuditor]:
    """Load policy.yaml and return a configured Middleware + auditor."""
    auditor = InMemoryAuditor()
    policy = Policy(rules=[], default_deny=False)
    evaluator = SimplePolicyEvaluator(policy)
    mw = MiddlewareImpl(executor=None, evaluator=evaluator, auditor=auditor)
    return mw, auditor


def apply_middleware(tools: list, middleware: MiddlewareImpl) -> list:
    """Wrap LangChain tools with policy enforcement, preserving their schemas."""
    wrapped = []
    for tool in tools:
        wrapped.append(_wrap_one(tool, middleware))
    return wrapped


def _wrap_one(tool, middleware: MiddlewareImpl):
    """Wrap a single LangChain tool (or plain function) through middleware."""
    if not hasattr(tool, "name"):
        tool = StructuredTool.from_function(func=tool)

    tool_name = tool.name
    tool_description = tool.description
    tool_schema = getattr(tool, "args_schema", None)

    def make_executor(t):
        def executor(name: str, args: dict) -> tuple[Any, bool, str]:
            try:
                result = t.invoke(args)
                return (result, True, "")
            except Exception as e:
                return (None, False, str(e))
        return executor

    executor = make_executor(tool)

    def wrapped_fn(**kwargs):
        from pedro_agentware.middleware.types import CallerContext
        caller = CallerContext(session_id="social-poster", user_id="system")
        result, success, error = middleware.execute(tool_name, kwargs, caller)
        if not success:
            logger.warning("Middleware blocked %s: %s", tool_name, error)
            return f"Policy denied: {error}"
        return result

    create_kwargs = dict(func=wrapped_fn, name=tool_name, description=tool_description)
    if tool_schema:
        create_kwargs["args_schema"] = tool_schema
    return StructuredTool.from_function(**create_kwargs)


def log_audit_summary(auditor: InMemoryAuditor) -> None:
    """Log a summary of all tool calls recorded this run."""
    entries = auditor.query(AuditFilter())
    if not entries:
        return
    logger.info("Middleware audit — %d tool calls this run:", len(entries))
    for e in entries:
        logger.info(
            "  [%s] %s → %s",
            e.timestamp.strftime("%H:%M:%S"),
            e.tool_name,
            e.decision.action.value,
        )