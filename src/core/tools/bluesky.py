import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

ATPROTO_BASE = "https://bsky.social"
BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")

_session_token = None
_session_did = None


def _get_session() -> Optional[dict]:
    """Get or create a Bluesky session."""
    global _session_token, _session_did
    
    if _session_token and _session_did:
        return {"token": _session_token, "did": _session_did}
    
    if not BLUESKY_HANDLE or not BLUESKY_APP_PASSWORD:
        logger.warning("Bluesky credentials not configured")
        return None
    
    try:
        response = requests.post(
            f"{ATPROTO_BASE}/xrpc/com.atproto.server.createSession",
            json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        _session_token = data["accessJwt"]
        _session_did = data["did"]
        logger.info("Bluesky session created for %s", BLUESKY_HANDLE)
        return {"token": _session_token, "did": _session_did}
    except requests.RequestException as e:
        logger.error("Failed to create Bluesky session: %s", e)
        return None


def _get_headers() -> dict[str, str]:
    """Get headers for AT Proto API requests."""
    session = _get_session()
    if not session:
        return {}
    return {
        "Authorization": f"Bearer {session['token']}",
        "Content-Type": "application/json",
    }


def post_to_bluesky(text: str, url: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Post content to Bluesky.
    
    Args:
        text: Post text content
        url: Optional URL to embed
        
    Returns:
        Dict with post_id and post_url, or None on failure
    """
    session = _get_session()
    if not session:
        logger.warning("Bluesky not configured - skipping post")
        return None
    
    if len(text) > 300:
        text = text[:297] + "..."
    
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": "2024-01-01T00:00:00.000Z",
    }
    
    if url:
        record["embed"] = {
            "$type": "app.bsky.embed.external",
            "external": {
                "$type": "app.bsky.embed.external#external",
                "uri": url,
                "title": text[:50],
                "description": text[:100],
            },
        }
    
    try:
        response = requests.post(
            f"{ATPROTO_BASE}/xrpc/com.atproto.server.createRecord",
            headers=_get_headers(),
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            timeout=30,
        )
        response.raise_for_status()
        
        data = response.json()
        uri = data.get("uri", "")
        post_id = uri.split("/")[-1] if uri else ""
        post_url = f"https://bsky.app/profile/{BLUESKY_HANDLE}/post/{post_id}"
        
        logger.info("Posted to Bluesky: %s", post_url)
        return {"post_id": post_id, "post_url": post_url, "text": text}
    except requests.RequestException as e:
        logger.error("Failed to post to Bluesky: %s - %s", e, response.text if hasattr(response, 'text') else '')
        return None


def is_bluesky_configured() -> bool:
    """Check if Bluesky is properly configured."""
    return bool(BLUESKY_HANDLE and BLUESKY_APP_PASSWORD)