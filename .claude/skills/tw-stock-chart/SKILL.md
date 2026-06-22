---
name: tw-stock-chart
description: "產生台灣上市股票近 N 個月的每日走勢 HTML 圖表，含收盤價、20MA、成交量柱狀圖，並自動搜尋 FactSet 分析師目標價中位數疊加於圖上。觸發時機：使用者提到「走勢圖」「股價圖」「K線」「FactSet目標價」「生成圖表」「產生HTML」，或股票代號加上月份數字（如「2330 6個月」「台積電走勢」）。"
---

# 台灣股票走勢圖 Skill

產生自包含 HTML 走勢圖，整合 TWSE 日價量、T86 三大法人買賣超、FactSet 目標價。

---

## 執行流程

### Step 1 — 解析參數

| 參數 | 說明 | 預設 |
|------|------|------|
| 股票代號 | 如 `2330`、`2881` | — |
| 股票名稱 | 如 `台積電`、`富邦金` | — |
| 月數 N | 最大 12 | 6 |
| 輸出檔名 | `{名稱}{代號}走勢圖.html` | — |
| 輸出路徑 | 當前工作目錄 | — |

代號或名稱不確定時先詢問使用者。

---

### Step 2 — 取得每日股價（TWSE）

```bash
SKILL_SCRIPTS=".claude/skills/tw-stock-chart/scripts"
PRICE_JSON=$(python3 "$SKILL_SCRIPTS/fetch_twse.py" {代號} {N})
```

**API：** `https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={YYYYMM}01&stockNo={代號}&response=json`

**月份範圍：** 從當月往回推 N 個月（含當月）。

**輸出：**
```json
[{"date":"2026-06-13","label":"6/13","close":59.5,"volume":12.34}, ...]
```

script 內部處理：民國年 +1911 轉西元、移除千分位逗號、逐月間隔 0.3s 防限流。

---

### Step 3 — 三大法人買賣超（T86）

**3a — 檢查快取，缺漏才下載：**

```bash
SKILL_SCRIPTS=".claude/skills/tw-stock-chart/scripts"
CACHE_DIR="twse_t86_data"
DATES_JSON=$(echo "$PRICE_JSON" | python3 -c "import json,sys; print(json.dumps([d['date'] for d in json.load(sys.stdin)]))")

echo "$DATES_JSON" | python3 "$SKILL_SCRIPTS/t86_ensure.py" {代號} --cache-dir "$CACHE_DIR"
```

- 已有 OK 快取的日期直接略過
- SKIP 檔（可能是限流誤標）會重打 API 確認
- exit 0 = 全部完整；exit 1 = 仍有缺漏，重跑即可

**3b — 萃取個股資料：**

```bash
T86_JSON=$(echo "$DATES_JSON" | python3 "$SKILL_SCRIPTS/t86_extract.py" {代號} --cache-dir "$CACHE_DIR")
```

**輸出（單位：張，1張=1000股）：**
```json
[{"date":"2026-01-02","foreign":5300,"trust":-7087,"dealer":309,"total":-1478}, ...]
```

缺漏時 stderr 提示，`len(T86_JSON)` 應等於交易日總數。

**T86 欄位索引：**

| 索引 | 欄位 |
|------|------|
| 4  | 外資及陸資買賣超（不含外資自營商） |
| 10 | 投信買賣超 |
| 11 | 自營商買賣超（合計） |
| 18 | 三大法人買賣超合計 |

---

### Step 4 — 搜尋 FactSet 目標價

```bash
SEARCH_RESULT=$(uv run --with fastmcp "$SKILL_SCRIPTS/search.py" "{股票名稱} {代號} FactSet 目標價 {年份}" 10)
```

從搜尋結果提取每則新聞的發布日期與目標價中位數，建立 step function（前值延用至下次調整）：

```json
[{"date":"2026-04-28","tp":97,"analysts":9,"note":"EPS上修至8.51"}, ...]
```

搜尋結果不足 3 筆時顯示警告，但繼續產生圖表（目標價線留空）。

---

### Step 5 — 計算衍生指標

**價格指標：**
- 20MA：前 19 日 + 當日均值，前 19 日為 `null`
- 漲跌幅 = (最新收盤 − 起始收盤) / 起始收盤 × 100%
- 距目標價空間 = (目標價 − 最新收盤) / 最新收盤 × 100%

**T86 陣列解析（必須從 `T86_JSON` 提取，禁止手動填寫）：**
```python
import json
t86 = json.loads(T86_JSON)          # T86_JSON 為 Step 3b 的輸出字串
t86_foreign = [r["foreign"] for r in t86]
t86_trust   = [r["trust"]   for r in t86]
t86_dealer  = [r["dealer"]  for r in t86]
```
將以上三個 Python list 序列化為 JSON 陣列，嵌入 HTML 的 JS 變數 `t86Foreign`、`t86Trust`、`t86Dealer`。**不可自行捏造或省略任何元素。**

**T86 累計買賣超（供累計法人圖使用）：**
```javascript
function cumsum(arr) {
  let s = 0;
  return arr.map(v => { if (v != null) s += v; return v != null ? s : null; });
}
const cumForeign   = cumsum(t86Foreign);
const cumTrust     = cumsum(t86Trust);
const cumDealer    = cumsum(t86Dealer);
const dailyTotal   = t86Foreign.map((f,i) =>
  f != null ? f + (t86Trust[i]??0) + (t86Dealer[i]??0) : null);
const cumTotalLine = cumsum(dailyTotal);
```

