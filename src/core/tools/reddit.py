import logging
import os
from typing import Any

import praw

logger = logging.getLogger(__name__)


def _get_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "TweetWatch/1.0"),
        ratelimit_seconds=300,
    )


def search_reddit_posts(subreddit: str, limit: int = 5) -> list[dict[str, Any]]:
    """Fetch recent posts from a subreddit. subreddit should be like 'LocalLLaMA' (no r/)."""
    logger.info("search_reddit_posts called: subreddit=%r limit=%d", subreddit, limit)
    reddit = _get_reddit()
    subreddit_name = subreddit.lstrip("r/")
    try:
        sub = reddit.subreddit(subreddit_name)
        posts = []
        for post in sub.new(limit=limit):
            posts.append(
                {
                    "post_id": post.id,
                    "text": f"{post.title}\n\n{post.selftext[:150] if post.selftext else ''}".strip(),
                    "author_handle": str(post.author) if post.author else "[deleted]",
                    "created_at": str(post.created_utc),
                    "post_url": f"https://reddit.com{post.permalink}",
                    "topic_query": subreddit,
                    "score": post.score,
                    "num_comments": post.num_comments,
                }
            )
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
