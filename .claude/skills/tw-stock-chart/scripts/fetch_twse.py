"""
Usage: python fetch_twse.py <stock_no> <n_months>
Output: JSON array to stdout
  [{"date": "2026-06-13", "label": "6/13", "close": 59.5, "volume": 12.34}, ...]
"""

import sys
import json
import time
import urllib.request
from datetime import date

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    # fallback: manual month arithmetic
    class relativedelta:
        def __init__(self, months=0):
            self.months = months
        def __rsub__(self, other):
            m = other.month - self.months
            y = other.year + (m - 1) // 12
            m = (m - 1) % 12 + 1
            return other.replace(year=y, month=m)


def fetch_month(stock_no: str, year: int, month: int) -> list[dict]:
    url = (
        f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
        f"?date={year}{month:02d}01&stockNo={stock_no}&response=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read())
    except Exception as e:
        print(f"[warn] {year}/{month:02d} fetch failed: {e}", file=sys.stderr)
        return []

    if payload.get("stat") != "OK":
        return []

    rows = []
    for rec in payload.get("data", []):
        # rec[0] = "115/06/01"  (民國年/月/日)
        # rec[1] = 成交股數, rec[6] = 收盤價
        try:
            roc_y, mm, dd = rec[0].split("/")
            iso_date = f"{int(roc_y) + 1911}-{mm}-{dd}"
            label = f"{int(mm)}/{dd}"
            close = float(rec[6].replace(",", ""))
            volume = float(rec[1].replace(",", "")) / 1_000_000  # 百萬股
            rows.append({"date": iso_date, "label": label, "close": close, "volume": volume})
        except (ValueError, IndexError):
            continue
    return rows


def main():
    if len(sys.argv) < 3:
        print("Usage: python fetch_twse.py <stock_no> <n_months>", file=sys.stderr)
        sys.exit(1)

    stock_no = sys.argv[1]
    n_months = int(sys.argv[2])

    today = date.today()
    all_rows = []

    for i in range(n_months - 1, -1, -1):
        target = relativedelta(months=i)
        d = today - target
        rows = fetch_month(stock_no, d.year, d.month)
        all_rows.extend(rows)
        if i > 0:
            time.sleep(0.3)  # 避免 TWSE 限流

    print(json.dumps(all_rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
