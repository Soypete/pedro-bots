import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")


def _get_headers() -> dict[str, str]:
    """Get headers for LinkedIn API requests."""
    return {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def refresh_access_token(auth_code: str) -> Optional[str]:
    """Refresh the LinkedIn access token using an auth code.
    
    Args:
        auth_code: Authorization code from OAuth flow
        
    Returns:
        New access token, or None on failure
    """
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
        logger.error("LinkedIn client credentials not configured")
        return None
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": os.environ.get("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback"),
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }
    
    try:
        response = requests.post(LINKEDIN_TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        token = response.json().get("access_token")
        logger.info("LinkedIn access token refreshed successfully")
        return token
    except requests.RequestException as e:
        logger.error("Failed to refresh LinkedIn token: %s", e)
        return None


def post_to_linkedin(text: str, url: Optional[str] = None, title: Optional[str] = None, 
                     description: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Post content to LinkedIn.
    
    Args:
        text: Post text content
        url: Optional URL to share (article/link)
        title: Title for the shared link
        description: Description for the shared link
        
    Returns:
        Dict with post_id and post_url, or None on failure
    """
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_PERSON_URN:
        logger.warning("LinkedIn not configured - skipping post")
        return None
    
    if len(text) > 3000:
        text = text[:2997] + "..."
    
    share_content = {
        "shareCommentary": {"text": text},
    }
    
    if url:
        share_media_category = "ARTICLE"
        media = [{
            "status": "READY",
            "originalUrl": url,
        }]
        if title:
            media[0]["title"] = {"text": title}
        if description:
            media[0]["description"] = {"text": description}
        share_content["shareMediaCategory"] = share_media_category
        share_content["media"] = media
    else:
        share_content["shareMediaCategory"] = "NONE"
    
    payload = {
        "author": LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    
    try:
        response = requests.post(
            f"{LINKEDIN_API_BASE}/ugcPosts",
            headers=_get_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        
        post_id = response.headers.get("X-RestLi-Id", "").split(":")[-1]
        post_url = f"https://www.linkedin.com/feed/update/urn:li:share:{post_id}"
        
        logger.info("Posted to LinkedIn: %s", post_url)
        return {"post_id": post_id, "post_url": post_url, "text": text}
    except requests.RequestException as e:
        logger.error("Failed to post to LinkedIn: %s - %s", e, response.text if hasattr(response, 'text') else '')
        return None


def is_linkedin_configured() -> bool:
    """Check if LinkedIn is properly configured."""
    return bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN)