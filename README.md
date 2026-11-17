# DroidPatch

Answers which Android security bulletin fixed a CVE, which patch level covers it, and what an unpatched phone is exposed to.

## Status

Day 1 foundation (FastAPI skeleton, quality gates). Live URL from Day 5.

## Who it's for

Mobile device management admin at a Chennai logistics company that gives 500 Android phones from four brands to delivery staff.

## The problem

Android security bulletins are published monthly and split into patch levels such as 2024-05-01 and 2024-05-05. A fleet admin needs a reliable way to compare a device's current patch level against a particular CVE and judge whether the phone is exposed. Because vendors ship updates on different schedules, the risk varies by brand, component, and bulletin date, which makes manual checking slow and error-prone.

## Data sources

All Android Security Bulletins since 2015, Pixel update bulletins and the Android security documentation pages.

- https://source.android.com/docs/security/bulletin
- https://source.android.com/docs/security/bulletin/pixel
- Terms: Android documentation content is CC BY 4.0 (code samples Apache-2.0).

## Hardest problem (my interview story)

Bulletins are mostly CVE tables. Chunking must keep every table row with its header and patch level, and 'exposed or not' needs a date comparison of patch levels in code (2024-05-01 vs 2024-05-05), not LLM guessing.

## Signature feature

Patch-level time machine: pick a device patch level and see every Critical CVE fixed after it, grouped by component.

## Target metric

CVE-to-patch-level lookup correct for 95%+ of 60 test CVEs; exposure answers correct for 90%+ of 30 device scenarios.

## Run it locally

```bash
uv sync
cp .env.example .env   # Windows: copy .env.example .env
uv run uvicorn droidpatch.api.main:create_app --factory --reload
```

Then open http://localhost:8000/docs

## Checks

```bash
uv run pytest
uv run ruff check .
```