---

### Step 6 — 產生 HTML 檔案

#### 頁面區塊

1. 標題 + 副標題（股票名稱、代號、日期範圍、交易日數）
2. 五個指標卡片
3. 圖例
4. 股價圖 canvas（300px）
5. 成交量圖 canvas（100px）
6. 三大法人累計買賣超圖 canvas（160px）
7. 三大法人每日買賣超圖 canvas（160px）
8. FactSet 調價紀錄表格
9. 資料來源聲明

#### Canvas 高度固定寫法（必須遵守）

Chart.js 在 `responsive:true` + `maintainAspectRatio:false` 模式下，若父容器無固定高度，圖表每次 resize 都會無限拉高。**每個 canvas 必須包在固定高度的 div 內：**

```html
<!-- 正確寫法 -->
<div style="position:relative;height:300px">
  <canvas id="priceChart"></canvas>
</div>

<!-- 錯誤寫法（canvas 的 height 屬性無效） -->
<canvas id="priceChart" height="300"></canvas>
```

各圖高度：股價圖 300px、成交量 100px、累計法人 160px、每日法人 160px。

#### 圖表規格（Chart.js 4.4.1）

**股價圖（雙 Y 軸）**

| 資料集 | 顏色 | 樣式 | Y 軸 |
|--------|------|------|------|
| 收盤價 | `#378ADD` | 實線，fill 半透明 | 右（元） |
| 20MA | `#5DCAA5` | 虛線 [4,3] | 右 |
| FactSet 目標價 | `#EF9F27` | 虛線 [6,3]，stepped，調價日圓點 | 右 |
| 外資累計 | `rgba(55,138,221,0.7)` | 虛線 [3,3] | 左（張） |
| 投信累計 | `rgba(239,159,39,0.7)` | 虛線 [3,3] | 左 |
| 自營商累計 | `rgba(93,202,165,0.7)` | 虛線 [3,3] | 左 |
| 三大合計累計 | `rgba(208,74,42,0.85)` | 虛線 [5,3]，borderWidth 1.8 | 左 |

左軸 `position:'left'`，格線關閉，≥1000張顯示 K。

**成交量圖（bar）**
- 上漲日 `rgba(208,71,42,0.5)`，下跌日 `rgba(26,122,90,0.5)`
- Y 軸單位：百萬股（M）

**三大法人買賣超圖（stacked bar）**

| 資料集 | 顏色 |
|--------|------|
| 外資 | `rgba(55,138,221,0.75)` |
| 投信 | `rgba(239,159,39,0.75)` |
| 自營商 | `rgba(93,202,165,0.75)` |

每日堆疊柱，右軸單位：張（K 縮寫）。不含累計線。

#### 指標卡片

| # | 內容 | 顏色規則 |
|---|------|---------|
| 1 | 最新收盤價 | 紅 |
| 2 | FactSet 目標價（無資料顯示 N/A） | 橙 |
| 3 | 距目標價空間 | 正綠負紅 |
| 4 | 追蹤分析師數 | 藍 |
| 5 | N 個月漲跌幅 | 正綠負紅 |

#### 深色模式

```css
@media (prefers-color-scheme: dark) {
  body { background: #1a1a1a; color: #e0e0e0; }
  .card, .events, .chart-container { background: #242424; border-color: rgba(255,255,255,0.1); }
}
```

---

### Step 7 — 輸出確認

```
已產生 {檔名}.html
  路徑：{完整路徑}
  交易日數：{N} 筆　T86：{M} 筆
  FactSet 調價紀錄：{K} 筆（{最早目標價} → {最新目標價}）
  最新收盤：{價格}　距目標價：{±X.X%}
```

---

## 錯誤處理

| 情況 | 處理方式 |
|------|---------|
| TWSE 股價 API stat≠OK | 跳過該月，繼續其他月份 |
| T86 限流導致交易日誤存 SKIP | `t86_ensure.py` 自動重打 API 驗證並覆寫快取 |
| T86 筆數仍不足 | 重跑 Step 3a；缺漏日對應累計值以前值延用（`spanGaps:true`） |
| FactSet 搜尋無結果（< 3筆） | 圖表仍產生，目標價線不顯示，卡片顯示 N/A |
| 輸出路徑不存在 | 改寫至當前工作目錄並告知使用者 |

---

## Scripts 對照

| 檔案 | 用途 |
|------|------|
| `fetch_twse.py` | 抓 TWSE 日價量，輸出 JSON |
| `t86_ensure.py` | 掃快取，補抓缺漏 T86 日期 |
| `t86_extract.py` | 從快取萃取個股 T86，輸出 JSON |
| `t86_download.py` | 批次下載整段期間 T86（可選，初次建立快取用） |
| `search.py` | Exa 語意搜尋，取得 FactSet 調價新聞 |

---

## 注意事項

- 民國年 + 1911 = 西元年（如 115 → 2026）
- FactSet 目標價為中位數，來自鉅亨網速報，非官方 FactSet 資料庫
- 所有數據僅供參考，不作為投資建議
- 產生的 HTML 完全靜態，無後端服務
