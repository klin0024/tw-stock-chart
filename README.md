# 台股走勢圖產生器

使用 Claude Code + `tw-stock-chart` skill 自動抓取台灣上市股票每日行情、三大法人買賣超，並疊加 FactSet 分析師目標價，產生互動式 HTML 走勢圖。

![台積電2330走勢圖] (台積電2330走勢圖.jpg)


## 圖表功能

- **收盤價折線** + **20 日移動平均線**
- **每日成交量** 柱狀圖（漲紅跌綠）
- **三大法人累計買賣超**（外資 / 投信 / 自營商，單位：張）
- **FactSet 分析師目標價中位數** 水平線（含更新日期）
- 支援 **深色模式**（`prefers-color-scheme: dark`）
- 右上角資訊卡：最新收盤、目標價、距離目標價 %、期間漲幅

## 資料來源

| 資料 | API / 來源 |
|------|-----------|
| 每日 OHLCV | [TWSE STOCK_DAY](https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY) |
| 三大法人買賣超 | TWSE T86，快取於 `twse_t86_data/` |
| FactSet 目標價 | 鉅亨速報（Exa 語義搜尋） |

## 使用方式

在 Claude Code 中輸入，例如：

```
台積電半年走勢
台化 9 個月走勢
2454 6 個月走勢
```

skill 會自動：
1. 呼叫 `fetch_twse.py` 下載收盤價與成交量
2. 呼叫 `t86_ensure.py` 補齊缺漏的三大法人快取
3. 呼叫 `t86_extract.py` 提取指定股票的買賣超資料
4. 呼叫 `search.py` 搜尋最新 FactSet 目標價
5. 產生單一自包含 HTML（無外部依賴，可離線開啟）

## 目錄結構

```
stock3/
├── README.md
├── 台積電2330走勢圖.html
├── 台積電2330走勢圖.pdf
├── twse_t86_data/          # T86 三大法人每日 JSON 快取
│   ├── 20260101.json
│   └── ...
└── .claude/
    └── skills/
        └── tw-stock-chart/
            └── scripts/
                ├── fetch_twse.py
                ├── t86_download.py
                ├── search.py
                └── base.py
```
