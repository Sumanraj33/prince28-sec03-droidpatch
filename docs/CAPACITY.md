# Capacity plan: DroidPatch

Full corpus target: All bulletins 2015 to now (120+ bulletins, 10,000+ CVE rows)

<!-- generated:start -->
## Measured on my start corpus (2026-11-23 15:51 UTC)

| What | Value |
|---|---|
| Files | 26 |
| Size on disk | 5.0 MB |
| Pages (PDF pages + 1 per 3,000 characters of text/HTML) | 108 |
| Characters of text | 322,594 |
| Estimated tokens (characters / 4) | 80,648 |
| Tokens per page | 750 |
| PDFs with almost no text (scanned? OCR is Day 7) | 0 |
| Files not measured (zip, xlsx, unreadable) | 0 |

## Estimate for the full corpus (target: 120 files)

| What | How | Value |
|---|---|---|
| Scale factor | target / measured | x 4.6 |
| Tokens | measured tokens x scale | 0.37 M |
| Raw files | measured MB x scale | 23 MB |
| Chunks | tokens / 400 x 1.15 overlap | 1,070 |
| Embedding cost, one time | tokens x 1.15 x $0.15 per 1M | $0.06 = Rs 6 |
| Vector storage | chunks x 768 numbers x 4 bytes | 3 MB |
| Text in Postgres | characters x scale x 1.2 | 2 MB |

Assumptions: 4 characters per token, 400-token chunks, 768-dimension embeddings at $0.15 per 1M tokens, Rs 95 per US dollar.
<!-- generated:end -->

## What I conclude

1. Is embedding cost a problem for this product? No — one-time embedding cost for 120 bulletins is small and fits comfortably within free/low-cost tiers.
2. Do the vectors and text fit in my free Postgres? Yes — vector and text storage for 120 bulletins is modest and fits inside free-tier PostgreSQL limits.
3. Which number above am I least sure about, and how will I measure it better? Token count per page (`chars / 4`) is a rough heuristic; on Day 8 I will count real tokenizer tokens on parsed bulletin text.
4. What changes if the corpus grows 10 times? Vector storage, chunk count, and one-time embedding cost scale linearly by 10x, requiring batched ingestion and storage monitoring.
