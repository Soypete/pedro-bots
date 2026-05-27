import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import get_llm
from core.middleware_config import build_middleware, log_audit_summary
from core.tools.reddit import search_reddit_posts, WINDOW_HOURS
from core.tools.supabase_tools import load_active_topics, store_classification, get_seen_post_ids
from core.tools.discord import send_discord_message, is_high_signal

logger = logging.getLogger(__name__)

CLASSIFY_SYSTEM_PROMPT = """You are a tech curator. Classify the Reddit post below.
Respond with JSON only — no prose, no markdown:
{"classification":"INTERESTING"|"NOT_INTERESTING","confidence":0.0-1.0,"reason":"one sentence","summary":"one sentence or null"}

Classify as INTERESTING if relevant to: AI agents, LLMs, local inference, Kubernetes, Go, Python, cloud infra, startups/VC, physics, open-source tooling."""

_CHUNK_COUNT = int(os.environ.get("REDDIT_CLASSIFY_WORKERS", "2"))  # keep low to avoid overwhelming large models
_CLASSIFY_MIN_SCORE = int(os.environ.get("REDDIT_CLASSIFY_MIN_SCORE", "50"))

_MAX_DIGEST_CHARS = 1500
_MAX_DIGEST_POSTS = 10


def _parse_classification(response_content: str) -> dict | None:
    """Parse classification JSON from LLM response. Returns dict or None if parse fails."""
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        pass

    m = re.search(r'\{.*\}', response_content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    return None


def _classify_post(post: dict, max_retries: int = 3) -> dict:
    """Call LLM to classify a single post. Returns classification dict.

    Uses robust JSON extraction with automatic retry and nudge injection
    on parse failures.
    """
    llm = get_llm()
    text = post.get("text", "")[:300]
    messages = [
        SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
        HumanMessage(content=f"Post from r/{post.get('topic_query', '?')}:\n{text}"),
    ]

    nudge_template = """Your previous response was not valid JSON. Please respond with ONLY JSON, no prose or markdown.
Required format: {"classification":"INTERESTING"|"NOT_INTERESTING","confidence":0.0-1.0,"reason":"one sentence","summary":"one sentence or null"}"""

    for attempt in range(1, max_retries + 1):
        response = llm.invoke(messages)

        result = _parse_classification(response.content)
        if result is not None:
            required_keys = {"classification", "confidence", "reason", "summary"}
            if required_keys.issubset(result.keys()):
                return result
            if "classification" in result:
                return {
                    "classification": result.get("classification", "NOT_INTERESTING"),
                    "confidence": result.get("confidence", 0.0),
                    "reason": result.get("reason", ""),
                    "summary": result.get("summary"),
                }

        if attempt < max_retries:
            logger.warning(
                "Classification parse failed (attempt %d/%d), injecting nudge for post %s",
                attempt,
                max_retries,
                post.get("post_id", "?")[:8],
            )
            messages.append(HumanMessage(content=nudge_template))

    logger.warning(
        "Classification failed after %d attempts for post %s",
        max_retries,
        post.get("post_id", "?")[:8],
    )
    return {
        "classification": "NOT_INTERESTING",
        "confidence": 0.0,
        "reason": "parse error",
        "summary": None,
    }


def _classify_chunk(chunk: list[dict], dry_run: bool = False) -> list[tuple[dict, dict]]:
    """Classify all posts in a time bucket. Returns (post, classification) pairs."""
    results = []
    for post in chunk:
        clf = _classify_post(post)
        if not dry_run:
            store_classification(post, clf)
        results.append((post, clf))
    return results


def _split_into_time_chunks(posts: list[dict], n: int) -> list[list[dict]]:
    """Bucket posts into n equal time slices across the 24h window (newest = chunk 0)."""
    now = time.time()
    chunk_seconds = (WINDOW_HOURS * 3600) / n
    buckets: list[list[dict]] = [[] for _ in range(n)]
    for post in posts:
        age = now - float(post["created_at"])
        idx = min(int(age / chunk_seconds), n - 1)
        buckets[idx].append(post)
    return buckets


def _format_digest(interesting: list[tuple], total_fetched: int) -> str:
    top = sorted(interesting, key=lambda x: x[1].get("confidence", 0), reverse=True)[:_MAX_DIGEST_POSTS]
    lines = ["check out this:\n"]
    for i, (post, clf) in enumerate(top, 1):
        lines.append(f"{i}. [r/{post.get('topic_query')}] u/{post.get('author_handle')}")
        if clf.get("summary"):
            lines.append(f"   {clf['summary'][:120]}")
        lines.append(f"   {post.get('post_url')}\n")
    lines.append(f"-- {len(interesting)} of {total_fetched} posts relevant --")
    return "\n".join(lines)[:_MAX_DIGEST_CHARS]


def run_monitor(dry_run: bool = False) -> None:
    logger.info("RedditWatch monitor run starting at %s (dry_run=%s)", datetime.now(timezone.utc).isoformat(), dry_run)
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

    # 2b. Pre-classify score filter — reduces LLM calls for large post sets
    before = len(all_posts)
    all_posts = [p for p in all_posts if p["score"] >= _CLASSIFY_MIN_SCORE]
    logger.info("Score filter (>=%d): %d → %d posts to classify", _CLASSIFY_MIN_SCORE, before, len(all_posts))

    if not all_posts:
        logger.info("No posts passed score filter")
        log_audit_summary(auditor)
        return

    # 3. Split into time buckets and classify in parallel
    chunks = [c for c in _split_into_time_chunks(all_posts, _CHUNK_COUNT) if c]
    logger.info("Classifying %d posts across %d time chunks in parallel", len(all_posts), len(chunks))

    interesting: list[tuple] = []
    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {executor.submit(_classify_chunk, chunk, dry_run): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            chunk_idx = futures[future]
            try:
                for post, clf in future.result():
                    if clf.get("classification") == "INTERESTING":
                        interesting.append((post, clf))
                        logger.info(
                            "INTERESTING [%.2f] chunk=%d r/%s: %s",
                            clf.get("confidence", 0), chunk_idx,
                            post.get("topic_query"), clf.get("reason", "")[:80],
                        )
            except Exception as e:
                logger.error("Chunk %d classification failed: %s", chunk_idx, e)

    logger.info("Classification complete: %d/%d interesting", len(interesting), len(all_posts))

    # 4. Send Discord digest if anything interesting
    if interesting:
        msg = _format_digest(interesting, len(all_posts))
        top_confidence = max((clf.get("confidence", 0) for _, clf in interesting), default=0)
        if dry_run:
            print("\n--- DRY RUN: would send this Discord message ---")
            print(msg)
            print("--- END DRY RUN ---")
        else:
            sent = send_discord_message(msg, high_signal=is_high_signal(top_confidence))
            if sent:
                logger.info("Discord digest sent")
            else:
                logger.warning("Discord send failed")
    else:
        logger.info("No interesting posts — no Discord message sent")

    log_audit_summary(auditor)
    logger.info("RedditWatch monitor run complete")
