# ADR 002: Multi-Agent Architecture with Shared Core

## Status
Accepted

## Date
2026-03-25

## Context
The original TweetWatch had a monolithic structure with agents and tools in the same directory. For maintainability and extensibility, we need a cleaner separation that allows:
- Multiple agents to share common tools and configuration
- Easier testing of individual components
- Clear boundaries between agent logic and shared infrastructure

## Decision
Organize codebase into `src/core/` with subdirectories for `agents/`, `tools/`, and `config.py`. The CLI entry point (`main.py`) remains at `src/` level and imports from `core`.

## Consequences
- **Positive**: Clear separation of concerns
- **Positive**: Reusable tools across agents
- **Positive**: Easier to add new agents in the future
- **Negative**: Requires import path updates when moving code

## Structure
```
src/
  main.py           # CLI entry point
  core/
    __init__.py
    config.py       # Configuration and LLM factory
    agents/
      __init__.py
      monitor.py    # Tweet fetch + classify agent
      suggestion.py # Weekly suggestions agent
    tools/
      __init__.py
      reddit.py     # Reddit API client
      discord.py    # Discord webhook integration
      supabase_tools.py # Database operations
```