"""Download the latest Thai Government Lottery results and rewrite data.json.

Primary source: huayreview/thai-lottery-results. Fallback: huaybase/thai-lottery-results.
Draws already in data.json are kept, so a source that goes missing never shrinks the history.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data.json"
PRIMARY = "https://raw.githubusercontent.com/huayreview/thai-lottery-results/HEAD/thai-lottery-results.csv"
FALLBACK = "https://raw.githubusercontent.com/huaybase/thai-lottery-results/HEAD/draws.csv"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lotto-stats-updater"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


def nums(s, size):
    return [x for x in re.split(r"[;\s]+", s or "") if re.fullmatch(r"\d{%d}" % size, x)]


def from_primary(rows):
    for r in rows:
        yield r["draw_date"], r["first_prize"], nums(r["front_three_digits"], 3), nums(r["last_three_digits"], 3), r["last_two_digits"]


def from_fallback(rows):
    for r in rows:
        yield r["date"], r["first"], nums(r["front3"], 3), nums(r["back3"], 3), r["back2"]


def valid(d, first, f3, b3, b2):
    return (re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") and re.fullmatch(r"\d{6}", first or "")
            and b3 and re.fullmatch(r"\d{2}", b2 or ""))


def main():
    old = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"draws": []}
    draws = {r[0]: r for r in old["draws"]}
    before = len(draws)

    got = False
    for url, parse in ((PRIMARY, from_primary), (FALLBACK, from_fallback)):
        try:
            rows = fetch(url)
        except Exception as e:  # network or source problem: try the next source
            print(f"skip {url}: {e}", file=sys.stderr)
            continue
        for d, first, f3, b3, b2 in parse(rows):
            if valid(d, first, f3, b3, b2) and d not in draws:
                draws[d] = [d, first, " ".join(f3), " ".join(b3), b2]
        got = True
    if not got:
        sys.exit("no source could be downloaded")

    added = len(draws) - before
    print(f"draws: {len(draws)} (+{added})")
    if added == 0 and DATA.exists():
        return
    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": ["huayreview/thai-lottery-results", "huaybase/thai-lottery-results"],
        "draws": [draws[k] for k in sorted(draws)],
    }
    DATA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
