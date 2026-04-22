import collections
import json
import logging
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import get_llm
from core.tools import rss as rss_tool
from core.tools import social_tools
from core.tools.discord import send_discord_message
from core.tools import linkedin, bluesky, substack
from core.middleware_config import build_middleware, log_audit_summary

logger = logging.getLogger(__name__)

VOICE_ANALYSIS_PROMPT = """You are analyzing the writing style of Miriah Peterson (soypete/soypete.tech), 
a thought leader in the software+AI space who helps people build AI with security, data, and privacy in mind.
She is also a cohost of the "Domesticating Open AI" podcast with Matt Sharp and Chris Brousseau.

Analyze the writing style from these recent blog posts. 
Focus on: sentence length, tone (casual/formal), common phrases, vocabulary level.
Respond with JSON only:
{{"voice_summary": "2-3 sentence description of the writing style", "example_phrases": ["phrase1", "phrase2"]}}

Posts:
{posts}"""

RELEVANCE_PROMPT = """You are a content curator. Given a piece of content and recent posts you've made, 
evaluate if this is worth sharing as a thought leader.

Content to evaluate:
- Title: {title}
- Description: {description}
- URL: {url}

Your recent posts (for context on what you've already shared):
{recent_posts}

Respond with JSON only:
{{"relevant": true/false, "reason": "one sentence explanation", "confidence": 0.0-1.0, "suggested_text": "compelling 2-3 sentence hook in your voice"}}

ONLY mark as relevant if:
- It's genuinely interesting or useful to your audience (tech professionals, founders, builders)
- It's NOT just a routine commit/branch/update with no real story
- It has some substance - a real insight, useful resource, interesting project, or thoughtful analysis
- It's share-worthy: would this make someone say "oh that's cool" or "I learned something"?

Skip: boring commits, minor updates, purely technical changes with no broader meaning, things you've already covered."""

REWRITE_PROMPT = """You are a thought leader writing a compelling social media post. Use this voice/style:
{voice}

Original content:
- Title: {title}
- Description: {description}
- URL: {url}

Write a {platform} post (max {max_chars} chars) that:
1. Opens with a hook that makes people stop scrolling - could be a provocative question, bold statement, or surprising insight
2. Adds YOUR unique perspective - why does this matter? What's the hidden angle? Why should readers care?
3. Shows genuine enthusiasm or skepticism - don't just summarize
4. Include 1-2 relevant hashtags if appropriate for {platform}
5. End with engagement: ask a question, invite discussion, or direct to click through

Write like you're telling a friend something interesting. Not "check this out" - more like "this really got me thinking about...". Make them want to click."""


def fetch_voice_from_rss(limit: int = 5) -> str:
    """Fetch recent Substack posts to understand your writing style."""
    feed_url = os.environ.get("SUBSTACK_RSS_FEED", "https://soypetetech.substack.com/feed")
    items = rss_tool.fetch_rss_feed(feed_url, limit=limit)
    
    if not items:
        return "Casual, technical, direct. Uses short sentences. No fluff."
    
    posts_text = "\n\n".join([
        f"Title: {item.get('title', '')}\n{item.get('description', '')}"
        for item in items[:limit]
    ])
    
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=VOICE_ANALYSIS_PROMPT.format(posts=posts_text)),
    ])
    
    try:
        result = json.loads(response.content)
        return result.get("voice_summary", "Casual, technical, direct.")
    except json.JSONDecodeError:
        return "Casual, technical, direct."


def analyze_relevance(item: dict, recent_posts: list[str]) -> dict:
    """Use LLM to evaluate if content is relevant to post about."""
    recent_text = "\n".join([f"- {p[:100]}..." for p in recent_posts[:5]]) or "No recent posts"
    
    response = get_llm().invoke([
        SystemMessage(content=RELEVANCE_PROMPT.format(
            title=item.get("title", ""),
            description=item.get("description", ""),
            url=item.get("url", ""),
            recent_posts=recent_text,
        )),
    ])
    
    try:
        result = json.loads(response.content)
        return result
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', response.content, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"relevant": False, "reason": "parse error", "confidence": 0.0, "suggested_text": None}


