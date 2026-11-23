# Dataset: DroidPatch

Answers which Android security bulletin fixed a CVE, which patch level covers it, and what an unpatched phone is exposed to.

- **Start target:** 24 monthly bulletins (2 years)
- **Full target:** All bulletins 2015 to now (120+ bulletins, 10,000+ CVE rows)
- **Collected by:** `scripts/fetch.py` as `examate-student-bot` (https://github.com/Sumanraj33/prince28-sec03-droidpatch): robots.txt respected, at most 4 requests at once, 0.5 s between requests to one site.

## Where the documents come from

- https://source.android.com/docs/security/bulletin
- https://source.android.com/docs/security/bulletin/pixel

## Terms I follow

Android documentation content is CC BY 4.0 (code samples Apache-2.0).

- Every answer links to the original document.
- No personal data is collected.

<!-- generated:start -->
## Sources (generated 2026-11-23 10:09 UTC by scripts/dataset_report.py)

| Source | Licence / terms | Files | MB | Pages* | How | Fetched | Example URL |
|---|---|---|---|---|---|---|---|
| android-bulletin | CC BY 4.0 | 5 | 1.0 | 25 | http | 2026-11-23 | https://source.android.com/docs/security/bulletin/2025-03-01 |
| pixel-bulletin | CC BY 4.0 | 5 | 0.9 | 15 | http | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2025-03-01 |

**Total:** 10 files, 1.9 MB, 40 pages. Not downloaded: 0 blocked by robots.txt, 0 failed.

*Pages = PDF pages, plus one page per 3,000 characters of text or HTML.

## Files (first 10 of 10)

The complete list, with a sha256 fingerprint of every file, is `data/manifest.jsonl`.

| # | Title / file | Source | Pages | Fetched | URL |
|---|---|---|---|---|---|
| 1 | Android Security Bulletin - November 2024 | android-bulletin | 5 | 2026-11-23 | https://source.android.com/docs/security/bulletin/2024-11-01 |
| 2 | Android Security Bulletin - December 2024 | android-bulletin | 5 | 2026-11-23 | https://source.android.com/docs/security/bulletin/2024-12-01 |
| 3 | Android Security Bulletin - January 2025 | android-bulletin | 5 | 2026-11-23 | https://source.android.com/docs/security/bulletin/2025-01-01 |
| 4 | Android Security Bulletin - February 2025 | android-bulletin | 5 | 2026-11-23 | https://source.android.com/docs/security/bulletin/2025-02-01 |
| 5 | Android Security Bulletin - March 2025 | android-bulletin | 5 | 2026-11-23 | https://source.android.com/docs/security/bulletin/2025-03-01 |
| 6 | Pixel Update Bulletin - November 2024 | pixel-bulletin | 3 | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2024-11-01 |
| 7 | Pixel Update Bulletin - December 2024 | pixel-bulletin | 3 | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2024-12-01 |
| 8 | Pixel Update Bulletin - January 2025 | pixel-bulletin | 3 | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2025-01-01 |
| 9 | Pixel Update Bulletin - February 2025 | pixel-bulletin | 3 | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2025-02-01 |
| 10 | Pixel Update Bulletin - March 2025 | pixel-bulletin | 3 | 2026-11-23 | https://source.android.com/docs/security/bulletin/pixel/2025-03-01 |
<!-- generated:end -->

## Known gaps

- Currently collected 10 monthly bulletins (5 Android Security Bulletins and 5 Pixel Update Bulletins from Nov 2024–Mar 2025) toward the 24-bulletin start target; remaining monthly bulletins will be added to `data/sources.csv` and fetched with `scripts/fetch.py urls`.
