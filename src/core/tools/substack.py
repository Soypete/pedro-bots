import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

SUBSTACK_BASE = "https://substack.com"
SUBSTACK_SESSION_COOKIE = os.environ.get("SUBSTACK_SESSION_COOKIE", "")
SUBSTACK_PUBLICATION = os.environ.get("SUBSTACK_PUBLICATION", "soypetetech")

_session = None


def _get_session() -> Optional[requests.Session]:
    """Get or create a Substack session."""
    global _session
    
    if _session is not None:
        return _session
    
    if not SUBSTACK_SESSION_COOKIE:
        logger.warning("Substack session cookie not configured")
        return None
    
    _session = requests.Session()
    _session.cookies.set("substack.sid", SUBSTACK_SESSION_COOKIE)
    _session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://{SUBSTACK_PUBLICATION}.substack.com/",
    })
    
    logger.info("Substack session created for %s", SUBSTACK_PUBLICATION)
    return _session


def post_note(text: str, url: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Post a Note to Substack.
    
    Args:
        text: Note text content
        url: Optional URL to include
        
    Returns:
        Dict with note_id and note_url, or None on failure
        
    Note: This uses Substack's unofficial API and may break.
    """
    session = _get_session()
    if not session:
        logger.warning("Substack not configured - skipping post")
        return None
    
    payload = {
        "body": text,
        "type": "note",
    }
    
    if url:
        payload["url"] = url
    
    try:
        response = session.post(
            f"{SUBSTACK_BASE}/api/v1/posts",
            json=payload,
            timeout=30,
        )
        
        if response.status_code == 401:
            logger.error("Substack authentication failed - check session cookie")
            return None
            
        response.raise_for_status()
        
        data = response.json()
        note_id = data.get("id", "")
        note_url = f"https://{SUBSTACK_PUBLICATION}.substack.com/p/{note_id}"
        
        logger.info("Posted to Substack Notes: %s", note_url)
        return {"note_id": note_id, "note_url": note_url, "text": text}
    except requests.RequestException as e:
        logger.error("Failed to post to Substack: %s", e)
        return None


def is_substack_configured() -> bool:
    """Check if Substack is properly configured."""
    return bool(SUBSTACK_SESSION_COOKIE and SUBSTACK_PUBLICATION)