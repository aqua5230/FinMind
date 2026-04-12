# SESSION.md — FinMind 專案狀態

更新時間：2026-04-12（session 2）

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

## 當前階段：首頁改版（量化終端機風格）

| 項目 | 狀態 | 備注 |
|------|------|------|
| SearchInput 放大鏡 icon | ✅ 完成 | |
| ChartControls 分隔線優化 | ✅ 完成 | 顏色 #636366 |
| 訊號箭頭系統 | ✅ 完成 | 藍↑做多，條件同步 |
| 回測最佳化 | ✅ 完成 | RSI<30 + 跌幅≥20%，n=487，T+10 75.8% |
| 首頁改版：量化終端機風格 | ✅ 完成 + 部署 | 黑底螢光配色，左側大盤+日誌，右側K線/監控列表 |
| 搜尋列整合確認＋掃描按鈕 | ✅ 完成 + 部署 | 同一排：input → [↵ 確認] [掃描] |
| AppHeader 移除 | ✅ 完成 | 搜尋移入終端機首頁，AppHeader 不再使用於 page.tsx |
| 字型放大 | ✅ 完成 + 部署 | 全面升一級（最小 13px，標題 28px）|
| 後端 /api/scan | ✅ 完成 + 部署 | 1075支（證交所動態），TTL快取10分鐘 |
| 前端掃描器 UI | ✅ 完成 + 部署 | 點股票後面板保留，可直接切換 |
| signals.ts 條件同步 | ✅ 完成 + 部署 | RSI<30 + 跌幅≥20%，移除 BOLL/MACD/short |
| 股票清單動態化 | ✅ 完成 + 部署 | 證交所 openapi，850→1075支，TTL 1天 |
| 玉山交易 SDK | ✅ 安裝完成 | esun_trade 2.2.0，模擬下單測試通過 |
| 玉山行情 SDK | ✅ 安裝完成 | esun_marketdata 2.2.0 |
| 玉山模擬下單 | ✅ 測試通過 | ret_code 000000，待申請正式金鑰 |
| StockInfoBar 視覺強化 | ✅ 完成 + 部署 | 現價 text-4xl，漲跌幅改色塊 badge |
| RSI 算法修正 | ✅ 完成 + 部署 | 改 Wilder's EMA，與後端 scan.py 同步，訊號箭頭可正確顯示 |
| 全面 bug 修復（2026-04-12）| ✅ 完成 + 部署 | 見下方清單 |
| cursor-crosshair → cursor-pointer | ✅ 完成 + 部署 | 監控列表/大盤指數/掃描結果，2026-04-12 |

### 2026-04-12 修復清單（已全部部署）
| 項目 | 說明 |
|------|------|
| tw_stocks.py `verify=False` | 移除 SSL 漏洞 |
| scan.py / signals.ts 死碼 | 移除 BOLL/MACD/Volume 未使用的計算函數與常數 |
| CandlestickChart.tsx 訊號條件 | SIGNAL_REQUIRED_INDICATORS 改為只需 `["RSI"]` |
| .gitignore | 加入 `trading/config*.ini` 和 `*.p12` |
| trading 路徑 bug | test_order.py / reset_password.py 改用 `Path(__file__).parent` |
| requirements.txt | 補上 numpy / pandas / esun_trade / esun_marketdata |
| fetchLatestPrice | 查詢區間 14 天縮短為 5 天 |
| resolveStockId 搜尋 | 加入 startsWith 優先層（完全相符 > 開頭 > 包含）|
| AppHeader 狀態提升 | searchValue 提升至 page.tsx，搜尋後清空，選掃描結果後填入代號 |
| routes.py 冗餘過濾 | 移除 get_price 的多餘日期二次過濾 |

