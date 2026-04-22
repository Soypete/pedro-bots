#!/usr/bin/env python3
"""Standalone script to add feeds to socialwatch DB."""
import os
import sys
import uuid

POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
if not POSTGRES_URL:
    print("Error: POSTGRES_URL not set")
    sys.exit(1)

def add_feed(url: str, feed_type: str, name: str = None, channel_id: str = None):
    import psycopg2
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path = socialwatch")
        cur.execute(
            """
            INSERT INTO feeds (id, url, feed_type, name, channel_id, active)
            VALUES (%s, %s, %s, %s, %s, true)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (str(uuid.uuid4()), url, feed_type, name, channel_id),
        )
        result = cur.fetchone()
        if result:
            print(f"Added feed: {name or url} ({feed_type})")
        else:
            print(f"Feed already exists or added: {name or url}")
    conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add feed to socialwatch")
    parser.add_argument("--url", default="", help="RSS feed URL (not needed for YouTube)")
    parser.add_argument("--feed-type", choices=["youtube", "substack", "generic"], default="generic")
    parser.add_argument("--channel-id", help="YouTube channel ID")
    parser.add_argument("--name", help="Feed name")
    args = parser.parse_args()

    if args.feed_type == "youtube" and not args.channel_id:
        print("Error: --channel-id required for youtube feed type")
        sys.exit(1)

    add_feed(args.url, args.feed_type, args.name, args.channel_id)