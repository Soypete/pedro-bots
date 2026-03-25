import logging
from datetime import datetime, timezone

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from core.config import get_llm
from core.middleware_config import build_middleware, apply_middleware, log_audit_summary
from core.tools.reddit import get_trending_subreddits
from core.tools.supabase_tools import get_interesting_posts
from core.tools.discord import send_discord_message

logger = logging.getLogger(__name__)

SUGGESTION_SYSTEM_PROMPT = """
You are RedditWatch, a Reddit curation assistant. Your job is to generate weekly
suggestions for new subreddits and authors to follow.

Steps:
1. Call get_interesting_posts with days=7 to load this week's interesting Reddit posts.
2. Analyze the corpus: which subreddits, authors, and topics appear repeatedly?
   Which are new compared to the seed list? Which drove the most interesting content?
3. Call get_trending_subreddits to see what is currently trending (may return an empty
   list on error — handle gracefully).
4. Generate a ranked suggestion list: up to 5 subreddits to add and up to 5 authors
   to follow, with a one-line reason for each.
5. Call send_discord_message with a formatted suggestion message:

   RedditWatch Weekly Suggestions

   Subreddits to consider adding:
     - r/ExampleSub — reason why it's relevant this week

   Authors to consider following:
     - u/handle — reason based on their content this week

If there is insufficient data (fewer than 10 interesting posts this week), note
that in the message and suggest checking back next week.
"""


def build_suggestion_agent():
    tools = [
        get_interesting_posts,
        get_trending_subreddits,
        send_discord_message,
    ]
    mw, auditor = build_middleware()
    return create_react_agent(
        model=get_llm(),
        tools=apply_middleware(tools, mw),
        prompt=SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
    ), auditor


def run_suggestion() -> None:
    logger.info("RedditWatch suggestion run starting at %s", datetime.now(timezone.utc).isoformat())
    agent, auditor = build_suggestion_agent()
    agent.invoke(
        {"messages": [{"role": "user", "content": "Generate weekly subreddit and author suggestions."}]}
    )
    log_audit_summary(auditor)
    logger.info("RedditWatch suggestion run complete")
