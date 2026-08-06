#!/usr/bin/env bash
# Run all pending migrations against Supabase.
# Usage: op run --env-file=.env -- ./scripts/migrate.sh
# Or via pixi: pixi run migrate
set -euo pipefail

MIGRATIONS_DIR="$(cd "$(dirname "$0")/../migrations" && pwd)"

python3 << 'PYEOF'
import os
import glob

db_url = os.environ.get("POSTGRES_URL")
if not db_url:
    raise ValueError("POSTGRES_URL not set")

import psycopg2
conn = psycopg2.connect(db_url)
conn.autocommit = True

# Create search_path if needed
with conn.cursor() as cur:
    cur.execute("CREATE SCHEMA IF NOT EXISTS redditwatch")

# Run migrations in order
migrations = sorted(glob.glob("migrations/*.sql"))
for f in migrations:
    print(f"Running {f}...")
    with open(f) as sql:
        with conn.cursor() as cur:
            cur.execute(sql.read())
    print(f"  done.")

print("All migrations complete.")
PYEOF
