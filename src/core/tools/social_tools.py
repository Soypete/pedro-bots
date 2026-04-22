import json
import logging
import os
from typing import Any, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def _get_conn():
    conn = psycopg2.connect(os.environ["POSTGRES_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path = socialwatch")
    return conn


def load_active_feeds() -> list[dict[str, Any]]:
    """Load active RSS feeds from socialwatch.feeds."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM feeds WHERE active = true ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def add_feed(url: str, feed_type: str, name: Optional[str] = None, channel_id: Optional[str] = None) -> bool:
    """Add a new feed to monitor."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feeds (url, feed_type, name, channel_id, active)
                VALUES (%s, %s, %s, %s, true)
                ON CONFLICT DO NOTHING
                """,
                (url, feed_type, name, channel_id),
            )
        return True
    except Exception as e:
        logger.error("Failed to add feed %s: %s", url, e)
        return False
    finally:
        conn.close()


def add_content_item(url: str, title: Optional[str] = None, description: Optional[str] = None,
                     source_feed_id: Optional[str] = None, source_type: str = "manual", 
                     added_by: str = "cli") -> bool:
    """Add a new content item to potentially post about."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO content_items (url, title, description, source_feed_id, source_type, added_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (url, title, description, source_feed_id, source_type, added_by),
            )
        return True
    except Exception as e:
        logger.error("Failed to add content item %s: %s", url, e)
        return False
    finally:
        conn.close()


def get_unposted_items(limit: int = 20) -> list[dict[str, Any]]:
    """Get content items that haven't been posted yet."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get all unposted items first
            cur.execute(
                """
                SELECT ci.*, f.feed_type, f.name as feed_name
                FROM content_items ci
                LEFT JOIN feeds f ON ci.source_feed_id = f.id
                WHERE ci.posted = false
                ORDER BY ci.created_at DESC
                """,
            )
            all_items = [dict(row) for row in cur.fetchall()]
            
            # Sample to ensure diversity across feed types
            by_feed = {}
            for item in all_items:
                ft = item.get("feed_type") or "unknown"
                if ft not in by_feed:
                    by_feed[ft] = []
                by_feed[ft].append(item)
            
            # Take equal samples from each feed type
            sampled = []
            items_per_type = max(5, limit // max(len(by_feed), 1))
            for ft, items in by_feed.items():
                sampled.extend(items[:items_per_type])
            
            # Return up to limit
            return sampled[:limit]
    finally:
        conn.close()


def mark_item_posted(content_item_id: str) -> bool:
    """Mark a content item as posted."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE content_items 
                SET posted = true, posted_at = now()
                WHERE id = %s
                """,
                (content_item_id,),
            )
        return True
    except Exception as e:
        logger.error("Failed to mark item %s as posted: %s", content_item_id, e)
        return False
    finally:
        conn.close()


def store_posted_content(content_item_id: str, platform: str, post_id: str, 
                         post_url: str, post_text: str) -> bool:
    """Store a posted content record."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posted_content (content_item_id, platform, post_id, post_url, post_text)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (content_item_id, platform, post_id, post_url, post_text),
            )
        return True
    except Exception as e:
        logger.error("Failed to store posted content: %s", e)
        return False
    finally:
        conn.close()


def store_relevance_score(content_item_id: str, relevance_score: float, 
                          confidence: float, reason: str) -> bool:
    """Store LLM relevance score for a content item."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO relevance_scores (content_item_id, relevance_score, confidence, reason)
                VALUES (%s, %s, %s, %s)
                """,
                (content_item_id, relevance_score, confidence, reason),
            )
        return True
    except Exception as e:
        logger.error("Failed to store relevance score: %s", e)
        return False
    finally:
        conn.close()


def get_recent_posted_text(limit: int = 10) -> list[str]:
    """Get text from recently posted content (for context)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT post_text FROM posted_content 
                ORDER BY posted_at DESC 
                LIMIT %s
                """,
                (limit,),
            )
            return [row[0] for row in cur.fetchall() if row[0]]
    finally:
        conn.close()


def check_url_posted(url: str) -> bool:
    """Check if a URL has already been posted."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT posted FROM content_items WHERE url = %s", (url,))
            result = cur.fetchone()
            return result[0] if result else False
    finally:
        conn.close()


def add_content_url(url: str, title: Optional[str] = None) -> None:
    """CLI command to add a URL to track."""
    if add_content_item(url, title=title, source_type="manual"):
        print(f"Added: {url}")
    else:
        print(f"Failed to add: {url}")


def list_pending() -> None:
    """CLI command to list pending content items."""
    items = get_unposted_items(limit=20)
    if not items:
        print("No pending items.")
        return
    for item in items:
        print(f"- {item['url']} ({item.get('title', 'No title')})")