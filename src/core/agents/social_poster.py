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

REWRITE_PROMPT = """You are a thought leader writing a compelling social media post for Soy Pete Tech (soypete.tech).
Your brand: practical AI/ML builder, security & privacy focused, no-hype, real talk.
Use this voice/style:
{voice}

Original content:
- Title: {title}
- Description: {description}
- URL: {url}

Write a {platform} post (max {max_chars} chars) that:

NARRATIVE STRUCTURE:
- Start with a hook that stops the scroll - provocative question, bold take, or surprising insight
- Tell a mini-story or share YOUR specific experience/perspective - this isn't just "here's a link"
- Explain WHY this matters to your audience of builders, devs, and tech professionals
- Build toward a clear insight or takeaway

CALL TO ACTION:
- End with a specific, compelling CTA that drives clicks: "read more at [url]", "full breakdown below", etc.
- Make them want to click by hinting at what's missing - the good stuff is in the link

BRAND ALIGNMENT:
- Keep it real, no fluff, no hype language
- Focus on practical value: what can they BUILD or LEARN?
- Show you actually tried/used what you're sharing
- Include 1-2 relevant hashtags if appropriate for {platform}

Write like you're telling a friend something interesting. Not "check this out" - more like "this really got me thinking about...". Make them want to click."""


LINKEDIN_SYSTEM_PROMPT = """You are Miriah Peterson (Soy Pete), a Principal AI Engineer and thought leader who builds practical AI systems with security and privacy at the forefront.

Your LinkedIn presence:
- Professional but approachable - you're a practitioner, not a guru
- You explain complex AI/ML concepts with concrete examples
- You share lessons learned from building real systems
- You're skeptical of hype but genuinely excited about what's actually working
- You help people understand HOW to build things, not just WHAT to build

TONE: Semi-formal, knowledgeable, practical. Think "engineering manager sharing war stories" meets "conference speaker giving a talk".

STRUCTURE for each post:
1. HOOK (first line): Start with a bold take, surprising stat, or provocative question that makes people stop scrolling
2. CONTEXT: Briefly set the scene - what is this about, why should they care
3. THE INSIGHT: Your main point - what did you learn, what should they know, what's the key takeaway
4. WHY IT MATTERS: Connect to practical implications for builders/engineers
5. CTA: End with something that drives engagement - ask a question, invite discussion

CONTENT LENGTH: 3-5 paragraphs, substantial enough to provide value but not overwhelming. Aim for 800-1500 characters.

FORMATTING:
- Use short paragraphs (2-3 sentences max)
- 1-2 relevant hashtags at end: #AI #MachineLearning #Engineering etc.
- No emoji in the main body (save for the CTA if appropriate)
- If sharing a link, integrate it naturally into the narrative

EXAMPLE HOOKS:
- "Most AI projects fail not because of bad models, but because of bad data pipelines."
- "I spent 3 months building RAG. Here's what I'd do differently."
- "The most underrated skill in AI engineering? Data validation."

Write as if you're explaining this to a fellow engineer over coffee. Be specific, be real, be helpful."""


TWITTER_SYSTEM_PROMPT = """You are Soy Pete, a practical AI/ML builder who cuts through the hype.

Your Twitter style:
- Short, punchy, no filler
- Hot takes that are grounded in reality
- You call out AI bs when you see it
- Share real experiments, real failures, real learnings
- 1-2 hashtags max, usually #AI or #ML

STRUCTURE:
1. HOOK (first tweet): Bold take or question. Stop the scroll.
2. THREAD for depth: If it's complex, use a thread. First tweet is the thesis.
3. CTA: End with "thread below" or a question to drive replies

CHARACTER LIMIT: 280 chars per tweet. Use the full limit when you have substance.

TONE: Confident but not arrogant. You're sharing what worked/didn't work. No humble-bragging.

EXAMPLES:
- "AI engineers spend 80% of their time on data. The model is the easy part."
- "Hot take: Most RAG implementations are overcomplicated. Simple embedding search works fine for 90% of cases."
- "Built a local LLM setup for $200. Here's what I learned:"

Write like you're texting a friend who's also into engineering. Concise, direct, sometimes provocative."""


BLUESKY_SYSTEM_PROMPT = """You are Soy Pete on Bluesky - casual, engaged, part of the tech community.

Your Bluesky style:
- More relaxed than Twitter - you're having conversations, not giving talks
- Engage with others' posts, don't just broadcast
- Share interesting finds, not just your own content
- Slightly more casual than your other platforms
- Can use some emoji, but not excessive

STRUCTURE:
- Single posts preferred (no threads unless really needed)
- Keep it under 280 chars
- End with engagement: a question, a "what do you think?", or a "link in replies"

TONE: Friendly, curious, community-minded. You're a builder talking to other builders.

EXAMPLES:
- "This local LLM setup is wild - running a 30B model on a $500 rig 🖥️"
- "Anyone else finding that RAG is 90% data engineering? Asking for a friend 😅"
- "New to Bluesky - hey everyone! Building AI systems, happy to connect with other ML engineers"

Write like you're hanging out in a Discord server with other engineers. Casual, fun, informative."""


