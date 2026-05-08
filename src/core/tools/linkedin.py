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
                     description: Optional[str] = None, comment_with_url: bool = True) -> Optional[dict[str, Any]]:
    """Post content to LinkedIn.

    Args:
        text: Post text content (should NOT include URL - LinkedIn penalizes links in posts)
        url: Optional URL to share - will be added as a comment if comment_with_url=True
        title: Title for the shared link (used if url is embedded)
        description: Description for the shared link (used if url is embedded)
        comment_with_url: If True, post text-only first, then add link as comment (better reach)

    Returns:
        Dict with post_id and post_url, or None on failure
    """
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_PERSON_URN:
        logger.warning("LinkedIn not configured - skipping post")
        return None

    if len(text) > 3000:
        text = text[:2997] + "..."

    if comment_with_url and url:
        return _post_with_url_comment(text, url, title, description)
    else:
        return _post_with_embedded_link(text, url, title, description)


def _post_with_url_comment(text: str, url: str, title: Optional[str], description: Optional[str]) -> Optional[dict[str, Any]]:
    """Post text-only first, then add URL as a comment (better organic reach)."""
    share_content = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "NONE",
    }

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

        post_urn = response.headers.get("X-RestLi-Id", "")
        post_id = post_urn.split(":")[-1]
        post_url = f"https://www.linkedin.com/feed/update/urn:li:share:{post_id}"

        logger.info("Posted text-only to LinkedIn: %s", post_url)

        url_comment = f"🔗 Read more: {url}"
        _add_comment_to_post(post_urn, url_comment)

        return {"post_id": post_id, "post_url": post_url, "text": text, "url_added_as_comment": True}
    except requests.RequestException as e:
        logger.error("Failed to post to LinkedIn: %s - %s", e, response.text if hasattr(response, 'text') else '')
        return None


def _post_with_embedded_link(text: str, url: Optional[str], title: Optional[str], description: Optional[str]) -> Optional[dict[str, Any]]:
    """Post with link embedded (legacy behavior, worse reach)."""
    share_content = {
        "shareCommentary": {"text": text},
    }

    if url:
        share_content["shareMediaCategory"] = "ARTICLE"
        media = [{
            "status": "READY",
            "originalUrl": url,
        }]
        if title:
            media[0]["title"] = {"text": title}
        if description:
            media[0]["description"] = {"text": description}
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


def _add_comment_to_post(post_urn: str, comment_text: str) -> bool:
    """Add a comment to an existing post."""
    try:
        response = requests.post(
            f"{LINKEDIN_API_BASE}/ugcPosts/{post_urn}/comments",
            headers=_get_headers(),
            json={"commentary": comment_text},
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Added comment with URL to LinkedIn post")
        return True
    except requests.RequestException as e:
        logger.error("Failed to add comment to LinkedIn post: %s", e)
        return False


def is_linkedin_configured() -> bool:
    """Check if LinkedIn is properly configured."""
    return bool(LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN)