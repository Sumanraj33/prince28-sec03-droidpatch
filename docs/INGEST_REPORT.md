# Ingestion report

<!-- generated:start -->
_Generated 27 Nov 2026 21:45 from the database._

| What | Count |
|---|---|
| Documents in the database | 6 |
| Pages | 24 |
| Tokens of text (characters ÷ 4) | 16,341 |
| Files the parser gave up on | 0 |
| Documents with an extracted record | 1 |
| Documents whose extraction failed | 0 |

| Queue | Count |
|---|---|
| Ingest jobs started | 3 |
| Items finished (done or skipped) | 21 |
| Items that needed more than one try | 19 |
| Items in the dead-letter list | 11 |

Model calls for extraction: 237 · tokens in 243,395 · tokens out 121,949 · cost at list price Rs 4.98

Last job `a140158a5e6d4b4ab921f8f8817687a5`: 6 requested, 1 ok, 5 failed, 2.6 minutes.

Dead-letter list by stage: gave up after 3 tries 11
<!-- generated:end -->

## What I learnt

Queueing ingestion lets POST /v1/ingest return 202 immediately while the worker runs in the background.

Checking hashes and existing records in Postgres keeps retries and worker restarts from creating duplicate documents.

Pacing model calls and tracking dead-letter failures prevents rate limits from silently dropping items.
