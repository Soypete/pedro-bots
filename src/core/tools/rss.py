import logging
import os
from datetime import datetime
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

RSS_FEED_TIMEOUT = 30
GITHUB_API_URL = "https://api.github.com"


def fetch_rss_feed(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch and parse an RSS/Atom feed.
    
    Args:
        url: RSS feed URL
        limit: Maximum number of items to return
        
    Returns:
        List of feed items with title, link, description, published
    """
    try:
        response = requests.get(url, timeout=RSS_FEED_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch RSS feed %s: %s", url, e)
        return []
    
    feed = feedparser.parse(response.content)
    
    items = []
    for entry in feed.entries[:limit]:
        item = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "description": entry.get("description", "")[:500],
            "published": None,
        }
        
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                item["published"] = datetime(*entry.published_parsed[:6])
            except Exception:
                pass
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                item["published"] = datetime(*entry.updated_parsed[:6])
            except Exception:
                pass
                
        items.append(item)
    
    logger.info("Fetched %d items from RSS feed %s", len(items), url)
    return items


def fetch_youtube_channel(channel_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Fetch latest videos from a YouTube channel via RSS.
    
    Args:
        channel_id: YouTube channel ID
        limit: Maximum number of videos to return
        
    Returns:
        List of video items
    """
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return fetch_rss_feed(url, limit)


def fetch_substack_feed(publication_url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch posts from a Substack RSS feed.
    
    Args:
        publication_url: Substack publication name (e.g., 'soypetetech')
        limit: Maximum number of posts to return
        
    Returns:
        List of post items
    """
    url = f"https://{publication_url}.substack.com/feed"
    return fetch_rss_feed(url, limit)


def fetch_github_user_events(username: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent GitHub events for a user with more details than RSS.
    
    Args:
        username: GitHub username
        limit: Maximum number of events to return
        
    Returns:
        List of events with details including commit messages
    """
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/users/{username}/events/public",
            params={"per_page": limit * 2},
            timeout=RSS_FEED_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch GitHub events for %s: %s", username, e)
        return []
    
    events = response.json()
    items = []
    
    for event in events:
        event_type = event.get("type")
        repo = event.get("repo", {}).get("name", "")
        
        if event_type == "PushEvent":
            commits = event.get("payload", {}).get("commits", [])
            commit_msgs = [c.get("message", "") for c in commits[:3]]
            branch = event.get("payload", {}).get("ref", "").replace("refs/heads/", "")
            if commits:
                title = f"{username} pushed {len(commits)} commit(s) to {repo}"
                description = " | ".join(commit_msgs) if commit_msgs else "Code updates"
            elif branch:
                title = f"{username} pushed to {branch} in {repo}"
                description = "Code updates"
            else:
                title = f"{username} pushed to {repo}"
                description = "Code updates"
            link = f"https://github.com/{repo}"
        elif event_type == "PullRequestEvent":
            pr = event.get("payload", {}).get("pull_request", {})
            title = pr.get("title", "Pull Request")
            description = pr.get("body", "")[:200] or f"PR to {repo}"
            link = pr.get("html_url", f"https://github.com/{repo}")
        elif event_type == "IssuesEvent":
            issue = event.get("payload", {}).get("issue", {})
            action = event.get("payload", {}).get("action", "")
            title = f"Issue {action}: {issue.get('title', '')}"
            description = issue.get("body", "")[:200] or f"Issue on {repo}"
            link = issue.get("html_url", f"https://github.com/{repo}")
        elif event_type == "CreateEvent":
            ref_type = event.get("payload", {}).get("ref_type", "")
            title = f"Created {ref_type} in {repo}"
            description = event.get("payload", {}).get("description", "")
            link = f"https://github.com/{repo}"
        elif event_type == "ReleaseEvent":
            release = event.get("payload", {}).get("release", {})
            title = f"Released: {release.get('tag_name', '')}"
            description = release.get("body", "")[:200] or f"New release in {repo}"
            link = release.get("html_url", f"https://github.com/{repo}")
        elif event_type == "PullRequestReviewEvent":
            pr = event.get("payload", {}).get("pull_request", {})
            action = event.get("payload", {}).get("action", "")
            title = f"Reviewed PR in {repo}"
            description = f"Review: {action} - {pr.get('title', 'Pull Request')}"
            link = pr.get("html_url", f"https://github.com/{repo}")
        elif event_type == "PullRequestEvent":
            pr = event.get("payload", {}).get("pull_request", {})
            action = event.get("payload", {}).get("action", "")
            title = f"PR {action} in {repo}: {pr.get('title', 'Pull Request')[:50]}"
            description = pr.get("body", "")[:200] or f"PR {action} in {repo}"
            link = pr.get("html_url", f"https://github.com/{repo}")
        elif event_type == "DeleteEvent":
            ref_type = event.get("payload", {}).get("ref_type", "")
            title = f"Deleted {ref_type} in {repo}"
            description = event.get("payload", {}).get("description", "") or f"Deleted {ref_type}"
            link = f"https://github.com/{repo}"
        else:
            continue
        
        items.append({
            "title": title,
            "link": link,
            "description": description,
            "published": event.get("created_at"),
            "source": "github",
        })
        
        if len(items) >= limit:
            break
    
    return items