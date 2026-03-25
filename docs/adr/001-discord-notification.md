# ADR 001: Discord Notification over WhatsApp

## Status
Accepted

## Date
2026-03-25

## Context
The original implementation delivered curated digests via Twilio/WhatsApp. We need to switch to Discord for the following reasons:
- WhatsApp/Twilio has sandbox limitations and requires opt-in re-authentication
- Discord webhooks are simpler to configure and more reliable
- Discord supports rich formatting, mentions, and @here for high-signal alerts

## Decision
Replace Twilio/WhatsApp integration with Discord webhooks.

## Consequences
- **Positive**: Simpler deployment, no phone number management, better formatting
- **Positive**: @here pings for high-signal content, user mentions for important alerts
- **Negative**: User must have Discord app installed or use web

## Implementation
- New `src/core/tools/discord.py` module with webhook posting
- Supports mentions (`<@user_id>`) and `@here` for high-signal alerts
- Environment variables: `DISCORD_WEBHOOK_URL`, `DISCORD_NOTIFY_USER_ID`, `PING_THRESHOLD`