import argparse
import logging
import os
import sys

# Ensure src/ is on the path when invoked as a module
sys.path.insert(0, os.path.dirname(__file__))

from core.agents.monitor import run_monitor
from core.agents.suggestion import run_suggestion

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def cli() -> None:
    parser = argparse.ArgumentParser(description="RedditWatch agent runner")
    parser.add_argument(
        "--agent",
        choices=["monitor", "suggest"],
        required=True,
        help="Which agent to run: 'monitor' (Reddit digest) or 'suggest' (weekly suggestions)",
    )
    args = parser.parse_args()

    if args.agent == "monitor":
        run_monitor()
    else:
        run_suggestion()


if __name__ == "__main__":
    cli()
