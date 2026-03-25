#!/usr/bin/env bash
# Run all pending migrations against Supabase.
# Usage: op run --env-file=.env -- ./scripts/migrate.sh
# Or via pixi: pixi run migrate
set -euo pipefail

MIGRATIONS_DIR="$(cd "$(dirname "$0")/../migrations" && pwd)"

DB_URL="${POSTGRES_URL}"

for file in "$MIGRATIONS_DIR"/*.sql; do
    echo "Running $(basename "$file")..."
    psql "$DB_URL" -f "$file"
    echo "  done."
done

echo "All migrations complete."
