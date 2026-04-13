import logging
import os
import time
from typing import Any

import praw

logger = logging.getLogger(__name__)

_DEFAULT_MAX_POSTS = int(os.environ.get("MAX_POSTS_PER_SUBREDDIT", "20"))
WINDOW_HOURS = int(os.environ.get("REDDIT_WINDOW_HOURS", "168"))  # default 7 days
_MIN_UPVOTES_DEFAULT = int(os.environ.get("REDDIT_MIN_UPVOTES", "25"))
_FETCH_SAFETY_CAP = int(os.environ.get("REDDIT_FETCH_SAFETY_CAP", "500"))


def _get_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "RedditWatch/1.0"),
        ratelimit_seconds=300,
    )


def search_reddit_posts(subreddit: str, limit: int = _DEFAULT_MAX_POSTS, min_upvotes: int = _MIN_UPVOTES_DEFAULT) -> list[dict[str, Any]]:
    """Fetch posts from the last WINDOW_HOURS hours (default 7 days) from a subreddit.

    subreddit should be like 'LocalLLaMA' (no r/). sub.new() is sorted newest-first,
    so we stop iteration as soon as we hit a post older than the cutoff.
    """
    logger.info("search_reddit_posts called: subreddit=%r limit=%d min_upvotes=%d window_hours=%d", subreddit, limit, min_upvotes, WINDOW_HOURS)
    reddit = _get_reddit()
    subreddit_name = subreddit.lstrip("r/")
    cutoff = time.time() - (WINDOW_HOURS * 3600)
    try:
        sub = reddit.subreddit(subreddit_name)
        posts = []
        for post in sub.new(limit=_FETCH_SAFETY_CAP):
            if post.created_utc < cutoff:
                break  # sub.new() is sorted newest-first; stop once outside window
            if post.score >= min_upvotes:
                posts.append({
                    "post_id": post.id,
                    "text": f"{post.title}\n\n{post.selftext[:150] if post.selftext else ''}".strip(),
                    "author_handle": str(post.author) if post.author else "[deleted]",
                    "created_at": str(post.created_utc),
                    "post_url": f"https://reddit.com{post.permalink}",
                    "topic_query": subreddit,
                    "score": post.score,
                    "num_comments": post.num_comments,
                })
            if len(posts) >= limit:
                break
        return posts
    except Exception as e:
        logger.error("Reddit API error for subreddit %r: %s", subreddit, e)
        return []


def get_trending_subreddits() -> list[str]:
    """Return a list of currently popular posts across watched subreddits. Best-effort."""
    try:
        reddit = _get_reddit()
        trending = []
        for post in reddit.subreddit("all").hot(limit=10):
            trending.append(post.subreddit.display_name)
        return list(dict.fromkeys(trending))  # deduplicate, preserve order
    except Exception as e:
        logger.warning("Could not fetch trending subreddits: %s", e)
        return []
