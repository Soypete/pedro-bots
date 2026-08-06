#!/usr/bin/env bash
# Run all pending migrations against Postgres.
# Usage: op run --env-file=.env -- ./scripts/migrate.sh
# Or via pixi: pixi run migrate
set -euo pipefail

MIGRATIONS_DIR="$(cd "$(dirname "$0")/../migrations" && pwd)"

MIGRATIONS_DIR="$MIGRATIONS_DIR" python3 << 'PYEOF'
import os
import glob
import sys

db_url = os.environ.get("POSTGRES_URL")
if not db_url:
    raise ValueError("POSTGRES_URL not set")

migrations_dir = os.environ["MIGRATIONS_DIR"]

import psycopg2

conn = psycopg2.connect(db_url)
conn.autocommit = True

# Applied migrations are recorded here so each one runs exactly once. Without
# this every run replayed 001 onward, and the non-idempotent ones (005's bare
# ALTER TABLE ... RENAME) aborted the run before later migrations were reached.
with conn.cursor() as cur:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename    TEXT PRIMARY KEY,
            applied_at  TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    cur.execute("SELECT filename FROM schema_migrations")
    applied = {row[0] for row in cur.fetchall()}

# redditwatch.sql is the legacy standalone schema. It targets a `redditwatch`
# schema that nothing uses -- the live tables are in `public` -- and it sorts
# after the numbered files, so running it would create a second, shadow copy of
# every table. Skipped deliberately; the numbered migrations are the source of
# truth.
paths = sorted(
    p for p in glob.glob(os.path.join(migrations_dir, "*.sql"))
    if os.path.basename(p) != "redditwatch.sql"
)

pending = [p for p in paths if os.path.basename(p) not in applied]

if not pending:
    print(f"Nothing to do; {len(applied)} migration(s) already applied.")
    sys.exit(0)

for path in pending:
    name = os.path.basename(path)
    print(f"Running {name}...")
    with open(path) as fh:
        sql = fh.read()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (name,)
            )
    except Exception as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        raise
    print("  done.")

print(f"Applied {len(pending)} migration(s).")
PYEOF
