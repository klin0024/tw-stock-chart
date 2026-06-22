#!/usr/bin/env python3
"""t86_ensure.py — 檢查 T86 快取，缺漏才下載。

用法：
  echo '["2026-01-02","2026-01-05",...]' | python t86_ensure.py <stock_no> [--cache-dir DIR]

從 stdin 讀取 YYYY-MM-DD 日期 JSON 陣列，
掃描快取目錄找出「不存在」或「SKIP（可能是限流誤標）」的日期，
只對這些日期重打 TWSE T86 API；已有 OK 快取的日期直接跳過。

結束時印出摘要，exit code 0 = 全部 OK，1 = 仍有缺漏。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


API_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_t86(date_yyyymmdd: str) -> dict:
    url = f"{API_URL}?date={date_yyyymmdd}&selectType=ALLBUT0999&response=json"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Check T86 cache, fetch only missing dates")
    p.add_argument("stock_no", help="股票代號，e.g. 2881")
    p.add_argument("--cache-dir", default="twse_t86_data", help="快取目錄（預設 twse_t86_data）")
    p.add_argument("--delay", type=float, default=0.4, help="每次請求間隔秒（預設 0.4）")
    args = p.parse_args()

    stock = args.stock_no.strip()
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    dates: list[str] = json.loads(sys.stdin.read())

    # ── 1. 掃描快取，找出需補抓的日期 ──────────────────────────────
    need_fetch: list[str] = []
    ok_count = 0

    for d in dates:
        fname = cache / (d.replace("-", "") + ".json")
        if not fname.exists():
            need_fetch.append(d)
            continue
        try:
            payload = json.loads(fname.read_text(encoding="utf-8"))
        except Exception:
            need_fetch.append(d)
            continue

        stat = payload.get("stat")
        if stat == "SKIP":
            need_fetch.append(d)        # SKIP 可能是限流誤標，重打確認
        elif stat == "OK":
            row = next((r for r in payload.get("data", []) if r[0].strip() == stock), None)
            if row:
                ok_count += 1
            else:
                need_fetch.append(d)    # 有資料但找不到個股列
        else:
            need_fetch.append(d)

    print(f"快取 OK：{ok_count}/{len(dates)}　需補抓：{len(need_fetch)}")

    # ── 2. 補抓缺漏 ────────────────────────────────────────────────
    if not need_fetch:
        print("快取完整，無需下載。")
        sys.exit(0)

    fetched_ok = 0
    for i, d in enumerate(need_fetch):
        date_fmt = d.replace("-", "")
        try:
            data = fetch_t86(date_fmt)
        except Exception as e:
            print(f"  [{i+1}/{len(need_fetch)}] {d}: ERROR {e}", file=sys.stderr)
            if i < len(need_fetch) - 1:
                time.sleep(args.delay)
            continue

        (cache / f"{date_fmt}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        stat = data.get("stat")
        row = next((r for r in data.get("data", []) if r[0].strip() == stock), None)
        total = row[18] if row else "N/A"
        print(f"  [{i+1}/{len(need_fetch)}] {d}: stat={stat}  total={total}")
        if stat == "OK" and row:
            fetched_ok += 1

        if i < len(need_fetch) - 1:
            time.sleep(args.delay)

    final_ok = ok_count + fetched_ok
    print(f"\n完成：{final_ok}/{len(dates)} 筆 OK")
    sys.exit(0 if final_ok == len(dates) else 1)


if __name__ == "__main__":
    main()
