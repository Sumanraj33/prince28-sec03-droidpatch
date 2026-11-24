# DroidPatch engineering notes

## D03 � PostgreSQL

### PostgreSQL

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

## D04 � Docker, Compose and tests

### Breaking the database on purpose

db stopped:  /health -> {"status":"ok"}
db stopped:  /ready  -> {"status":"not ready","checks":{"database":false}}
db started:  /ready  -> {"status":"ready","checks":{"database":true}}

Why should a load balancer stop sending traffic here but not restart the app?
The API is still alive (/health is ok), so restarting it will not fix a stopped database. Traffic should stop because the database is down (/ready is false), and once the database starts, /ready recovers automatically.

## D04 � Docker, Compose and tests

### The image

REPOSITORY       TAG       IMAGE ID       CREATED        SIZE
droidpatch:dev   latest    ...            ...            ~230 MB
uid=999(app) gid=999(app) groups=999(app)

- Size: ~230 MB (target: under 400 MB)
- First build: ~17s in Compose / multi-stage build. After changing one line of code: a few seconds.
- Which step said CACHED, and why? Dependency and base/user setup layers stayed cached until code or lockfile layers changed.
- Largest `docker history droidpatch:dev` layer: 109 MB for `COPY --from=builder /app/.venv /app/.venv`, which packages the production virtual environment and installed runtime dependencies.

### The stack

NAME                   IMAGE                    COMMAND                  SERVICE   CREATED          STATUS          PORTS
droidpatch-api-1       droidpatch-api           "sh -c 'exec uvicorn�"   api       10 seconds ago   Up (healthy)    0.0.0.0:8000->8000/tcp
droidpatch-db-1        pgvector/pgvector:pg17   "docker-entrypoint.s�"   db        11 seconds ago   Up (healthy)    0.0.0.0:5433->5432/tcp
droidpatch-migrate-1   droidpatch-migrate       "sh -c 'alembic upgr�"   migrate   10 seconds ago   Exited (0)
droidpatch-redis-1     redis:7-alpine           "docker-entrypoint.s�"   redis     11 seconds ago   Up (healthy)    0.0.0.0:6379->6379/tcp
records=20 inserted=20 updated=0 unchanged=0
records=20 inserted=0 updated=0 unchanged=20

- Production-image Neon check: `/ready` returned `{"status":"ready","checks":{"database":true}}`.

### Breaking the database on purpose

db stopped:  /health -> {"status":"ok",...}
db stopped:  /ready  -> {"status":"not_ready","checks":{"database":false}}
db started:  /ready  -> {"status":"ready","checks":{"database":true}}

Why should a load balancer stop sending traffic here but not restart the app?
The API process itself is still alive (/health is ok), but it cannot serve database-backed traffic until Postgres recovers. Restarting the container would not fix a stopped database and would drop in-flight traffic.

- Added `restart: true` to `api.depends_on.db`; `docker compose restart db` restarted the API (its start timestamp changed). Both services returned healthy, and `/ready` returned `{"status":"ready","checks":{"database":true}}`.

### Tests and coverage

uv run poe test              -> 26 passed in 3.63s
uv run poe test-integration  -> 7 passed in 5.38s
coverage TOTAL, unit only    -> 81%
coverage TOTAL, with integration tests -> 78% (2 logging caplog assertions in test_api.py when run after integration)

After adding a repository exposure edge-case test, 27 unit tests passed and unit coverage reached 88%. The test exercises missing/malformed patch dates and a patch level that is not later than the requested level. `poe lint`, `pre-commit run --all-files`, and the final `poe test` passed.

Two files or lines my coverage report says are never run, and whether they matter:
src/droidpatch/db/repository.py and src/droidpatch/api/routes/documents.py have uncovered error/edge branches that matter for resilience and should be covered in future tests.

## D05 ? CI/CD and going live

