"""Unit tests for src/core/agents/monitor.py classification and digest logic.

All LLM calls, Supabase writes, and Discord sends are mocked — no secrets needed.
"""
import json
import time
from unittest.mock import MagicMock, patch


def make_post(post_id: str = "p1", score: int = 100, age_seconds: float = 3600, subreddit: str = "LocalLLaMA") -> dict:
    return {
        "post_id": post_id,
        "text": f"Test post {post_id} title\n\nSome body text.",
        "author_handle": "test_user",
        "created_at": str(time.time() - age_seconds),
        "post_url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
        "topic_query": subreddit,
        "score": score,
        "num_comments": 10,
    }


# --- _classify_post tests ---

@patch("core.agents.monitor.get_llm")
def test_classify_valid_json(mock_get_llm):
    from core.agents.monitor import _classify_post

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "classification": "INTERESTING",
        "confidence": 0.9,
        "reason": "Relevant to LLMs",
        "summary": "New model release",
    }))
    mock_get_llm.return_value = llm

    result = _classify_post(make_post())
    assert result["classification"] == "INTERESTING"
    assert result["confidence"] == 0.9
    assert result["reason"] == "Relevant to LLMs"


@patch("core.agents.monitor.get_llm")
def test_classify_json_embedded_in_prose(mock_get_llm):
    """Regex fallback should extract JSON even when wrapped in prose."""
    from core.agents.monitor import _classify_post

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(
        content='Here is my answer: {"classification":"NOT_INTERESTING","confidence":0.1,"reason":"Off topic","summary":null} Hope that helps!'
    )
    mock_get_llm.return_value = llm

    result = _classify_post(make_post())
    assert result["classification"] == "NOT_INTERESTING"
    assert result["confidence"] == 0.1


@patch("core.agents.monitor.get_llm")
def test_classify_unparseable_returns_not_interesting(mock_get_llm):
    """Completely unparseable LLM response defaults to NOT_INTERESTING."""
    from core.agents.monitor import _classify_post

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Sorry, I cannot classify this post.")
    mock_get_llm.return_value = llm

    result = _classify_post(make_post())
    assert result["classification"] == "NOT_INTERESTING"
    assert result["confidence"] == 0.0
    assert result["reason"] == "parse error"


# --- _classify_chunk tests ---

@patch("core.agents.monitor.store_classification")
@patch("core.agents.monitor.get_llm")
def test_classify_chunk_stores_when_not_dry_run(mock_get_llm, mock_store):
    from core.agents.monitor import _classify_chunk

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "classification": "INTERESTING", "confidence": 0.8, "reason": "Good", "summary": "Test",
    }))
    mock_get_llm.return_value = llm

    posts = [make_post("p1"), make_post("p2")]
    _classify_chunk(posts, dry_run=False)

    assert mock_store.call_count == 2


@patch("core.agents.monitor.store_classification")
@patch("core.agents.monitor.get_llm")
def test_classify_chunk_skips_store_in_dry_run(mock_get_llm, mock_store):
    from core.agents.monitor import _classify_chunk

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "classification": "INTERESTING", "confidence": 0.8, "reason": "Good", "summary": "Test",
    }))
    mock_get_llm.return_value = llm

    _classify_chunk([make_post("p1")], dry_run=True)

    mock_store.assert_not_called()


# --- _split_into_time_chunks tests ---

def test_split_posts_into_buckets():
    from core.agents.monitor import _split_into_time_chunks

    posts = [
        make_post("recent", age_seconds=1800),    # 0.5h — bucket 0
        make_post("mid", age_seconds=50400),      # 14h — bucket 2 (of 4 across 168h window → 42h each)
        make_post("old", age_seconds=150000),     # ~41.7h — bucket 0 (within first 42h bucket)
    ]
    chunks = _split_into_time_chunks(posts, 4)
    assert len(chunks) == 4
    # All posts should be distributed across the buckets (total count preserved)
    total = sum(len(c) for c in chunks)
    assert total == 3


