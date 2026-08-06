import logging
import random
import re
import time
from typing import Annotated, Literal

import httpx
from langchain.tools import tool

from core.config import get_secret

logger = logging.getLogger(__name__)

_DDG_TIMEOUT = 15.0
_ddg_last_request = 0.0
_DDG_MIN_DELAY = 2.0  # seconds between requests


def _parse_ddg_results(html: str) -> list[dict]:
    """Parse DuckDuckGo search results from HTML."""
    results = []

    result_blocks = re.findall(
        r'<a rel="nofollow" class="result__a"[^>]*href="([^"]+)"[^>]*>(.+?)</a>.*?'
        r'<a class="result__snippet"[^>]*>(.+?)</a>',
        html,
        re.DOTALL,
    )

    for url, title, snippet in result_blocks[:10]:
        title_clean = re.sub(r"<[^>]+>", "", title).strip()
        snippet_clean = re.sub(r"<[^>]+>", "", snippet).strip()
        results.append(
            {
                "url": url,
                "title": title_clean,
                "snippet": snippet_clean,
            }
        )

    if not results:
        alt_pattern = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
            html,
        )
        for url, title in alt_pattern[:10]:
            results.append(
                {
                    "url": url,
                    "title": title.strip(),
                    "snippet": "",
                }
            )

    return results


@tool
def duckduckgo_search(
    query: str,
    max_results: Annotated[int, lambda x: min(max(x, 1), 10)] = 5,
) -> str:
    """Search the web using DuckDuckGo.

    Use this to find Call For Papers, conference announcements, and speaking
    opportunities for tech conferences and meetups.

    Args:
        query: Search query (e.g., "Call For Papers AI agents conference 2026")
        max_results: Maximum number of results (default: 5, max: 10)

    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    global _ddg_last_request

    # Rate limiting: ensure minimum delay between requests
    elapsed = time.time() - _ddg_last_request
    if elapsed < _DDG_MIN_DELAY:
        sleep_time = _DDG_MIN_DELAY - elapsed + random.uniform(0.5, 1.5)
        logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)

    logger.info(f"DuckDuckGo search: {query}")

    encoded_query = query.replace(" ", "+")
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    # Rotate user agents to avoid blocking
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        with httpx.Client(timeout=_DDG_TIMEOUT) as client:
            response = client.get(url, headers=headers)
            _ddg_last_request = time.time()
            response.raise_for_status()

        results = _parse_ddg_results(response.text)

        if not results:
            return f"No results found for: {query}"

        output = [f"Found {len(results)} result(s) for '{query}':\n"]
        for i, r in enumerate(results, 1):
            output.append(f"## {i}. {r['title']}")
            output.append(f"**URL:** {r['url']}")
            if r["snippet"]:
                output.append(f"**Summary:** {r['snippet']}")
            output.append("")

        return "\n".join(output)

    except httpx.TimeoutException:
        return f"Search timeout for: {query}"
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in DuckDuckGo search: {e}")
        return f"Search error for {query}: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in DuckDuckGo search: {e}")
        return f"Search failed for {query}: {str(e)}"


_fetch_last_request = 0.0
_FETCH_MIN_DELAY = 1.5


def fetch_webpage_content(url: str, timeout: float = 15.0) -> str:
    """Fetch a webpage and convert HTML to markdown."""
    global _fetch_last_request

    # Rate limiting
    elapsed = time.time() - _fetch_last_request
    if elapsed < _FETCH_MIN_DELAY:
        time.sleep(_FETCH_MIN_DELAY - elapsed)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            _fetch_last_request = time.time()
            response.raise_for_status()

        html = response.text
        text = _strip_html(html)
        return text[:8000]

    except Exception as e:
        return f"Error fetching {url}: {e!s}"


def _strip_html(html: str) -> str:
    """Remove HTML tags and clean up text."""
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(
        r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = text.strip()

    return text


@tool
def fetch_cfp_page(url: str) -> str:
    """Fetch a webpage to extract CFP details.

    Use this to get more details about a specific conference or meetup page
    to extract CFP deadlines, dates, and submission information.

    Args:
        url: The URL to fetch

    Returns:
        Extracted text content from the page
    """
    logger.info(f"Fetching CFP page: {url}")

    content = fetch_webpage_content(url)

    if content.startswith("Error"):
        return content

    return f"Content from {url}:\n\n{content}"
