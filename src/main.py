import argparse
import logging
import os
import sys

# Ensure src/ is on the path when invoked as a module
sys.path.insert(0, os.path.dirname(__file__))

from core.agents.monitor import run_monitor
from core.agents.suggestion import run_suggestion
from core.agents.social_poster import run_social_poster
from core.tools.social_tools import add_content_url, add_feed, list_pending

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Pedro Bots CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    parser_agent = subparsers.add_parser("agent", help="Run an agent")
    parser_agent.add_argument(
        "--agent",
        choices=["monitor", "suggest", "social-poster"],
        required=True,
        help="Which agent to run",
    )
    parser_agent.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Fetch and classify but print to stdout instead of posting",
    )

    parser_url = subparsers.add_parser("add-url", help="Add a URL to track")
    parser_url.add_argument("--url", required=True, help="URL to add")
    parser_url.add_argument("--title", help="Optional title for the URL")

    parser_feed = subparsers.add_parser("add-feed", help="Add an RSS feed to track")
    parser_feed.add_argument("--feed-url", help="RSS feed URL (not needed for YouTube channel)")
    parser_feed.add_argument(
        "--feed-type", choices=["youtube", "substack", "generic"], default="generic", help="Feed type"
    )
    parser_feed.add_argument("--channel-id", help="YouTube channel ID (for youtube feed type)")
    parser_feed.add_argument("--name", help="Feed name")

    subparsers.add_parser("list-pending", help="List pending content items")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "agent":
        if args.agent == "monitor":
            run_monitor(dry_run=args.dry_run)
        elif args.agent == "suggest":
            run_suggestion()
        elif args.agent == "social-poster":
            run_social_poster(dry_run=args.dry_run)
    elif args.command == "add-url":
        add_content_url(args.url, args.title)
    elif args.command == "add-feed":
        add_feed(args.feed_url, args.feed_type, args.name, args.channel_id)
    elif args.command == "list-pending":
        list_pending()


if __name__ == "__main__":
    cli()
