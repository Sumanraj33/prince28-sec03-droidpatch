# Functional requirements

1. `GET /health` must return HTTP 200; `GET /ready` must return HTTP 200 when records load and HTTP 503 otherwise.
2. `GET /v1/documents` must list loaded records, support case-insensitive `q` search, and accept a `limit` from 1 to 100.
3. `GET /v1/documents/{id}` must return the matching record; an unknown ID must return HTTP 404 as `application/problem+json`.
4. Invalid limits, including 0 and 101, must return HTTP 422 with at least one field-level validation error.
5. `APP_ENV` must accept only `local`, `ci`, or `production`; a missing or invalid value must prevent settings creation.
6. `GET /v1/exposure?patch_level=YYYY-MM-DD` must list Critical CVEs fixed after the supplied patch level, grouped by component; equal or earlier patch levels are not exposed.

# Non-functional requirements

1. The app must run on Python 3.12 or newer.
2. 100% of successful and handled-error HTTP responses must include `X-Request-ID`; each request log must be one JSON line containing `request_id`.
3. Runtime and development dependencies must be managed by uv and pinned in the committed `uv.lock`.
4. Before merge, all API tests must pass and `ruff check .` must report 0 errors.
5. All 9 configured pre-commit hooks, including secret scanning, must run automatically on each commit and pass.
