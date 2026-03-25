import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import get_llm
from core.middleware_config import build_middleware, log_audit_summary
from core.tools.reddit import search_reddit_posts
from core.tools.supabase_tools import load_active_topics, store_classification, get_seen_post_ids
from core.tools.discord import send_discord_message, is_high_signal

logger = logging.getLogger(__name__)

CLASSIFY_SYSTEM_PROMPT = """You are a tech curator. Classify the Reddit post below.
Respond with JSON only — no prose, no markdown:
{"classification":"INTERESTING"|"NOT_INTERESTING","confidence":0.0-1.0,"reason":"one sentence","summary":"one sentence or null"}

Classify as INTERESTING if relevant to: AI agents, LLMs, local inference, Kubernetes, Go, Python, cloud infra, startups/VC, physics, open-source tooling."""


def _classify_post(post: dict) -> dict:
    """Call LLM to classify a single post. Returns classification dict."""
    llm = get_llm()
    text = post.get("text", "")[:300]
    response = llm.invoke([
        SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
        HumanMessage(content=f"Post from r/{post.get('topic_query', '?')}:\n{text}"),
    ])
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        # Try extracting JSON block if LLM added prose
        import re
        m = re.search(r'\{.*\}', response.content, re.DOTALL)
        if m:
            return json.loads(m.group())
        logger.warning("Could not parse classification JSON: %s", response.content[:100])
        return {"classification": "NOT_INTERESTING", "confidence": 0.0, "reason": "parse error", "summary": None}


_MAX_DIGEST_CHARS = 1500
_MAX_DIGEST_POSTS = 10


def _format_digest(interesting: list[tuple], total_fetched: int) -> str:
    now = datetime.now(timezone.utc).strftime("%H:%M")
    # Sort by confidence descending, cap at top N
    top = sorted(interesting, key=lambda x: x[1].get("confidence", 0), reverse=True)[:_MAX_DIGEST_POSTS]
    lines = [f"check out this:\n"]
    for i, (post, clf) in enumerate(top, 1):
        lines.append(f"{i}. [r/{post.get('topic_query')}] u/{post.get('author_handle')}")
        if clf.get("summary"):
            lines.append(f"   {clf['summary'][:120]}")
        lines.append(f"   {post.get('post_url')}\n")
    lines.append(f"-- {len(interesting)} of {total_fetched} posts relevant --")
    msg = "\n".join(lines)
    return msg[:_MAX_DIGEST_CHARS]


def run_monitor() -> None:
    logger.info("RedditWatch monitor run starting at %s", datetime.now(timezone.utc).isoformat())
    _, auditor = build_middleware()

    # 1. Load topics and seen IDs
    topics = load_active_topics()
    if not topics:
        logger.warning("No active topics found — aborting")
        return
    seen_ids = get_seen_post_ids()
    logger.info("Loaded %d topics, %d seen post IDs", len(topics), len(seen_ids))

    # 2. Fetch posts from each subreddit
    all_posts = []
    for topic in topics:
        posts = search_reddit_posts(topic)
        new_posts = [p for p in posts if p["post_id"] not in seen_ids]
        logger.info("r/%s: %d fetched, %d new", topic, len(posts), len(new_posts))
        all_posts.extend(new_posts)

    if not all_posts:
        logger.info("No new posts to classify")
        log_audit_summary(auditor)
        return

    logger.info("Classifying %d posts", len(all_posts))

    # 3. Classify each post and store
    interesting = []
    for post in all_posts:
        clf = _classify_post(post)
        store_classification(post, clf)
        if clf.get("classification") == "INTERESTING":
            interesting.append((post, clf))
            logger.info("INTERESTING [%.2f] r/%s: %s", clf.get("confidence", 0), post.get("topic_query"), clf.get("reason", "")[:80])

    logger.info("Classification complete: %d/%d interesting", len(interesting), len(all_posts))

    # 4. Send Discord digest if anything interesting
    if interesting:
        msg = _format_digest(interesting, len(all_posts))
        top_confidence = max((clf.get("confidence", 0) for _, clf in interesting), default=0)
        high_signal = is_high_signal(top_confidence)
        sent = send_discord_message(msg, high_signal=high_signal)
        if sent:
            logger.info("Discord digest sent (high_signal=%s)", high_signal)
        else:
            logger.warning("Discord send failed")
    else:
        logger.info("No interesting posts — no Discord message sent")

    log_audit_summary(auditor)
    logger.info("RedditWatch monitor run complete")
