# Functional requirements

1. The service must expose /health and /ready endpoints so operators can check liveness and readiness.
2. The API must list documents from the loaded JSON records with a pagination limit and optional search query.
3. The service must return one document by ID and fail with a problem-details response when no record matches.
4. Invalid query parameters, such as limit=0, must return HTTP 422 with field-level validation details.
5. The application must fail fast when APP_ENV is missing or invalid.

# Non-functional requirements

1. The app must run under Python 3.12 or newer.
2. All request logs must include a request ID and be emitted as single-line JSON.
3. The project must use uv for dependency management and lock files.
4. The code base must pass Ruff and pytest checks before a merge.
5. Secret scanning and pre-commit hooks must run automatically for each commit.