- Live URL: [https://droidpatch.onrender.com](https://droidpatch.onrender.com)
- CI run for pull request 1: [https://github.com/Sumanraj33/prince28-sec03-droidpatch/actions/runs/44755162413](https://github.com/Sumanraj33/prince28-sec03-droidpatch/actions/runs/44755162413)
- First deploy that ran by itself: [https://github.com/Sumanraj33/prince28-sec03-droidpatch/actions/runs/44773661245](https://github.com/Sumanraj33/prince28-sec03-droidpatch/actions/runs/44773661245)
- Merge clicked at 21:57 -> "Smoke test passed" at 21:59 -> lead time: 2 min

### Smoke test output from that CD run

```text
ok   /health -> 200, version 54e2734f129584176230c0d4fe0a73fbd5ad11fa
ok   /ready -> 200 {"status": "ready", "checks": {"database": True}}
ok   /v1/documents?limit=1 -> 200
Smoke test passed
```

### Rollback drill

- Rolled back to sha 99689bc51b4dbebfa2441ccbf6950172ff2cba38 : started 22:14, smoke passed 22:15 (1 min)
- Rolled forward to sha 54e2734f129584176230c0d4fe0a73fbd5ad11fa : 1 min
- During the rollback, the database stayed on the newer schema. Why is that safe here? Because migrations follow expand/contract backward-compatibility rules?the older app code only reads columns and tables that still exist on the newer Neon schema without breaking.

### Where my secrets live

- Neon string: GitHub Secret DATABASE_URL + Render environment. Not in Git, not in the image.
- Render deploy hook: GitHub Secret RENDER_DEPLOY_HOOK only.

### Monitoring

- UptimeRobot checks /health every 5 minutes; alerts go to my email.
- One thing that would make my live app faster on its first request: Upgrading Render from the Free instance tier (which spins down after 15 minutes of inactivity) to a paid always-on instance so there is no cold start.

## D05 ? Stretch tasks

### Human gate (required reviewer on production)

- Worth the delay when deploying irreversible schema changes, high-risk production hotfixes, or releases during peak traffic windows where human sign-off prevents bad rollouts.
- For routine low-risk changes covered by automated tests, migrations, and smoke checks, auto-deploy keeps feedback fast.

### Lead time & slowest step (DORA metric)

- Observed CD run durations on GitHub Actions: CD #3 (48s), CD #4 (55s), CD #5 (49s), and CD #6 (55s), with PR #7 merge-to-smoke lead time recorded at ~2 min.
- Slowest step: Waiting for Render to pull the new SHA image, start the container, and pass /health and /ready during the smoke test (compared to setup/migration/hook steps).

## D06 � Collecting the corpus

- Start target: 24 monthly bulletins (2 years)
- Collected today: 24 files, 98 pages, 4.6 MB (from DATASET.md)
- Doors used: URL list (scripts/fetch.py urls)

### Licence check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| android-bulletin | Android documentation content is CC BY 4.0 (code samples Apache-2.0) | Yes, with attribution and link to the source bulletin |
| pixel-bulletin | Android documentation content is CC BY 4.0 (code samples Apache-2.0) | Yes, with attribution and link to the source bulletin |

### robots.txt

- Site: https://source.android.com/robots.txt . Its robots.txt allows public documentation paths for bots without blocking our bulletin URLs.
- Was anything blocked for my bot? No (locked=0) across all 24 fetched bulletins.

### Kill and resume

- Run 1: Ran scripts/fetch.py urls --delay 3 across 24 sources (downloaded=24 skipped=0 blocked=0 failed=0, 70.9s), with interrupted runs resuming cleanly from data/manifest.jsonl and leaving zero .part files.
- Run 2: downloaded=0 skipped=24 (locked=0 failed=0, 0.2s)
- Run 3: downloaded=0 skipped=24 (locked=0 failed=0, 0.1s)

### Capacity (from docs/CAPACITY.md)

- Tokens per page, measured: 750 (73,213 estimated tokens across 98 pages / 292,853 chars)
- Full corpus: 0.37 M tokens, 1,052 chunks, embedding about Rs 6 (.06), vectors 3 MB (and 2 MB text in Postgres for 120 files)
- The number that surprised me most, and why (2 lines): Even scaled to 120 bulletins (0.37 M tokens), embedding cost (~Rs 6) and vector storage (3 MB) are tiny, while token count per page (750 via chars / 4) remains an estimate until real tokenization on Day 8.

### One thing that went wrong today, and how I fixed it

- Windows PowerShell -Encoding utf8 added a UTF-8 BOM that
uff format --check flagged, and some candidate bulletin dates returned HTTP 404; running uv run ruff format . and using published Android and Pixel bulletin URLs fixed both.

## D06 · Collecting the corpus

- Start target: 24 monthly bulletins (2 years)
- Collected today: 24 files, 98 pages, 4.6 MB (from DATASET.md)
- Doors used: URL list (scripts/fetch.py urls)

### Licence check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| android-bulletin | Android documentation content is CC BY 4.0 (code samples Apache-2.0) | Yes, with attribution and link to the source bulletin |
| pixel-bulletin | Android documentation content is CC BY 4.0 (code samples Apache-2.0) | Yes, with attribution and link to the source bulletin |

### robots.txt

- Site: https://source.android.com/robots.txt . Its robots.txt allows public documentation paths for bots without blocking our bulletin URLs.
- Was anything blocked for my bot? No (locked=0) across all 24 fetched bulletins.

### Kill and resume

- Run 1: Ran scripts/fetch.py urls --delay 3 across 24 sources (downloaded=24 skipped=0 blocked=0 failed=0, 70.9s), with interrupted runs resuming cleanly from data/manifest.jsonl and leaving zero .part files.
- Run 2: downloaded=0 skipped=24 (locked=0 failed=0, 0.2s)
- Run 3: downloaded=0 skipped=24 (locked=0 failed=0, 0.1s)

### Capacity (from docs/CAPACITY.md)

- Tokens per page, measured: 750 (73,213 estimated tokens across 98 pages / 292,853 chars)
- Full corpus: 0.37 M tokens, 1,052 chunks, embedding about Rs 6 (.06), vectors 3 MB (and 2 MB text in Postgres for 120 files)
- The number that surprised me most, and why (2 lines): Even scaled to 120 bulletins (0.37 M tokens), embedding cost (~Rs 6) and vector storage (3 MB) are tiny, while token count per page (750 via chars / 4) remains an estimate until real tokenization on Day 8.

### One thing that went wrong today, and how I fixed it

- Windows PowerShell file encoding/line endings affected
uff format, and some candidate bulletin dates returned HTTP 404; saving UTF-8 cleanly, running uv run ruff format ., and using published Android and Pixel bulletin URLs fixed both.

## D07 · Parser comparison

<!-- parsers:start -->
| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |
|---|---|---|---|---|---|---|
| 2025-04-01-5ab69331.html | trafilatura / strip tags | 5 | 13,227 chars, 14 headings, 12 tables | 17,911 chars, 0 headings, 0 tables | 0.30 s / 0.01 s | trafilatura — extracts 14 headings and 12 Markdown CVE tables; strip-tags adds ~4.7k chars of nav/footer noise with 0 structure |
| 2024-08-01-93905981.html | trafilatura / strip tags | 5 | 12,325 chars, 14 headings, 11 tables | 17,177 chars, 0 headings, 0 tables | 0.19 s / 0.01 s | trafilatura — preserves 14 section headings and 11 CVE tables cleanly; strip-tags collapses tables into flat word soup |
| 2025-05-01-3a4360d6.html | trafilatura / strip tags | 5 | 12,889 chars, 15 headings, 13 tables | 17,509 chars, 0 headings, 0 tables | 0.24 s / 0.01 s | trafilatura — keeps 15 headings and 13 patch-level tables intact while stripping site chrome (~4.6k fewer noise chars) |
| 2025-02-01-98e58d5f.html | trafilatura / strip tags | 5 | 12,802 chars, 16 headings, 14 tables | 17,520 chars, 0 headings, 0 tables | 0.20 s / 0.01 s | trafilatura — captures 16 headings and 14 CVE tables; strip-tags loses all hierarchy and table boundaries |
| 2024-11-01-efb7f064.html | trafilatura / strip tags | 5 | 12,452 chars, 15 headings, 13 tables | 17,254 chars, 0 headings, 0 tables | 0.19 s / 0.01 s | trafilatura — retains 15 headings and 13 Markdown tables; strip-tags includes ~4.8k chars of navigation/sidebar boilerplate |
| 2024-09-01-00e84ebd.html | trafilatura / strip tags | 4 | 11,664 chars, 14 headings, 12 tables | 16,562 chars, 0 headings, 0 tables | 0.23 s / 0.01 s | trafilatura — keeps 14 section headings and 12 vulnerability tables readable; strip-tags has 0 headings/tables |
| 2025-03-01-2626d319.html | trafilatura / strip tags | 4 | 11,458 chars, 12 headings, 10 tables | 16,391 chars, 0 headings, 0 tables | 0.23 s / 0.01 s | trafilatura — extracts 12 headings and 10 Markdown CVE tables; strip-tags adds ~4.9k chars of page menus |
| 2025-01-01-88834c1f.html | trafilatura / strip tags | 4 | 11,143 chars, 12 headings, 9 tables | 16,026 chars, 0 headings, 0 tables | 0.20 s / 0.00 s | trafilatura — preserves 12 headings and 9 patch tables; strip-tags outputs unstructured text with sidebar links |
| 2024-06-01-b2aad26d.html | trafilatura / strip tags | 4 | 11,486 chars, 13 headings, 11 tables | 16,281 chars, 0 headings, 0 tables | 0.16 s / 0.01 s | trafilatura — keeps 13 headings and 11 CVE tables; strip-tags dumps ~4.8k chars of non-article HTML |
| 2024-06-01-684a29db.html | trafilatura / strip tags | 3 | 6,963 chars, 8 headings, 6 tables | 12,279 chars, 0 headings, 0 tables | 0.32 s / 0.01 s | trafilatura — Pixel bulletin keeps 8 headings and 6 CVE tables; strip-tags nearly doubles chars with site navigation |
<!-- parsers:end -->

### D07 · Parsing my corpus

- Files in the manifest: 26 · parsed: 26 · failed: 0 · pages in Postgres: 86
- Parsing coverage: 100 % of files

### Failures by reason

| Reason | Files | What I did |
|---|---|---|
| none | 0 | 0 failures out of 26 files — all 26 downloaded HTML bulletins parsed cleanly into 86 pages in Postgres |

- The one I fixed: file none (0 failures out of 26 files), reason N/A, fix: verified idempotency by re-running `parse_corpus.py` (`files=26 already_parsed=26 pages=0`).

### What I saw when I read my parsed pages

- A page where the heading path is right (document, page, path): Android Security Bulletin (`2024-10-01`), page 2, `["Android and Google service mitigations", "2024-10-01 security patch level vulnerability details", "Framework"]`
- Something that came out wrong (document, page, what): Because `finish()` sets the document title from the first `#` heading in extracted Markdown, Android Security Bulletins get titled `"Android and Google service mitigations"` (and Pixel bulletins `"Announcements"`) instead of the bulletin month/title from `<title>` or the `Published ...` line.
- A table: Markdown grid or loose text? (document, page): Markdown grid (`| CVE | References | Severity | Subcomponent |` and `| CVE | References | Type | Severity | Updated AOSP versions |`) on page 2 of the Android Security Bulletins.

### My parser choice

- For PDFs I use `PyMuPDF` because it detects body font size to build heading paths and converts ruled tables into Markdown, and for HTML bulletins `trafilatura` preserves 6–14 Markdown CVE tables and 8–16 headings per file in ~0.16–0.32 s while stripping ~4.7k–5.3k menu/footer characters that `strip tags` keeps with 0 headings and 0 tables.
- A kind of document in my corpus that neither parser handles well: JavaScript-rendered pages, scanned PDFs without a text layer (`no_text_layer`), or borderless/bold-only tables that require OCR or layout-aware parsing.

### One thing that went wrong today, and how I fixed it

- A stale PowerShell session variable (`$env:DATABASE_URL` ending in `?sslmode=require`) overrode `.env` (`?ssl=require`), causing `asyncpg` to raise `TypeError: connect() got an unexpected keyword argument 'sslmode'`. Clearing it with `Remove-Item Env:DATABASE_URL` let `parse_corpus.py` read `.env` and connect to Neon cleanly.
