"""Unit tests for src/core/tools/reddit.py fetch logic.

All PRAW calls are mocked — no Reddit credentials needed.
"""
import time
from unittest.mock import MagicMock, patch


def make_fake_post(post_id: str, score: int, age_seconds: float) -> MagicMock:
    """Return a fake PRAW post object."""
    post = MagicMock()
    post.id = post_id
    post.score = score
    post.created_utc = time.time() - age_seconds
    post.title = f"Test post {post_id}"
    post.selftext = "Some body text here."
    post.author = MagicMock()
    post.author.__str__ = lambda _: "test_user"
    post.permalink = f"/r/test/comments/{post_id}/test_post"
    post.num_comments = 5
    return post


def _make_reddit_mock(posts: list) -> MagicMock:
    """Return a mock Reddit instance whose subreddit().new() yields the given posts."""
    reddit_instance = MagicMock()
    sub_mock = MagicMock()
    sub_mock.new.return_value = iter(posts)
    reddit_instance.subreddit.return_value = sub_mock
    return reddit_instance


@patch("core.tools.reddit._get_reddit")
def test_posts_within_window_are_returned(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts

    posts = [
        make_fake_post("a", score=30, age_seconds=3600),   # 1h ago — inside window
        make_fake_post("b", score=40, age_seconds=7200),   # 2h ago — inside window
    ]
    mock_get_reddit.return_value = _make_reddit_mock(posts)

    result = search_reddit_posts("LocalLLaMA", limit=20, min_upvotes=10)
    assert len(result) == 2
    assert result[0]["post_id"] == "a"
    assert result[1]["post_id"] == "b"


@patch("core.tools.reddit._get_reddit")
def test_posts_outside_window_are_excluded(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts, WINDOW_HOURS

    inside = make_fake_post("in", score=50, age_seconds=3600)       # 1h ago
    outside = make_fake_post("out", score=200, age_seconds=WINDOW_HOURS * 3600 + 1)  # just past window

    # sub.new() is newest-first; outside post comes after inside
    mock_get_reddit.return_value = _make_reddit_mock([inside, outside])

    result = search_reddit_posts("LocalLLaMA", limit=20, min_upvotes=10)
    ids = [p["post_id"] for p in result]
    assert "in" in ids
    assert "out" not in ids


@patch("core.tools.reddit._get_reddit")
def test_iteration_stops_at_cutoff(mock_get_reddit):
    """Once a post is outside the window, iteration should stop (no further posts processed)."""
    from core.tools.reddit import search_reddit_posts, WINDOW_HOURS

    old_post = make_fake_post("old", score=500, age_seconds=WINDOW_HOURS * 3600 + 60)
    newer_but_after_old = make_fake_post("never_seen", score=500, age_seconds=100)

    # If we iterate past old_post without breaking, never_seen (which comes after in the list)
    # would be returned. The break-on-cutoff means never_seen should NOT appear.
    mock_get_reddit.return_value = _make_reddit_mock([old_post, newer_but_after_old])

    result = search_reddit_posts("LocalLLaMA", limit=20, min_upvotes=10)
    ids = [p["post_id"] for p in result]
    assert "never_seen" not in ids


@patch("core.tools.reddit._get_reddit")
def test_posts_below_min_upvotes_are_excluded(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts

    low = make_fake_post("low", score=5, age_seconds=3600)
    high = make_fake_post("high", score=100, age_seconds=7200)
    mock_get_reddit.return_value = _make_reddit_mock([low, high])

    result = search_reddit_posts("LocalLLaMA", limit=20, min_upvotes=25)
    ids = [p["post_id"] for p in result]
    assert "low" not in ids
    assert "high" in ids


@patch("core.tools.reddit._get_reddit")
def test_limit_cap_respected(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts

    posts = [make_fake_post(str(i), score=100, age_seconds=i * 60) for i in range(50)]
    mock_get_reddit.return_value = _make_reddit_mock(posts)

    result = search_reddit_posts("LocalLLaMA", limit=5, min_upvotes=10)
    assert len(result) <= 5


@patch("core.tools.reddit._get_reddit")
def test_api_exception_returns_empty_list(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts

    mock_get_reddit.return_value = MagicMock()
    mock_get_reddit.return_value.subreddit.side_effect = Exception("API down")

    result = search_reddit_posts("LocalLLaMA")
    assert result == []


@patch("core.tools.reddit._get_reddit")
def test_returned_post_has_expected_fields(mock_get_reddit):
    from core.tools.reddit import search_reddit_posts

    posts = [make_fake_post("x1", score=50, age_seconds=1800)]
    mock_get_reddit.return_value = _make_reddit_mock(posts)

    result = search_reddit_posts("LocalLLaMA", limit=5, min_upvotes=10)
    assert len(result) == 1
    p = result[0]
    assert p["post_id"] == "x1"
    assert "post_url" in p
    assert "text" in p
    assert "score" in p
    assert p["score"] == 50
    assert p["topic_query"] == "LocalLLaMA"
