# pedro-bots Implementation Plan

## GitHub Issues (Priority Order)

| # | Title | Status |
|---|-------|--------|
| 1 | MonitorAgent: Add ResponseValidator with retries and nudges | **DONE** |
| 2 | MonitorAgent: Add ErrorTracker for classification failures | TODO |
| 3 | middleware_config: Add tool input validation | TODO |
| 4 | Add context window management for agent conversations | TODO |
| 5 | SuggestionAgent: Add StepEnforcer for sequential tool execution | TODO |

## Issue Details

### #1 MonitorAgent ResponseValidator
- Import ResponseValidator, retry_nudge from middleware_py
- Wrap _classify_post() with max 3 retries
- Inject nudges on parse failures

### #2 MonitorAgent ErrorTracker
- Track classification failures per session
- Log error rates, alert on threshold

### #3 Tool Input Validation
- Validate tool args in middleware_config.py
- Return validation errors via ToolResult

### #4 Context Window Management
- Add ContextWindowManager for long conversations
- Implement compaction strategy

### #5 StepEnforcer for SuggestionAgent
- Enforce sequential tool prerequisites
- Track completed steps per session

## Next Steps After #5

1. **Full Inference Loop**: Migrate to pedro-agentware's `run_inference()` for unified guardrails
2. **Custom AgentGraph**: Replace `create_react_agent` with custom LangGraph for full control
3. **Policy YAML Updates**: Expand policy rules as new tools are added
4. **Observability Dashboard**: Build metrics from audit records and error tracking