def rewrite_for_platform(item: dict, voice: str, platform: str, max_chars: int = 280) -> str:
    """Rewrite content for a specific platform in the user's voice."""
    platform_limits = {
        "bluesky": 280,
        "substack": 500,
        "linkedin": 3000,
        "discord": 2000,
    }
    limit = platform_limits.get(platform, 280)
    
    response = get_llm().invoke([
        SystemMessage(content=REWRITE_PROMPT.format(
            voice=voice,
            title=item.get("title", ""),
            description=item.get("description", ""),
            url=item.get("url", ""),
            platform=platform,
            max_chars=limit,
        )),
    ])
    
    return response.content.strip()


def fetch_rss_feeds(feeds: list[dict]) -> list[dict]:
    """Fetch new content from RSS feeds."""
    new_items = []
    
    for feed in feeds:
        feed_type = feed.get("feed_type")
        url = feed.get("url")
        
        if feed_type == "youtube":
            channel_id = feed.get("channel_id", "")
            items = rss_tool.fetch_youtube_channel(channel_id)
        elif feed_type == "substack":
            # Use URL if it's a full URL, otherwise treat name as publication name
            if url and ("substack.com" in url or url.startswith("http")):
                items = rss_tool.fetch_rss_feed(url)
            else:
                items = rss_tool.fetch_substack_feed(feed.get("name", ""))
        elif feed_type == "github" or "github" in feed.get("name", "").lower():
            # Use GitHub API for better details
            import re
            # Handle both github.com/username and github.com/username.atom
            match = re.search(r"github\.com/([^/.]+)", url)
            username = match.group(1) if match else "Soypete"
            items = rss_tool.fetch_github_user_events(username)
        else:
            items = rss_tool.fetch_rss_feed(url)
        
        for item in items:
            title = item.get("title", "").lower()
            url = item.get("link", "")
            
            # Skip boring GitHub events
            if feed.get("feed_type") == "generic" and "github" in url.lower():
                if not any(kw in title for kw in ["pull request", "issue", "released", "opened", "merged"]):
                    continue
            
            if not social_tools.check_url_posted(url):
                social_tools.add_content_item(
                    url=url,
                    title=item.get("title"),
                    description=item.get("description"),
                    source_feed_id=str(feed.get("id")),
                    source_type="rss",
                    added_by=feed.get("name", "rss"),
                )
                # Also store feed_type for later reference
                item["feed_type"] = feed.get("feed_type")
                new_items.append(item)
    
    return new_items


def post_to_discord(item: dict, text: str, dry_run: bool = False) -> dict:
    """Post content to Discord #social-posts channel."""
    discord_text = f"{text}\n\n{item.get('url', '')}"
    
    if dry_run:
        print(f"\n--- DRY RUN: would post to Discord ---")
        print(f"Text: {discord_text[:500]}...")
        print("--- END DRY RUN ---")
        return {"posted": True}
    
    result = send_discord_message(discord_text, channel="social-posts")
    return {"posted": result, "platform": "discord"}