def test_split_empty_posts():
    from core.agents.monitor import _split_into_time_chunks

    chunks = _split_into_time_chunks([], 4)
    assert chunks == [[], [], [], []]


# --- _format_digest tests ---

def test_format_digest_sorts_by_confidence():
    from core.agents.monitor import _format_digest

    items = [
        (make_post("low"), {"classification": "INTERESTING", "confidence": 0.5, "summary": "Low", "reason": "meh"}),
        (make_post("high"), {"classification": "INTERESTING", "confidence": 0.95, "summary": "High", "reason": "great"}),
    ]
    msg = _format_digest(items, total_fetched=10)
    # High confidence post should appear before low
    assert msg.index("high") < msg.index("low")


def test_format_digest_caps_at_max_posts():
    from core.agents.monitor import _format_digest, _MAX_DIGEST_POSTS

    items = [
        (make_post(str(i)), {"classification": "INTERESTING", "confidence": 0.8, "summary": f"Summary {i}", "reason": "ok"})
        for i in range(_MAX_DIGEST_POSTS + 5)
    ]
    msg = _format_digest(items, total_fetched=100)
    # Count occurrences of "reddit.com" as a proxy for post count
    assert msg.count("reddit.com") <= _MAX_DIGEST_POSTS


def test_format_digest_truncated_to_max_chars():
    from core.agents.monitor import _format_digest, _MAX_DIGEST_CHARS

    items = [
        (make_post(str(i)), {"classification": "INTERESTING", "confidence": 0.9, "summary": "x" * 200, "reason": "ok"})
        for i in range(20)
    ]
    msg = _format_digest(items, total_fetched=20)
    assert len(msg) <= _MAX_DIGEST_CHARS


# --- run_monitor dry_run tests ---

@patch("core.agents.monitor.send_discord_message")
@patch("core.agents.monitor.store_classification")
@patch("core.agents.monitor.get_seen_post_ids", return_value=set())
@patch("core.agents.monitor.load_active_topics", return_value=["LocalLLaMA"])
@patch("core.agents.monitor.search_reddit_posts")
@patch("core.agents.monitor.get_llm")
@patch("core.agents.monitor.build_middleware")
def test_dry_run_does_not_send_discord(
    mock_middleware, mock_get_llm, mock_fetch, _mock_topics, _mock_seen,
    mock_store, mock_discord
):
    from core.agents.monitor import run_monitor

    mock_middleware.return_value = (MagicMock(), MagicMock())
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "classification": "INTERESTING", "confidence": 0.9, "reason": "Good", "summary": "Test post",
    }))
    mock_get_llm.return_value = llm
    mock_fetch.return_value = [make_post("p1", score=100)]

    run_monitor(dry_run=True)

    mock_discord.assert_not_called()
    mock_store.assert_not_called()


@patch("core.agents.monitor.send_discord_message")
@patch("core.agents.monitor.store_classification")
@patch("core.agents.monitor.get_seen_post_ids", return_value=set())
@patch("core.agents.monitor.load_active_topics", return_value=["LocalLLaMA"])
@patch("core.agents.monitor.search_reddit_posts")
@patch("core.agents.monitor.get_llm")
@patch("core.agents.monitor.build_middleware")
def test_non_dry_run_sends_discord(
    mock_middleware, mock_get_llm, mock_fetch, _mock_topics, _mock_seen,
    mock_store, mock_discord
):
    from core.agents.monitor import run_monitor

    mock_middleware.return_value = (MagicMock(), MagicMock())
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "classification": "INTERESTING", "confidence": 0.9, "reason": "Good", "summary": "Test post",
    }))
    mock_get_llm.return_value = llm
    mock_fetch.return_value = [make_post("p1", score=100)]
    mock_discord.return_value = True

    run_monitor(dry_run=False)

    mock_discord.assert_called_once()
    mock_store.assert_called_once()
