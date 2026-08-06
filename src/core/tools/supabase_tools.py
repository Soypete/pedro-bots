import json
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras
from langchain.tools import tool

from core.config import get_secret

logger = logging.getLogger(__name__)


def _get_conn():
    postgres_url = get_secret("postgres_url")
    if not postgres_url:
        raise ValueError("POSTGRES_URL not found in Vault secrets or environment")
    conn = psycopg2.connect(postgres_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path = public")
    return conn


def load_active_topics() -> list[str]:
    """Load monitored subreddits from rw_topics, ordered by priority."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT query FROM rw_topics WHERE active = true ORDER BY priority DESC"
            )
            topics = [row["query"] for row in cur.fetchall()]
            logger.info(
                "load_active_topics: returned %d topics: %s", len(topics), topics
            )
            return topics
    finally:
        conn.close()


def get_seen_post_ids() -> set[str]:
    """Return set of all post_ids already classified (for deduplication)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT post_id FROM rw_classifications")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def store_classification(post: dict, classification: dict) -> bool:
    """Save a classified Reddit post. post: dict from search_reddit_posts. classification: {classification, confidence, reason, summary}."""
    logger.info(
        "store_classification called: post_id=%s classification=%s",
        post.get("post_id"),
        classification.get("classification"),
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rw_classifications
                    (post_id, post_url, author_handle, topic_query,
                     classification, confidence, reason, summary, raw_post)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id) DO NOTHING
                """,
                (
                    post["post_id"],
                    post["post_url"],
                    post["author_handle"],
                    post["topic_query"],
                    classification["classification"],
                    classification["confidence"],
                    classification["reason"],
                    classification.get("summary"),
                    json.dumps(post),
                ),
            )
        return True
    except Exception as e:
        logger.error(
            "Failed to store classification for post %s: %s", post.get("post_id"), e
        )
        return False
    finally:
        conn.close()


def add_topic(query: str, category: str, priority: str = "medium") -> bool:
    """Add a new topic to rw_topics."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rw_topics (query, category, priority, active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (query) DO NOTHING
                """,
                (query, category, priority),
            )
        return True
    except Exception as e:
        logger.error("Failed to add topic %s: %s", query, e)
        return False
    finally:
        conn.close()


def get_interesting_posts(days: int = 7) -> list[dict[str, Any]]:
    """Retrieve INTERESTING-classified posts from the last N days."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM rw_classifications
                WHERE classification = 'INTERESTING'
                  AND classified_at > now() - make_interval(days => %s)
                ORDER BY classified_at DESC
                """,
                (days,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@tool
def store_cfp(
    event_name: str,
    event_url: str,
    cfp_url: str | None = None,
    location: str | None = None,
    event_date: str | None = None,
    cfp_deadline: str | None = None,
    topics: str | list[str] | None = None,
    source: str = "unknown",
) -> bool:
    """Store a Call For Papers entry in the database. Returns True if stored/updated."""
    logger.info(f"store_cfp called: event={event_name}, url={event_url}")
    conn = _get_conn()
    try:
        topics_list = (
            topics if isinstance(topics, list) else topics.split(",") if topics else []
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rw_cfps (event_name, event_url, cfp_url, location, event_date, cfp_deadline, topics, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_url) DO UPDATE SET
                    cfp_url = COALESCE(excluded.cfp_url, rw_cfps.cfp_url),
                    location = COALESCE(excluded.location, rw_cfps.location),
                    event_date = COALESCE(excluded.event_date, rw_cfps.event_date),
                    cfp_deadline = COALESCE(excluded.cfp_deadline, rw_cfps.cfp_deadline),
                    topics = ARRAY(SELECT DISTINCT unnest(rw_cfps.topics || excluded.topics)),
                    source = CASE WHEN rw_cfps.source = 'unknown' THEN excluded.source ELSE rw_cfps.source END
                """,
                (
                    event_name,
                    event_url,
                    cfp_url,
                    location,
                    event_date,
                    cfp_deadline,
                    topics_list,
                    source,
                ),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to store CFP {event_name}: {e}")
        return False
    finally:
        conn.close()


def get_recent_cfps(days: int = 30) -> list[dict[str, Any]]:
    """Retrieve CFPs found in the last N days from the database."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM rw_cfps
                WHERE created_at > now() - make_interval(days => %s)
                ORDER BY created_at DESC
                """,
                (days,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_seen_cfp_urls() -> set[str]:
    """Return set of all CFP event URLs already stored in the database (for deduplication)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT event_url FROM rw_cfps")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