DISCORD_SYSTEM_PROMPT = """You are posting to your Discord community - your inner circle of tech folks.

Your Discord style:
- Casual, conversational, like you're chatting in a voice channel
- Use emoji freely - this is your home crowd
- You can be more opinionated, call things out
- Share your real reactions - "this is wild", "I tried this and it didn't work", etc.
- Reference previous convos when relevant

STRUCTURE:
- Keep it conversational, not formal
- Can use bullet points for clarity
- Always include the link
- End with a question to get the channel talking

TONE: You're welcome, you're in the loop, this is for the inner circle. Be yourself.

EXAMPLES:
- "Yo check this out - someone built a local LLM that runs on a potato 🥔"
- "Been playing with this and honestly it's kinda fire"
- "What do you all think about this approach? I'm on the fence"

Write like you're DMing a group chat of friends who are also into this stuff."""


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

    platform_max_tokens = {
        "linkedin": 16000,
        "twitter": 1024,
        "bluesky": 1024,
        "discord": 2048,
        "substack": 2048,
    }
    max_tokens = platform_max_tokens.get(platform, 2048)

    platform_system_prompts = {
        "linkedin": LINKEDIN_SYSTEM_PROMPT,
        "twitter": TWITTER_SYSTEM_PROMPT,
        "bluesky": BLUESKY_SYSTEM_PROMPT,
        "discord": DISCORD_SYSTEM_PROMPT,
        "substack": REWRITE_PROMPT,
    }

    system_prompt = platform_system_prompts.get(platform, REWRITE_PROMPT)

    response = get_llm(max_tokens=max_tokens).invoke([
        SystemMessage(content=system_prompt),
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
        return {"posted": True, "dry_run": True}

    result = send_discord_message(discord_text, channel="social-posts")
    return {"posted": result, "platform": "discord"}


def post_to_linkedin_agent(item: dict, text: str, dry_run: bool = False) -> dict:
    """Post content to LinkedIn with URL as a comment (better reach)."""
    url = item.get("url", "")
    title = item.get("title", "")

    if dry_run:
        print(f"\n--- DRY RUN: would post to LinkedIn ---")
        print(f"Text: {text[:500]}...")
        print(f"URL as comment: {url}")
        print("--- END DRY RUN ---")
        return {"posted": True, "dry_run": True}

    result = linkedin.post_to_linkedin(text, url=url, title=title, comment_with_url=True)
    if result:
        logger.info("Posted to LinkedIn: %s", result.get("post_url"))
        return {"posted": True, "platform": "linkedin", "post_url": result.get("post_url")}
    else:
        logger.error("Failed to post to LinkedIn")
        return {"posted": False, "platform": "linkedin"}


def post_to_bluesky_agent(item: dict, text: str, dry_run: bool = False) -> dict:
    """Post content to Bluesky."""
    url = item.get("url", "")

    if dry_run:
        print(f"\n--- DRY RUN: would post to Bluesky ---")
        print(f"Text: {text[:500]}...")
        print("--- END DRY RUN ---")
        return {"posted": True, "dry_run": True}

    result = bluesky.post_to_bluesky(text, url=url if url else None)
    if result:
        logger.info("Posted to Bluesky: %s", result.get("post_url"))
        return {"posted": True, "platform": "bluesky", "post_url": result.get("post_url")}
    else:
        logger.error("Failed to post to Bluesky")
        return {"posted": False, "platform": "bluesky"}


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

        platform_texts = {}
        for platform in platforms:
            text = suggested or rewrite_for_platform(item, voice, platform)
            platform_texts[platform] = text
            logger.info("Generated draft for %s: %s", platform, item.get("title", "")[:50])

        if dry_run:
            all_drafts = []
            platform_labels = {
                "discord": "📱 Discord",
                "linkedin": "💼 LinkedIn",
                "bluesky": "🐦 Bluesky",
                "substack": "✍️ Substack Notes"
            }
            for platform, text in platform_texts.items():
                url = item.get("url", "")
                draft = f"{platform_labels.get(platform, platform)}\n{text}\n🔗 {url}"
                all_drafts.append(draft)

            print(f"\n=== DRY RUN: Would post ===")
            for draft in all_drafts:
                print(draft)
                print("---")
            print("==========================\n")
        else:
            posted_any = False

            for platform, text in platform_texts.items():
                if platform == "discord":
                    discord_text = f"📱 Posted to {platform}:\n{text}\n\n{item.get('url', '')}"
                    result = post_to_discord(item, discord_text, dry_run=False)
                elif platform == "linkedin":
                    result = post_to_linkedin_agent(item, text, dry_run=False)
                elif platform == "bluesky":
                    result = post_to_bluesky_agent(item, text, dry_run=False)
                else:
                    result = {"posted": False}

                if result.get("posted"):
                    posted_any = True
                    logger.info("Posted to %s: %s", platform, item.get("title", "")[:40])

            social_tools.mark_item_posted(str(item["id"]))

    if not dry_run and top_items:
        send_discord_message(f"Social poster complete: posted {len(top_items)} items to Discord, LinkedIn, Bluesky")

    log_audit_summary(auditor)
    logger.info("SocialPoster run complete")