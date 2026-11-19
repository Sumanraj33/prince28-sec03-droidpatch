# DroidPatch engineering notes

## PostgreSQL

Migrations 1 and 2 create `documents` and `pages`, store additional fields in
JSONB, and add the `ix_documents_metadata_gin` index. Migration 3 adds nullable
`documents.bulletin_month` (`VARCHAR(7)`), backfills it from
`metadata ->> 'bulletin_month'`, and adds the B-tree index
`ix_documents_bulletin_month`. The original migrations and JSONB data are
preserved.

Apply migrations to the intended database explicitly:

```powershell
uv run alembic upgrade head
```

The migration history and current revision were verified. Migration 3 was
also tested by downgrading one revision and upgrading back to head.

## Loader and pruning

### Idempotency verification

The loader supports these expected scenarios:

1. First load: 20 inserted, 0 updated, 0 unchanged.
2. Second load: 0 inserted, 0 updated, 20 unchanged.
3. After modifying one source record: 0 inserted, 1 updated, 19 unchanged.

The following second-load result was verified against the configured database
on 2026-11-18:

```text
records=20 inserted=0 updated=0 unchanged=20 deleted=0
```

The loader reports inserted, updated, and unchanged counts, with `deleted=N`
added to the output. By default it never deletes documents. `--prune` opts in
to deleting only IDs absent from `data/sample_records.json`.

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
base-pool slots. In this run one connection remained idle in the pool and
none were checked out after the requests. Counts vary with database
availability and prior use.

## GIN index EXPLAIN evidence

Ran:

```powershell
uv run python scripts/explain.py bulletin_month 2024-05
```

The normal query plan used a sequential scan because the sample table
contains only 20 records.

With sequential scans disabled, PostgreSQL used:

- Bitmap Heap Scan
- Bitmap Index Scan
- Index: `ix_documents_metadata_gin`

The index condition was:

```sql
metadata @> '{"bulletin_month": "2024-05"}'::jsonb
```

This confirms that the GIN index is available and can be used for JSONB
containment queries. The forced-index plan is verification, not proof that
the index is faster for this small dataset.

## Additional loader verification (2026-11-19)

The loader was tested against the configured database:

- Second load without changes:
  `records=20 inserted=0 updated=0 unchanged=20 deleted=0`
- After changing record `001` severity from `High` to `Critical`:
  `records=20 inserted=0 updated=1 unchanged=19 deleted=0`
- After restoring the JSON file and syncing the database:
  `records=20 inserted=0 updated=1 unchanged=19 deleted=0`
- Subsequent load without changes:
  `records=20 inserted=0 updated=0 unchanged=20 deleted=0`

The JSON file was restored and verified to contain 20 records, with the
first record severity set to `High`.

The initial insertion scenario was not separately tested against the
configured database because it already contained the 20 sample records.
The prune command was not run.
