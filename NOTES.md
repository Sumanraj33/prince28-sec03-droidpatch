# DroidPatch engineering notes

## PostgreSQL

Migrations 1 and 2 create `documents` and `pages`, store additional fields in
JSONB, and add the `ix_documents_metadata_gin` index. Migration 3 adds nullable
`documents.bulletin_month` (`VARCHAR(7)`), backfills it from
`metadata ->> 'bulletin_month'`, and adds the B-tree index
`ix_documents_bulletin_month`. The original migrations and JSONB data are
preserved.

Review migration 3, then apply it to the intended database explicitly:

```powershell
uv run alembic upgrade head
```

No migrations were run against a database during implementation.

## Loader and pruning

The loader remains idempotent: inserted, updated, and unchanged counts are
reported as before, with `deleted=N` added to the output. By default it never
deletes documents. `--prune` opts in to deleting only IDs absent from
`data/sample_records.json`.

```powershell
uv run python scripts/load_db.py
uv run python scripts/load_db.py --prune
```

Review both the JSON file and target database before running with `--prune`.
The prune command was not run against a database during implementation.

## API sorting

`GET /v1/documents?sort=title` sorts ascending and
`GET /v1/documents?sort=-published_on` sorts descending. Only `title` and
`published_on` are approved sort fields; other values return HTTP 400.

## Connection pool

The application logs `engine.pool.status()` on startup. To run 50 read-only
readiness checks (`SELECT 1`) and print pool status before and after, use a
configured database and run:

```powershell
uv run python scripts/measure_pool.py
```

The script uses HTTPX with an in-process ASGI transport, keeping the HTTP
requests and measured engine pool in the same process. A local run on
2026-11-18 produced:

```text
pool_before=Pool size: 5  Connections in pool: 0 Current Overflow: -5 Current Checked out connections: 0
requests=50
pool_after=Pool size: 5  Connections in pool: 1 Current Overflow: -4 Current Checked out connections: 0
```

The 50 requests were read-only `/ready` checks (`SELECT 1`); no document data
was changed.

The configured pool has a base size of 5 and allows up to 2 overflow
connections. `Pool size` is the base capacity; `Connections in pool` counts
idle pooled connections; `Current Checked out connections` should return to 0
after the sequential requests finish. `Current Overflow` is the number of
connections above the base size, so a negative number means there are unused
base-pool slots (for example, -4 means one connection occupies a five-slot
pool). In this run one connection remained idle in the pool and none were
checked out after the requests. Counts vary with database availability and
prior use.
