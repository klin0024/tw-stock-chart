"""
t86_download.py — TWSE T86 三大法人資料下載器

用法：
  python t86_download.py --start 2026-03-01
  python t86_download.py --start 2026-01-01 --end 2026-06-01
  python t86_download.py --days 90
  python t86_download.py --start 2026-03-01 --outdir my_data --delay 0.5 --force
"""

import argparse
import json
import sys
import time
import io
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

API_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/zh/fund/t86.html",
}


def parse_args():
    p = argparse.ArgumentParser(
        description="下載 TWSE T86 三大法人每日買賣超 JSON 快取"
    )
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--start", metavar="YYYY-MM-DD",
                     help="起始日期（與 --end 搭配）")
    grp.add_argument("--days",  type=int,
                     help="從今天往回幾天（與 --start 互斥）")
    p.add_argument("--end",    metavar="YYYY-MM-DD",
                   help="結束日期（預設昨日）")
    p.add_argument("--outdir", default="twse_t86_data",
                   help="JSON 快取目錄（預設 twse_t86_data）")
    p.add_argument("--delay",  type=float, default=0.4,
                   help="每次請求間隔秒數（預設 0.4）")
    p.add_argument("--force",  action="store_true",
                   help="強制重新下載，忽略已有快取")
    return p.parse_args()


def date_range(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def fetch_day(day: date) -> dict | None:
    params = {
        "date":       day.strftime("%Y%m%d"),
        "selectType": "ALLBUT0999",
        "response":   "json",
    }
    try:
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print(f"  [ERROR] {day}: {exc}", file=sys.stderr)
        return None
    # 回傳原始 payload（含非 OK 狀態），讓呼叫端決定如何處理
    return payload


def main():
    args   = parse_args()
    today  = date.today()
    end    = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else today - timedelta(days=1)

    if args.days:
        start = end - timedelta(days=args.days - 1)
    elif args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = end - timedelta(days=30)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    all_dates  = list(date_range(start, end))
    need_fetch = []
    cached_ok  = 0   # 有交易資料
    cached_skip = 0  # 已知假日/休市
    for d in all_dates:
        cached = outdir / f"{d.strftime('%Y%m%d')}.json"
        if args.force or not cached.exists():
            need_fetch.append(d)
        else:
            stat = json.loads(cached.read_text(encoding="utf-8")).get("stat")
            if stat == "OK":
                cached_ok += 1
            else:
                cached_skip += 1  # stat == "SKIP" 或其他非 OK

    print(f"[INFO] 區間：{start} ～ {end}（共 {len(all_dates)} 天）")
    print(f"[INFO] 快取目錄：{outdir.resolve()}")
    print(f"[INFO] 快取狀態：有資料 {cached_ok} 天　已知假日 {cached_skip} 天　待下載 {len(need_fetch)} 天")

    if not need_fetch:
        print("[OK] 資料已完整，無需下載。")
        return

    downloaded = skipped = errors = 0
    for i, d in enumerate(need_fetch):
        print(f"  [{i+1}/{len(need_fetch)}] {d} ...", end=" ", flush=True)
        payload = fetch_day(d)
        if payload and payload.get("stat") == "OK":
            (outdir / f"{d.strftime('%Y%m%d')}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            print("OK")
            downloaded += 1
        else:
            # 假日/休市：寫入 SKIP 標記，下次不再重打 API
            (outdir / f"{d.strftime('%Y%m%d')}.json").write_text(
                json.dumps({"stat": "SKIP", "date": d.strftime("%Y%m%d")},
                           ensure_ascii=False), encoding="utf-8"
            )
            print("SKIP（假日/休市，已記錄快取）")
            skipped += 1
        if i < len(need_fetch) - 1:
            time.sleep(args.delay)

    print(f"\n[DONE] 下載 {downloaded} 筆，跳過 {skipped} 筆，失敗 {errors} 筆")
    print(f"[DONE] 快取目錄：{outdir.resolve()}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
