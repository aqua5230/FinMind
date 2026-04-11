# SESSION.md — FinMind 專案狀態

更新時間：2026-04-11

---

## 專案結構

```
FinMind/
├── stock_report/          ← FastAPI 後端
│   ├── api/routes.py      ← 主要 API endpoints
│   ├── api/scan.py        ← 掃描器 endpoint（新）
│   └── data/tw_stocks.py  ← 台灣50+中型100股票清單（新）
├── frontend/              ← Next.js 前端
│   ├── components/chart/
│   │   ├── CandlestickChart.tsx  ← K 線圖主元件（含訊號 overlay）
│   │   └── KLinePanel.tsx        ← 工具列（分隔線優化）
│   ├── components/ui/
│   │   ├── SearchInput.tsx       ← 搜尋框（含放大鏡 icon）
│   │   └── ScanPanel.tsx         ← 掃描結果面板（新）
│   ├── components/layout/
│   │   ├── AppHeader.tsx         ← Header（含掃描按鈕）
│   │   └── StockInfoBar.tsx
│   └── lib/
│       ├── signals.ts    ← 訊號計算（BOLL+RSI+MACD+量能）
│       └── api.ts        ← fetchScan() 等 API 函數
├── backtest.py           ← Grid search 回測腳本
└── SESSION.md            ← 本檔案
```

## 部署

- 後端：Railway service = FinMind
- 前端：Railway service = frontend
- **部署指令（從專案根目錄）：**
  - 前端：`./deploy.sh`（會驗證 bundle）
  - 後端：`railway service FinMind && railway up`
- ⚠️ 前後端是兩個獨立 service，各自需要部署

---

## 當前階段：訊號系統 + 掃描器

| 項目 | 狀態 | 備注 |
|------|------|------|
| SearchInput 放大鏡 icon | ✅ 完成 | |
| ChartControls 分隔線優化 | ✅ 完成 | 顏色 #636366 |
| 訊號箭頭系統 | ✅ 完成 | 藍↑做多、洋紅↓做空 |
| 訊號顏色 | ✅ 完成 | #33B1FF / #E540FF |
| 回測最佳化 | ✅ 完成 | RSI<35 + 量>10日均量×1.2 |
| 後端 /api/scan | ✅ 完成 + 部署 | 掃描100支，TTL快取10分鐘 |
| 前端掃描器 UI | ✅ 完成 + 部署 | 掃描按鈕 + 結果清單 |

---

## 回測現況（2026-04-11 更新）

### 已完成
- 建立可交易宇宙：TWSE+TPEX 公開 API → yfinance 篩選日均成交 > 1000萬 → **559 支**
- 資料來源切換：FinMind（API 配額耗盡）→ **yfinance**
- Train/Test 分割方式修正：股票分割（❌ 過擬合）→ **時間分割（✅）**
  - Train：2021-2023（3 年）
  - Test：2024-2025（2 年）
- Grid search 參數（64 組合）：rsi / vol / twii / dd 四個維度

### 最新回測結果（時間分割，n=58 test）
| 最佳參數 | Train T+10 | **Test T+10** | Test T+20 |
|---------|-----------|-------------|---------|
| RSI<25，無其他過濾 | 72.9% (n=129) | **86.2%** (n=58) | 56.9% |

**關鍵結論：**
- RSI 門檻應為 **< 25**（不是原本的 < 35）
- 最佳持有期：**T+10（10 個交易日）**，T+20 勝率下降（反彈後回落）
- Test 比 Train 高 → 無過擬合

### 最終部署結果（2026-04-11）
| 改動 | 內容 |
|------|------|
| 訊號條件 | RSI<30 + 跌幅≥20%（移除量能條件）|
| 掃描宇宙 | 100支 → **850支**（TWSE+TPEX，日均成交>100萬，排除ETF）|
| 資料來源 | FinMind → **yfinance**（無配額限制）|
| 統計依據 | 799支股票 × 7年，n=487 test，T+20 勝率 **75.8%** |

### 工具檔案
- `/tmp/tw_universe_all.json` — 857 支完整宇宙（含ETF）
- `/tmp/tw_universe_builder.py` — 重建宇宙腳本（MIN_TURNOVER=1M，OUTPUT_PATH=tw_universe_all.json）
- `backtest.py` — 單次回測（yfinance，時間分割）
- `grid_search.py` — Grid search（START=2019-01-01，split=2022-01-01，60組合）
- `/tmp/test_rs35_dd20.py` — 驗證不同參數組合的 Test 勝率腳本

### 下一步
- 觀察掃描結果品質（850支每天有幾個訊號）
- 考慮把 T+20 勝率 75.8% 顯示在掃描結果 UI 上

---

## 根因分析（歷史）

### Bug 1-4
見原始 SESSION.md 內容（2026-04-05 ~ 2026-04-10）

---

## 工作流規則（嚴格執行）

- Claude 只出任務單，不讀程式碼、不自己改（例外：production debug）
- 程式碼任務 → `codex exec --full-auto --skip-git-repo-check`
- 查資料/跑腳本 → `gemini -p "..." --model gemini-2.5-pro --yolo`
- 驗收 → tsc --noEmit + 線上 bundle 驗證
- **部署** → `./deploy.sh`（前端）、`railway service FinMind && railway up`（後端）

---

## 禁止碰的地方

- `railway up` 不能從 `frontend/` 目錄執行
- `CandlestickChart.tsx` chart 繪製邏輯（已穩定）
- `KLinePanel.tsx` handler 邏輯

---

## 核心檔案（下個 session 優先讀）

1. `frontend/lib/signals.ts` — 訊號條件
2. `stock_report/api/scan.py` — 掃描邏輯
3. `stock_report/data/tw_stocks.py` — 股票清單（待更新）
4. `backtest.py` — 回測腳本（需重跑更大樣本）
