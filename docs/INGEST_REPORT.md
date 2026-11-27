# Ingestion report

<!-- generated:start -->
_Generated 27 Nov 2026 23:34 from the database._

| What | Count |
|---|---|
| Documents in the database | 23 |
| Pages | 90 |
| Tokens of text (characters ÷ 4) | 57,535 |
| Files the parser gave up on | 0 |
| Documents with an extracted record | 4 |
| Documents whose extraction failed | 0 |

| Queue | Count |
|---|---|
| Ingest jobs started | 6 |
| Items finished (done or skipped) | 25 |
| Items that needed more than one try | 26 |
| Items in the dead-letter list | 17 |

Model calls for extraction: 282 · tokens in 266,898 · tokens out 135,293 · cost at list price Rs 5.53

Last job `ab05f0a5a51a46bf99f6d339bbac8b19`: 20 requested, 0 ok, 0 failed, 1.0 minutes.

Dead-letter list by stage: gave up after 3 tries 17
<!-- generated:end -->

## What I learnt

Queueing ingestion lets POST /v1/ingest return 202 immediately while the worker runs in the background.

Checking hashes and existing records in Postgres keeps retries and worker restarts from creating duplicate documents.

Pacing model calls and tracking dead-letter failures prevents rate limits from silently dropping items.

- Storing job and per-item state (`queued`, `running`, `done`, `skipped`, `failed`, `attempts`) in Postgres while using Redis (`_job_id=f"ingest:{item_id}"`) for queuing kept items from being lost or duplicated across crashes and retries.
- Content-hash idempotency (`sha256` / `document_id`) and separating permanent errors (`Permanent` / dead-letter) from retryable failures (`Retry`) prevented wasted work when Gemini or Groq hit `429` limits and opened circuits.
- Running the embedded worker (`WORKER_IN_API=true`) on Render with internal `REDIS_URL` and `ADMIN_TOKEN` wired ingestion cleanly, while `scripts/ingest_report.py` generated live counts from Postgres.
