"""
Export tw_classifications as a JSONL fine-tuning dataset.

Each line is a ChatML instruction triple:
  {"system": <classify_prompt>, "user": <post_text>, "assistant": <json_label>}

Usage:
  python scripts/export_training_data.py
  python scripts/export_training_data.py --confidence 0.9 --output my_dataset.jsonl
"""

import argparse
import json
import os
import sys

import psycopg2
import psycopg2.extras

# Allow running from repo root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

CLASSIFY_SYSTEM_PROMPT = (
    "You are a tech Reddit curator for a developer, AI researcher, and content creator. "
    "Your job is to decide if a post is worth surfacing given these interests: "
    "AI agents, LLMs, local inference, Kubernetes, Go, Python, cloud infrastructure, "
    "VC funding for startups, physics, and open-source tooling. "
    "For each post, respond with JSON only: "
    '{"classification": "INTERESTING" | "NOT_INTERESTING", "confidence": 0.0-1.0, '
    '"reason": "one sentence explanation", '
    '"summary": "one sentence post summary (INTERESTING only, else null)"}'
)


def export(confidence_threshold: float, output_path: str) -> None:
    conn = psycopg2.connect(os.environ["POSTGRES_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET search_path = tweetwatch")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT tweet_id, author_handle, topic_query, raw_tweet,
                   classification, confidence, reason, summary
            FROM tw_classifications
            WHERE confidence >= %s
            ORDER BY classified_at DESC
            """,
            (confidence_threshold,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    if not rows:
        print(f"No classifications found with confidence >= {confidence_threshold}")
        return

    with open(output_path, "w") as f:
        for row in rows:
            post_text = ""
            if row.get("raw_post") and isinstance(row["raw_post"], dict):
                post_text = row["raw_post"].get("text", "")

            assistant_payload = json.dumps(
                {
                    "classification": row["classification"],
                    "confidence": row["confidence"],
                    "reason": row["reason"],
                    "summary": row["summary"],
                }
            )

            example = {
                "system": CLASSIFY_SYSTEM_PROMPT,
                "user": post_text,
                "assistant": assistant_payload,
            }
            f.write(json.dumps(example) + "\n")

    print(f"Exported {len(rows)} examples to {output_path}")
    interesting = sum(1 for r in rows if r["classification"] == "INTERESTING")
    print(f"  INTERESTING: {interesting}  NOT_INTERESTING: {len(rows) - interesting}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export RedditWatch classifications as JSONL for fine-tuning")
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.8,
        help="Minimum confidence score to include (default: 0.8)",
    )
    parser.add_argument(
        "--output",
        default="training_data.jsonl",
        help="Output file path (default: training_data.jsonl)",
    )
    args = parser.parse_args()
    export(args.confidence, args.output)


if __name__ == "__main__":
    main()
