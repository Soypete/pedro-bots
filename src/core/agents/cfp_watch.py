import json
import logging
import httpx
import os
from datetime import datetime, timezone

from core.tools.cfp import duckduckgo_search, fetch_cfp_page
from core.tools.discord import send_discord_message
from core.tools.supabase_tools import store_cfp, get_recent_cfps

logger = logging.getLogger(__name__)


def run_cfp_watch(dry_run: bool = False) -> None:
    """Run the CFP watch agent with direct OpenAI API calls."""
    logger.info(
        "CFP Watch run starting at %s (dry_run=%s)",
        datetime.now(timezone.utc).isoformat(),
        dry_run,
    )

    base_url = os.environ.get("LLAMA_CPP_BASE_URL", "http://100.121.229.114:8000/v1")
    model_name = os.environ.get("LLAMA_CPP_MODEL", "qwen3.6-27b-mtp")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "duckduckgo_search",
                "description": "Search the web using DuckDuckGo for Call For Papers, conference announcements, and speaking opportunities.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {
                            "type": "integer",
                            "description": "Max results (1-10)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_cfp_page",
                "description": "Fetch a webpage to extract CFP details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "store_cfp",
                "description": "Store a CFP to the database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_name": {"type": "string"},
                        "event_url": {"type": "string"},
                        "cfp_url": {"type": "string"},
                        "cfp_deadline": {"type": "string"},
                        "event_date": {"type": "string"},
                        "topics": {"type": "string"},
                    },
                    "required": ["event_name"],
                },
            },
        },
    ]

    search_topics = [
        "AgentCon North America 2026 Call For Papers",
        "Linux Foundation AI conference Call For Papers 2026",
        "AI agent conference CFP 2026",
    ]

    system_prompt = f"""You are a CFP researcher finding speaking opportunities for a tech speaker.

## Your Task
1. Search for Call For Papers using duckduckgo_search for these topics: {", ".join(search_topics)}
2. For each promising result, use fetch_cfp_page to get details from the event page
3. IMMEDIATELY call store_cfp for each unique CFP found (this is required!)
4. Do NOT summarize until you have stored at least 2 CFPs

## store_cfp required fields
- event_name: Name of the conference/event
- event_url: URL to the event page
- cfp_url: URL to the Call For Papers submission page
- cfp_deadline: Deadline date in YYYY-MM-DD format (estimate if needed)
- event_date: Dates of the event (e.g., "2026-10-22 to 2026-10-23")
- topics: Comma-separated topics/themes of the conference

## Important
- You MUST call store_cfp for every CFP you find
- Do not ask follow-up questions - just search and store
- If search returns no good results, try different search queries"""

    user_message = f"""Search for CFPs for these topics: {", ".join(search_topics)}

For each topic, search, extract event/CFP URLs, fetch details, and store them using store_cfp."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    client = httpx.Client(base_url=base_url, timeout=900.0)
    max_iterations = 5

    for i in range(max_iterations):
        logger.info(f"CFP iteration {i + 1}/{max_iterations}")

        payload = {
            "model": model_name,
            "messages": messages,
            "tools": tools,
            "temperature": 0.2,
            "max_tokens": 512,
        }

        response = client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        msg = choice["message"]

        messages.append(msg)

        if "tool_calls" not in msg:
            logger.info("No more tool calls, breaking")
            break

        for tc in msg["tool_calls"]:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])
            logger.info(f"Calling tool: {fn_name} with {fn_args}")

            try:
                if fn_name == "duckduckgo_search":
                    result = duckduckgo_search.invoke(fn_args)
                elif fn_name == "fetch_cfp_page":
                    result = fetch_cfp_page.invoke(fn_args)
                elif fn_name == "store_cfp":
                    # Everything reaches us via the DuckDuckGo search tool, so record
                    # that rather than letting the model omit it and default to "unknown".
                    fn_args.setdefault("source", "duckduckgo")
                    result = store_cfp.invoke(fn_args)
                else:
                    result = f"Unknown tool: {fn_name}"
            except Exception as e:
                result = f"Error: {e}"
                logger.error(f"Tool error: {e}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)[:2000],
                }
            )

    final_response = messages[-1].get("content", "")
    logger.info(f"CFP agent completed with response: {final_response[:500]}")

    cfps = _parse_cfp_from_text(final_response)
    try:
        recent_cfps = get_recent_cfps(days=7)
    except Exception as e:
        logger.warning(f"Could not fetch recent CFPs: {e}")
        recent_cfps = []
    new_count = len(recent_cfps)

    display_cfps = cfps if cfps else recent_cfps

    if display_cfps or new_count > 0:
        digest = _format_cfp_digest(display_cfps, new_count)

        if dry_run:
            logger.info(f"DRY RUN: would send Discord message: {digest}")
            print("\n--- DRY RUN: would send this Discord message ---")
            print(digest)
            print("--- END DRY RUN ---")
        else:
            sent = send_discord_message(digest)
            if sent:
                logger.info("CFP digest sent to Discord")
            else:
                logger.warning("CFP Discord send failed")
    else:
        logger.info("No new CFPs found")

    logger.info("CFP Watch run complete")
    client.close()


def _parse_cfp_from_text(text: str) -> list[dict]:
    """Extract CFP info from LLM response text."""
    cfps = []

    lines = text.split("\n")
    current_cfp = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("Event Name:") or line.startswith("- Event Name:"):
            if current_cfp and "event_name" in current_cfp:
                cfps.append(current_cfp)
            current_cfp = {"event_name": line.split(":", 1)[1].strip()}
        elif line.startswith("URL:") and "event_name" in current_cfp:
            current_cfp["event_url"] = line.split(":", 1)[1].strip()
        elif line.startswith("CFP Deadline:") and "event_name" in current_cfp:
            deadline = line.split(":", 1)[1].strip()
            if deadline and deadline != "TBD":
                current_cfp["cfp_deadline"] = deadline
        elif line.startswith("Event Date:") and "event_name" in current_cfp:
            event_date = line.split(":", 1)[1].strip()
            if event_date and event_date != "TBD":
                current_cfp["event_date"] = event_date
        elif line.startswith("Topics:") and "event_name" in current_cfp:
            topics = line.split(":", 1)[1].strip()
            if topics:
                current_cfp["topics"] = ",".join(topics.split(",")[:5])

    if current_cfp and "event_name" in current_cfp:
        cfps.append(current_cfp)

    return cfps


def _format_cfp_digest(cfps: list[dict], total_found: int) -> str:
    """Format CFPs for Discord digest."""
    if not cfps:
        return "No new CFPs found this week."

    lines = ["CFP Watch: New Speaking Opportunities\n"]

    for i, cfp in enumerate(cfps[:10], 1):
        lines.append(f"{i}. **{cfp.get('event_name', 'Unknown Event')}**")
        if cfp.get("event_url"):
            lines.append(f"   {cfp['event_url']}")
        if cfp.get("cfp_deadline"):
            lines.append(f"   CFP Deadline: {cfp['cfp_deadline']}")
        if cfp.get("event_date"):
            lines.append(f"   Event Date: {cfp['event_date']}")
        if cfp.get("topics"):
            lines.append(f"   Topics: {', '.join(cfp['topics'])}")
        lines.append("")

    lines.append(f"-- {len(cfps)} CFPs stored, {total_found} total found --")
    return "\n".join(lines)
