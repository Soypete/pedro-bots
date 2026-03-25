#!/usr/bin/env python3
"""Check if the monitor agent successfully scraped Reddit in the last hour.
Writes a timestamped error report to temp/errors/ if no rows were found or
if an exception occurs.

Usage: op run --env-file=.env -- python scripts/check_scrape.py
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

ERRORS_DIR = Path(__file__).parent.parent / "temp" / "errors"
ERRORS_DIR.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc)
timestamp = now.strftime("%Y-%m-%d-%H")
report_path = ERRORS_DIR / f"check-{timestamp}.txt"


def write_error(message: str) -> None:
    with open(report_path, "w") as f:
        f.write(f"RedditWatch scrape check — {now.isoformat()}\n")
        f.write("-" * 60 + "\n")
        f.write(message + "\n")
    print(f"ERROR: {message}")
    print(f"Report written to {report_path}")


def get_conn():
    conn = psycopg2.connect(os.environ["POSTGRES_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path = tweetwatch")
    return conn


def main() -> None:
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM rw_classifications "
            "WHERE classified_at > now() - interval '1 hour'"
        )
        count = cur.fetchone()["cnt"]
    except Exception as e:
        write_error(f"Database connection failed: {e}")
        sys.exit(1)

    if count == 0:
        try:
            cur.execute("SELECT MAX(classified_at) AS last FROM rw_classifications")
            last = cur.fetchone()["last"]
        except Exception:
            last = None
        conn.close()

        msg = (
            f"No posts classified in the last hour.\n"
            f"Last classification: {last or 'none on record'}\n"
            f"The monitor agent may not have run or Reddit returned no results."
        )
        write_error(msg)
        sys.exit(1)
    else:
        conn.close()
        print(f"OK — {count} post(s) classified in the last hour.")
        if report_path.exists():
            report_path.unlink()


if __name__ == "__main__":
    main()