def run_social_poster(dry_run: bool = False) -> None:
    """Main entry point for the social poster agent."""
    logger.info("SocialPoster run starting at %s (dry_run=%s)", datetime.now(timezone.utc).isoformat(), dry_run)
    _, auditor = build_middleware()
    
    voice = fetch_voice_from_rss()
    logger.info("Loaded voice: %s", voice[:100])
    
    feeds = social_tools.load_active_feeds()
    logger.info("Loaded %d active feeds", len(feeds))
    
    fetch_rss_feeds(feeds)
    
    items = social_tools.get_unposted_items(limit=30)
    if not items:
        logger.info("No unposted content items - exiting")
        log_audit_summary(auditor)
        return
    
    logger.info("Found %d unposted items to evaluate", len(items))
    
    recent_posts = social_tools.get_recent_posted_text(limit=5)
    
    ranked_items = []
    for item in items:
        # Skip boring GitHub events early
        feed_type = item.get("feed_type") or "unknown"
        feed_name = (item.get("feed_name") or "").lower()
        title = (item.get("title") or "").lower()
        if "github" in feed_name:
            feed_type = "github"
        if feed_type == "github":
            skip_boring = any(kw in title for kw in ["pushed", "created a branch", "created tag", "pushed to"])
            if skip_boring:
                logger.debug("Skipping boring GitHub early: %s", title[:40])
                continue
        
        relevance = analyze_relevance(item, recent_posts)
        
        if relevance.get("relevant") or relevance.get("confidence", 0) > 0.5:
            social_tools.store_relevance_score(
                content_item_id=str(item["id"]),
                relevance_score=1.0 if relevance.get("relevant") else relevance.get("confidence", 0),
                confidence=relevance.get("confidence", 0),
                reason=relevance.get("reason", ""),
            )
            item["relevance"] = relevance
            ranked_items.append(item)
    
    ranked_items.sort(key=lambda x: x.get("relevance", {}).get("confidence", 0), reverse=True)
    
    feed_counts = collections.Counter(i.get("feed_type") for i in ranked_items)
    logger.info("Ranked items by feed_type: %s", dict(feed_counts))
    
    # Group items by feed type
    by_feed_type = {}
    for item in ranked_items:
        feed_type = item.get("feed_type") or "unknown"
        feed_name = (item.get("feed_name") or "").lower()
        title = (item.get("title") or "").lower()
        
        # Normalize feed types
        if "github" in feed_name:
            feed_type = "github"
        
        # Skip boring GitHub events early
        if feed_type == "github":
            skip_boring = any(kw in title for kw in ["pushed", "created a branch", "created tag"])
            if skip_boring:
                logger.debug("Skipping boring GitHub: %s", title[:40])
                continue
        
        if feed_type not in by_feed_type:
            by_feed_type[feed_type] = []
        by_feed_type[feed_type].append(item)
    
    # Pick top item from each feed type for diversity
    top_items = []
    selected_types = set()
    for feed_type in ["youtube", "substack", "github"]:
        if feed_type in by_feed_type and by_feed_type[feed_type]:
            top_items.append(by_feed_type[feed_type][0])
            selected_types.add(feed_type)
            logger.info("Selected from %s: %s", feed_type, by_feed_type[feed_type][0].get("title", "")[:40])
    
    # Fill remaining slots with next-best from OTHER sources
    remaining = 3 - len(top_items)
    if remaining > 0:
        already_selected = set(id(i) for i in top_items)
        for item in ranked_items:
            if id(item) not in already_selected:
                feed_type = item.get("feed_type") or "unknown"
                # Don't add more from same type
                if feed_type in selected_types:
                    continue
                if len(top_items) < 3:
                    top_items.append(item)
                    selected_types.add(feed_type)
                    logger.info("Filled: %s", item.get("title", "")[:40])
    
    logger.info("Selected top %d items for posting (diverse by feed type): %s", len(top_items), [i.get("title", "")[:30] for i in top_items])
    
    platforms = ["discord", "linkedin", "bluesky", "substack"]
    
    for item in top_items:
        suggested = item.get("relevance", {}).get("suggested_text")
        
        # Generate drafts for all platforms, post all to Discord for review
        all_drafts = []
        
        for platform in platforms:
            text = suggested or rewrite_for_platform(item, voice, platform)
            url = item.get("url", "")
            
            platform_labels = {
                "discord": "📱 Discord",
                "linkedin": "💼 LinkedIn", 
                "bluesky": "🐦 Bluesky",
                "substack": "✍️ Substack Notes"
            }
            
            draft = f"{platform_labels.get(platform, platform)}\n{text}\n🔗 {url}"
            all_drafts.append(draft)
            
            logger.info("Generated draft for %s: %s", platform, item.get("title", "")[:50])
        
        if not dry_run:
            # Post all drafts to Discord as a review message
            for i, draft in enumerate(all_drafts):
                result = post_to_discord(item, draft, dry_run=False)
                if i == 0:
                    if result.get("posted"):
                        logger.info("Posted draft to Discord: %s", item.get("url"))
        
        if not dry_run:
            social_tools.mark_item_posted(str(item["id"]))
    
    if not dry_run and top_items:
        send_discord_message(f"Social poster complete: generated drafts for {len(top_items)} items across {len(platforms)} platforms")
    
    log_audit_summary(auditor)
    logger.info("SocialPoster run complete")