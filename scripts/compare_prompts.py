"""Which prompt version is best? Run every prompts/classify_v*.md on your labelled test set.

  uv run python scripts/compare_prompts.py             all versions, results cached
  uv run python scripts/compare_prompts.py --rpm 20    faster, if your rate limit allows it
  uv run python scripts/compare_prompts.py --no-cache  ask the model again for everything

The table goes into NOTES.md. Answers are cached in eval/cache/, so after you edit one
prompt only that prompt is paid for again.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from droidpatch.config import Settings, get_settings
from droidpatch.db import database as db_database
from droidpatch.db.llm_calls import make_recorder
from droidpatch.llm.classify import LABELS, accuracy, classify, find_leaks
from droidpatch.llm.gateway import LLMUnavailable, build_gateway
from droidpatch.llm.prompts import read_prompt, versions

TESTSET = Path("eval/prompt_testset.jsonl")
CACHE = Path("eval/cache/classify.json")
NOTES = Path("NOTES.md")
START, END = "<!-- prompts:start -->", "<!-- prompts:end -->"


def _database_url(settings: Settings) -> str:
    for attr in ("database_url", "async_database_url", "db_url"):
        val = getattr(settings, attr, None)
        if val:
            return str(val)
    raise RuntimeError("No database URL found on Settings")


def make_engine(settings: Settings) -> AsyncEngine:
    if hasattr(db_database, "engine") and isinstance(db_database.engine, AsyncEngine):
        return db_database.engine
    return create_async_engine(_database_url(settings))


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    if hasattr(db_database, "SessionLocal"):
        return db_database.SessionLocal
    if hasattr(db_database, "sessionmaker"):
        return db_database.sessionmaker
    return async_sessionmaker(engine, expire_on_commit=False)


def load_testset() -> tuple[list[dict], int]:
    """Usable examples, and how many lines are still TODO."""
    examples, todo = [], 0
    for number, line in enumerate(TESTSET.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row["label"] not in LABELS:
            raise SystemExit(f"{TESTSET} line {number}: label must be one of {LABELS}")
        if "TODO" in row["question"]:
            todo += 1
        else:
            examples.append({"n": number, **row})
    return examples, todo


def write_table(rows: list[dict], total: int) -> None:
    table = [START, "", "| Prompt version | Correct | Accuracy | Invalid replies | Avg tokens in |"]
    table.append("|---|---|---|---|---|")
    for row in rows:
        table.append(
            f"| {row['version']} | {row['correct']}/{total} | {row['accuracy']:.0%} "
            f"| {row['invalid']} | {row['tokens_in']} |"
        )
    table += ["", END]
    text = NOTES.read_text(encoding="utf-8") if NOTES.exists() else "# Notes\n"
    block = "\n".join(table)
    if START in text and END in text:
        text = text[: text.index(START)] + block + text[text.index(END) + len(END) :]
    else:
        text = text.rstrip() + "\n\n## D09 · Prompt versions compared\n\n" + block + "\n"
    NOTES.write_text(text, encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    examples, todo = load_testset()
    if todo:
        print(f"note: {todo} test lines still say TODO and are skipped ({len(examples)} usable)")
    if len(examples) < 5:
        print("write at least 5 real examples in eval/prompt_testset.jsonl first")
        return 1
    engine = make_engine(settings)
    gateway = build_gateway(settings, make_recorder(make_sessionmaker(engine)))
    cache = {} if args.no_cache or not CACHE.exists() else json.loads(CACHE.read_text("utf-8"))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    rows, asked = [], 0
    try:
        for version in versions(settings.prompts_dir, "classify"):
            prompt = read_prompt(settings.prompts_dir, version)
            if "TODO" in prompt:
                print(f"skipped {version}: the file still contains TODO")
                continue
            for leak in find_leaks(prompt, [e["question"] for e in examples]):
                print(f"LEAK in {version}: a test question is inside the prompt: {leak[:60]!r}")
            results = []
            for example in examples:
                key = hashlib.sha256(f"{prompt}\n\n{example['question']}".encode()).hexdigest()
                if key not in cache:
                    got, reply = await classify(gateway, prompt, version, example["question"])
                    cache[key] = {
                        "got": got,
                        "reply": reply.text[:120],
                        "tokens_in": reply.tokens_in,
                    }
                    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), "utf-8")
                    asked += 1
                    await asyncio.sleep(60 / args.rpm)
                results.append({**example, **cache[key]})
            for miss in (r for r in results if r["got"] != r["label"]):
                print(
                    f"{version} missed line {miss['n']}: wanted {miss['label']}, "
                    f"got {miss['got']} (reply {miss['reply'][:40]!r}) {miss['question'][:60]!r}"
                )
            rows.append(
                {
                    "version": version,
                    "correct": sum(r["got"] == r["label"] for r in results),
                    "accuracy": accuracy(results),
                    "invalid": sum(r["got"] == "invalid" for r in results),
                    "tokens_in": round(sum(r["tokens_in"] for r in results) / len(results)),
                    "results": results,
                }
            )
    except LLMUnavailable as error:
        print(f"stopped: no model can answer ({str(error)[:160]})")
        print("Wait a minute and run the same command again: finished answers are cached.")
        return 1
    finally:
        await engine.dispose()
    if not rows:
        print("no prompt version could be run: check prompts/classify_v*.md")
        return 1
    write_table(rows, len(examples))
    for row in rows:
        print(f"{row['version']:<14} {row['correct']:>2}/{len(examples)}  {row['accuracy']:.0%}")
        for true_label in (*LABELS, "invalid"):
            matched = [r for r in row["results"] if r["label"] == true_label]
            if not matched:
                continue
            breakdown = Counter(r["got"] for r in matched)
            parts = ", ".join(f"{got}: {count}" for got, count in sorted(breakdown.items()))
            print(f"    {true_label} -> {parts}")
    print(f"model calls made now: {asked} (the rest came from the cache) -> table in NOTES.md")
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--rpm", type=float, default=12, help="model calls per minute (default 12)")
    parser.add_argument("--no-cache", action="store_true", help="ignore eval/cache/")
    args = parser.parse_args()
    if not TESTSET.exists():
        print(f"{TESTSET} not found")
        return 1
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
