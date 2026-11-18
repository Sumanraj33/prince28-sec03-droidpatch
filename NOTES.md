\# DroidPatch PostgreSQL Evidence



\## 1. Database migrations



\- Created `documents` and `pages` tables.

\- Added JSONB metadata support.

\- Added GIN index: `ix\_documents\_metadata\_gin`.

\- Verified Alembic upgrade and downgrade.



\## 2. Sample data loader



File: `scripts/load\_db.py`



Verified idempotency:



\- First run: 20 inserted.

\- Second run: 20 unchanged.

\- Updated record: 1 updated.



\## 3. API verification



\- All 16 API tests passed.

\- `ruff check .` passed.

\- Pre-commit hooks passed.



\## 4. EXPLAIN ANALYZE



Query:



```sql

SELECT id, title

FROM documents

WHERE metadata @> '{"bulletin\_month": "2024-05"}'::jsonb;
