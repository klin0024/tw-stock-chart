#!/usr/bin/env python3
"""t86_extract.py — 從 T86 快取萃取個股每日買賣超，輸出 JSON。

用法：
  echo '["2026-01-02","2026-01-05",...]' | python t86_extract.py <stock_no> [--cache-dir DIR]

從 stdin 讀取 YYYY-MM-DD 日期 JSON 陣列，
從快取目錄讀取各日 T86 資料，萃取指定個股欄位。

stdout 輸出 JSON 陣列（單位：張，1張=1000股）：
  [{"date":"2026-01-02","foreign":5300,"trust":-7087,"dealer":309,"total":-1478}, ...]

若某日快取不存在或 stat≠OK，該日不輸出（由呼叫端決定是否先執行 t86_ensure.py）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_int(s: str) -> int:
    return int(s.replace(",", "").replace("+", ""))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Extract per-stock T86 data from cache")
    p.add_argument("stock_no", help="股票代號，e.g. 2881")
    p.add_argument("--cache-dir", default="twse_t86_data", help="快取目錄（預設 twse_t86_data）")
    args = p.parse_args()

    stock = args.stock_no.strip()
    cache = Path(args.cache_dir)

    dates: list[str] = json.loads(sys.stdin.read())

    results = []
    missing = []

    for d in dates:
        fname = cache / (d.replace("-", "") + ".json")
        if not fname.exists():
            missing.append(f"{d} (not found)")
            continue
        try:
            payload = json.loads(fname.read_text(encoding="utf-8"))
        except Exception as e:
            missing.append(f"{d} (read error: {e})")
            continue

        if payload.get("stat") != "OK":
            missing.append(f"{d} (stat={payload.get('stat')})")
            continue

        row = next((r for r in payload.get("data", []) if r[0].strip() == stock), None)
        if not row:
            missing.append(f"{d} (no row for {stock})")
            continue

        try:
            results.append({
                "date":    d,
                "foreign": round(parse_int(row[4])  / 1000),  # 外資買賣超
                "trust":   round(parse_int(row[10]) / 1000),  # 投信買賣超
                "dealer":  round(parse_int(row[11]) / 1000),  # 自營商買賣超
                "total":   round(parse_int(row[18]) / 1000),  # 三大法人合計
            })
        except (IndexError, ValueError) as e:
            missing.append(f"{d} (parse error: {e})")

    if missing:
        print(f"[t86_extract] 缺漏 {len(missing)} 筆（建議先執行 t86_ensure.py）:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)

    print(f"[t86_extract] 輸出 {len(results)}/{len(dates)} 筆", file=sys.stderr)
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
