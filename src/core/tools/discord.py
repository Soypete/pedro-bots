import logging
import os

import requests

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_NOTIFY_USER_ID = os.environ.get("DISCORD_NOTIFY_USER_ID", "")
DISCORD_PING_THRESHOLD = float(os.environ.get("DISCORD_PING_THRESHOLD", "0.8"))


def send_discord_message(body: str, high_signal: bool = False) -> bool:
    """Send a message to Discord via webhook.
    
    Args:
        body: The message content to send
        high_signal: If True, ping @here for high-signal posts (confidence >= threshold)
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set — skipping Discord notification")
        return False
        
    if "-- 0 of" in body or "No relevant" in body:
        logger.info("Skipping Discord send — no interesting posts in digest")
        return True
        
    try:
        mentions = []
        if high_signal:
            mentions.append("@here")
        if DISCORD_NOTIFY_USER_ID:
            mentions.append(f"<@{DISCORD_NOTIFY_USER_ID}>")
        
        payload = {
            "content": " ".join(mentions) + " " + body if mentions else body,
            "allowed_mentions": {
                "parse": ["everyone", "roles"] if high_signal else [],
                "users": [DISCORD_NOTIFY_USER_ID] if DISCORD_NOTIFY_USER_ID else []
            }
        }
        
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Discord message sent (%d chars)", len(body))
        return True
    except Exception as e:
        logger.error("Failed to send Discord message: %s", e)
        return False


def is_high_signal(confidence: float) -> bool:
    """Determine if a post is high-signal enough to ping @here."""
    return confidence >= DISCORD_PING_THRESHOLD