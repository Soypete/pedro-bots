import logging
import os
import asyncio
import threading

import discord

logger = logging.getLogger(__name__)

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_NAME = os.environ.get("DISCORD_CHANNEL_NAME", "interesting-content")
DISCORD_NOTIFY_USER_ID = os.environ.get("DISCORD_NOTIFY_USER_ID", "")
DISCORD_PING_THRESHOLD = float(os.environ.get("DISCORD_PING_THRESHOLD", "0.8"))

_client = None
_channel = None
_loop = None
_thread = None
_ready_event = threading.Event()


def _run_in_discord_thread(coro):
    """Run an async coroutine in the persistent Discord event loop."""
    global _loop
    if _loop is None:
        return None
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=30)


def _discord_worker():
    """Persistent thread that runs the Discord event loop."""
    global _client, _channel, _loop, _ready_event

    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    intents = discord.Intents.default()
    intents.message_content = True

    _client = discord.Client(intents=intents)

    @_client.event
    async def on_ready():
        logger.info("Discord bot logged in as %s", _client.user)
        _ready_event.set()

    @_client.event
    async def on_connect():
        logger.info("Discord bot connected")

    _loop.run_until_complete(_client.login(DISCORD_BOT_TOKEN))
    _loop.run_until_complete(_client.connect())


def _ensure_connected(channel: str = None):
    """Ensure Discord client is connected in background thread."""
    global _client, _channel, _thread, _ready_event

    if _channel is not None:
        return _channel

    if not DISCORD_BOT_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN not set — skipping Discord notification")
        return None

    if _thread is None:
        _thread = threading.Thread(target=_discord_worker, daemon=True)
        _thread.start()
        if not _ready_event.wait(timeout=15):
            logger.error("Discord client failed to connect (timeout)")
            return None

    channel_name = channel or DISCORD_CHANNEL_NAME
    
    for guild in _client.guilds:
        for ch in guild.text_channels:
            if ch.name == channel_name:
                _channel = ch
                logger.info("Found channel %s with ID %s", channel_name, ch.id)
                return _channel

    logger.error("Channel %s not found", channel_name)
    return None


def send_discord_message(body: str, high_signal: bool = False, channel: str = None) -> bool:
    """Send a message to Discord via bot session.
    
    Args:
        body: The message content to send
        high_signal: If True, ping @here for high-signal posts (confidence >= threshold)
        channel: Channel name to post to (defaults to DISCORD_CHANNEL_NAME)
    """
    if "-- 0 of" in body or "No relevant" in body:
        logger.info("Skipping Discord send — no interesting posts in digest")
        return True

    try:
        channel = _ensure_connected(channel)
    except Exception as e:
        logger.error("Failed to get Discord channel: %s", e)
        return False

    if not channel:
        logger.warning("Discord channel not available — skipping notification")
        return False

    try:
        mentions = []
        if high_signal:
            mentions.append("@here")
        if DISCORD_NOTIFY_USER_ID:
            mentions.append(f"<@{DISCORD_NOTIFY_USER_ID}>")

        message = " ".join(mentions) + " " + body if mentions else body

        _run_in_discord_thread(channel.send(message))
        logger.info("Discord message sent (%d chars)", len(body))
        return True
    except Exception as e:
        logger.error("Failed to send Discord message: %s", e)
        return False


def is_high_signal(confidence: float) -> bool:
    """Determine if a post is high-signal enough to ping @here."""
    return confidence >= DISCORD_PING_THRESHOLD