### 2026-04-12 掃描穩定化（已全部部署）
| 項目 | 說明 |
|------|------|
| Railway PostgreSQL | 新增 Postgres service，DATABASE_URL 注入後端 |
| stock_report/data/db.py | 新增 DB 連線、init_db()、upsert_prices()、query_prices() |
| stock_report/data/price_sync.py | 每日批次抓所有股票近150天資料存DB，含重試 |
| scan.py | _fetch_stock_prices 改從 DB 讀，fallback yfinance |
| main.py | 加 lifespan，啟動時 init_db + 首次同步，每天 16:30 自動更新 |
| requirements.txt | 移除 esun_trade/esun_marketdata（Railway 找不到），加 psycopg2-binary/apscheduler |
| 掃描預載 | page.tsx 頁面載入時背景 fetch，點按鈕瞬間顯示 |

### 2026-04-12 session 2 完成（已全部部署）
| 項目 | 說明 |
|------|------|
| 掃描穩定性強化 | db.py 加 get_latest_price_date()；main.py 改用 _should_run_initial_sync()，考慮台北時區+週末+16:30，資料過期才觸發同步 |
| /api/db-status 端點 | routes.py 新增，回傳 has_price_data + latest_price_date，DB 掛掉回 503 |
| 新分頁配色統一 | StockInfoBar / KLinePanel / PillButton 全面換成終端機風格（#050505 底、#222222 邊框、cyan #00E5FF、neon green/red 漲跌色）|

### 2026-04-12 session 3（✅ 完成並部署）
| 項目 | 狀態 | 說明 |
|------|------|------|
| T+10 勝率 badge | ✅ 完成 + 部署 | page.tsx line 387 加說明行 `T+10 勝率 75.8%（n=487）`，75.8% 用 cyan 強調 |
| 根因：ScanPanel 是孤兒元件 | ✅ 已診斷 | 原本 badge 加在 `ScanPanel.tsx` 但全專案無人 import，page.tsx 自己 inline 渲染 scanResults；改到 page.tsx 真正渲染處才生效 |
| deploy.sh 修復 | ✅ | 延長等待 90s、移除 grep 中斷 |
| Railway 部署機制 | ✅ 驗證正常 | v2.6→v2.7 測試證明 chunk hash 會變，非快取問題；本次 `page-2432a986c46555de.js` 已含 75.8/n=487/勝率 |

### 教訓
- 改 UI 前先確認元件有被 import — 用 `grep -n "ComponentName"` 全專案搜，沒有就是孤兒
- Railway 部署沒「卡快取」，是 source 改錯地方 — 之前耗費整個 session 排查假問題

### 待處理（session 3 之後）
| 項目 | 優先度 | 說明 |
|------|--------|------|
| 訊號記錄系統 | MED | 進場日/股票/價格 → T+10 追蹤，驗證策略持續有效性 |
| 申請玉山正式 API 金鑰 | LOW | esun_trade 只能本地用，Railway 上需另外處理（暫緩） |

---

## 回測現況（2026-04-11 更新）

### 已完成
- 建立可交易宇宙：TWSE+TPEX 公開 API → yfinance 篩選日均成交 > 1000萬 → **559 支**
- 資料來源切換：FinMind（API 配額耗盡）→ **yfinance**
- Train/Test 分割方式修正：股票分割（❌ 過擬合）→ **時間分割（✅）**
  - Train：2021-2023（3 年）
  - Test：2024-2025（2 年）
- Grid search 參數（64 組合）：rsi / vol / twii / dd 四個維度

### 回測結果（2026-04-11）
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
- 申請玉山正式 API 金鑰
- 整合掃描器 → 自動下單流程
- 建立訊號記錄系統（進場日、股票、價格 → T+10 追蹤）
- 考慮把 T+10 勝率 75.8% 顯示在掃描結果 UI 上

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

1. `frontend/app/page.tsx` — 首頁（量化終端機設計，含搜尋/掃描/K線/監控列表）
2. `frontend/lib/signals.ts` — 訊號條件（RSI<30 + 跌幅≥20%）
3. `stock_report/api/scan.py` — 掃描邏輯（同上條件）
4. `stock_report/data/tw_stocks.py` — 動態抓取證交所股票清單
5. `trading/test_order.py` — 玉山模擬下單測試
6. `trading/config.simulation.ini` — 玉山模擬環境設定
