# SESSION.md — FinMind 專案狀態

更新時間：2026-04-14（session 8 — 月營收動能策略回測完成）

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

### 2026-04-13 session 4（✅ 完成並部署）
| 項目 | 狀態 | 說明 |
|------|------|------|
| StockInfoBar 盤中不更新 bug | ✅ 修復 + 部署 | 原因：fetchLatestPrice 只抓一次 FinMind 昨收，盤中不會變；先加 30 秒輪詢證交所 API 作為快速修復 |
| Fugle WebSocket 即時行情 | ✅ 完成 + 部署 | 取代 30 秒輪詢，盤中毫秒級推送 |
| 後端 ws.py（新） | ✅ | WebSocket endpoint `/ws/realtime/{stock_id}`，連 Fugle 串流轉發前端 |
| main.py 掛載 ws_router | ✅ | |
| useRealtimeBar.ts | ✅ | HTTP 輪詢 → WebSocket，即時更新 K 線圖最後一根 bar |
| stock/page.tsx | ✅ | 30 秒輪詢 → WebSocket，即時更新 StockInfoBar 現價/漲跌 |
| Railway FUGLE_API_KEY | ✅ | 已設定環境變數 |
| requirements.txt | ✅ | 加 websockets>=12.0 |

### 2026-04-13 session 5（🚨 重大發現：策略實際虧錢）

**backtest_v2.py 完成並執行，揭露之前 75.8% 勝率是誤導性指標。**

| 指標 | 舊（T+10 死抱）| 新（真實模擬）|
|------|---------------|---------------|
| 勝率 | 75.8% | **29.2%** |
| 年化報酬 | — | **-21.3%** |
| 總報酬（2023-2025）| — | **-48.5%** |
| Sharpe | — | **-1.01** |
| Max Drawdown | — | **47.2%** |
| Profit Factor | — | **0.43** |

**為什麼 75.8% → 29.2%：**
- 75.8% = 訊號觸發後死抱 10 天漲跌比例（不可執行，會凹單）
- 29.2% = 加入停損 -10% / 停利 +20% / 移動停利 5% / 時間停損的真實勝率
- 訊號觸發後常續跌 → 被停損 → 死抱的話 T+10 可能已反彈，產生假勝率
- 贏家被停利截斷、輸家被停損砍掉，真實交易的不對稱性

**backtest_v2.py 內容（新建）：**
- 訊號：RSI<30 + 近20日高點跌幅≥20%
- 進場：訊號隔日開盤價
- 出場：停損/停利/移動停利/時間停損四擇一
- 成本：買 0.1425% + 賣 0.1425% + 證交稅 0.3%
- 資金：100萬起始、每筆 20%、最多 5 筆
- Grid search：SL/TP/Trail/MaxHold 共 81 組合，train set 選最佳 → test set 驗證
- 輸出：backtest_trades.csv + backtest_equity.png + 績效摘要

**執行：**
```bash
# 需要 matplotlib：pip3 install matplotlib
python3 backtest_v2.py
```
首跑用 400 支股票（/tmp/tw_universe_all.json 截取），完整 1956 支未跑。

**已知問題：**
- yfinance 對冷門股的 ticker fallback 可能回傳相同資料（trade log 中看到 1726/1727/1730/1731/1732 同日同價同結果）
- 需要資料清洗過濾

### 2026-04-13 session 6（📝 僅規劃，未派工）

使用者選項 1（先做資料清洗）。Claude 額度剩 1%，只寫任務書，不派 Codex。

**髒資料根因：** `backtest_v2.py` 的 `fetch_one` (line 133) 對同一 stock_id 先試 `.TW` 再試 `.TWO`，yfinance 對不存在的 ticker 有時回傳鄰近代號資料 → 1726/1727/1730/1731/1732 同日同價。且無 row-level sanity check。

**清洗任務書（下個 session 直接派給 Codex 用）：**

階段 1 — 改 `backtest_v2.py`，在 fetch 層加清洗：
1. Universe 帶 market tag（TWSE/TPEX），fetch_one 依 market 選 suffix，不再 try both
2. Row sanity：drop high<low / close<=0 / open<=0 / volume<0
3. 漲跌幅檢查：|daily_return|>11% 異常列數 > 5 → 整檔丟棄
4. 成交量：>=50% 天數 volume=0 → 丟棄
5. 覆蓋度：<120 天 → 丟棄（已有）
6. 指紋去重：close[-200:] SHA1 相同組只留 stock_id 最小者

階段 2 — 輸出 `/tmp/clean_report.json`：
`{input, kept, dropped:{insufficient_data, bad_rows, volume, limit_violation, duplicate}, duplicates:[[ids],...]}`

階段 3 — 重跑回測，比對 train/test signals 數與 test 績效，確認壞訊號消失。

**Universe 重建：** tw_stocks.py 已能分別抓 TWSE/TPEX，需要在 `/tmp/tw_universe_builder.py` 把 market 欄位寫入 `/tmp/tw_universe_all.json`。

### 2026-04-13 session 7（✅ Codex 完成資料清洗 + 本地行情快取）

**這段給下一位 Claude/Codex 先讀：資料清洗任務已經完成，不要再照 session 6 任務書重做。**

完成內容：
1. `stock_report/data/tw_stocks.py`
   - 新增 `get_tw_stocks(verify_ssl=True)`，回傳 `{id, name, market}`。
   - `market` 會標記 `TWSE` / `TPEX`。
   - `get_tw_stock_ids()` 保持向後相容，只回傳股票代號。
   - 2026-04-13 補修：TPEX API 欄位是英文 `SecuritiesCompanyCode` / `CompanyAbbreviation`，原本 parser 只吃 TWSE 中文欄位，導致 universe 只有 1075 檔 TWSE。已修正 `_parse_stock_rows()` 同時支援 TWSE/TPEX 欄位。

2. `scripts/build_tw_universe.py`（新檔）
   - 產出 `/tmp/tw_universe_all.json`。
   - 本機 Python 對 TWSE/TPEX 憑證驗證會失敗，所以腳本支援 `--insecure` 作為離線建 universe 用：
     `python3 scripts/build_tw_universe.py --insecure`
   - 已成功產出 1956 檔股票 universe：TWSE 1075 + TPEX 881。

3. `backtest_v2.py`
   - `fetch_one()` 不再同一檔 `.TW` / `.TWO` 都試。
   - 改用 universe 的 `market` 決定 yfinance suffix：
     - `TWSE` → `.TW`
     - `TPEX` → `.TWO`
   - 新增資料清洗：
     - row sanity：移除 `high < low`、`open/high/low/close <= 0`、`volume < 0`、OHLC 不一致列。
     - 漲跌幅檢查：`abs(daily_return) > 11%` 超過 5 天則整檔丟棄。
     - 成交量檢查：`volume == 0` 天數比例 >= 50% 則整檔丟棄。
     - 覆蓋度：少於 `MIN_DATA_DAYS=120` 丟棄。
     - 指紋去重：`close[-200:]` SHA1 相同組只保留 stock_id 最小者。
   - 新增 `/tmp/clean_report.json`。
   - 新增 progress output：每 50 檔印一次 `Fetched X/Y stocks; valid=N`。
   - `MAX_WORKERS` 改為 1。原因：實測 yfinance/curl 高併發會污染資料，曾出現 311 檔 duplicate；單線程後 duplicate=0。

4. 本地行情快取
   - 新增 `PRICE_CACHE_DIR = data/price_cache`。
   - `fetch_one()` 會先讀 parquet 快取；沒有或覆蓋不足才抓 yfinance。
   - 抓到資料後寫入 parquet：`data/price_cache/{stock_id}_{market}.parquet`。
   - `.gitignore` 已加入 `data/price_cache/`，避免提交 79MB 行情資料。
   - 2026-04-13 已補抓完整 1956 檔 universe；本地快取目前約 1934 個 parquet、141MB。
   - 已用完整上市+上櫃 universe 跑完 `python3 backtest_v2.py`，`fetch_error=0`。
   - `data/price_cache/` 已被 `.gitignore` 排除，不要提交。

**最新清洗報告（完整 1956 檔上市+上櫃 universe，補抓 TPEX 後）：**
```json
{
  "input": 1956,
  "kept": 1801,
  "dropped": {
    "insufficient_data": 42,
    "bad_rows": 1450,
    "volume": 0,
    "limit_violation": 113,
    "duplicate": 0,
    "missing_market": 0,
    "fetch_error": 0
  },
  "duplicates": []
}
```

**最新真實回測結果（完整 1956 檔上市+上櫃 universe，清洗 + 本地快取後）：**
| 指標 | 結果 |
|------|------|
| Train signals | 26338 |
| Test signals | 9624 |
| Best train params | SL=5%, TP=20%, Trail=8%, MaxHold=10 |
| Test trades | 456 |
| 勝率 | 34.87% |
| 總報酬 | -22.56% |
| 年化報酬 | -8.20% |
| Profit Factor | 0.93 |
| Max Drawdown | 50.36% |
| Sharpe | -0.30 |

**重要結論：**
- 資料清洗後，1726/1727/1730/1731/1732 這種重複髒資料問題已解決。
- 舊報告的 1075 檔不是完整台股，只是 TWSE；完整 universe 已修成並補抓到 1956 檔（TWSE 1075 + TPEX 881）。
- 完整 universe 後虧損縮小，但仍是負報酬、Profit Factor < 1；目前 RSI<30 + 跌幅≥20% 策略仍是負期望值。
- 不要實盤，不要 paper trading。下一步應先改策略。
- 前端若仍顯示 `T+10 勝率 75.8%`，必須移除或改成真實回測指標，否則誤導。

**下個 session 建議順序：**
1. HIGH：移除首頁/掃描 UI 的 `T+10 勝率 75.8%` 或任何類似文案。
2. HIGH：策略改進，不要再跑原策略：
   - 加大盤濾網：只在加權指數站上 200MA 或市場 regime 轉強時交易。
   - 加進場確認：跌深後隔日/數日收復短均、放量反轉、突破前高才進。
   - 加流動性濾網：排除低價、低成交額、小型冷門股。
   - 減少同一檔連續觸發：加入 cooldown。
   - 研究停損/停利邏輯是否造成當日進出過多。
3. MED：把 `backtest_v2.py` 拆成資料層/策略層/回測引擎，方便測多策略。
4. MED：建立快取更新腳本，只補最新交易日，不重抓全量。

### 2026-04-14 session 8（✅ 月營收動能策略完成）

**策略：月營收動能 + TWII 200MA 大盤濾網**

| 指標 | Train (2019-2022) | Test (2023-2025) |
|------|------------------|-----------------|
| 年化報酬 | 13.8% | **29.1%** |
| Sharpe | 0.86 | **1.74** |
| Max Drawdown | -12.5% | **-13.3%** |
| Profit Factor | 2.32 | **3.68** |
| 總報酬 | 63.9% | 106.1% |

**與 RSI 舊策略對比：Sharpe -0.30 → 1.74，MaxDD -50.4% → -13.3%**

**新增檔案：**
- `scripts/fetch_revenue.py` — 從 FinMind 拉月營收快取（已跑完，1928/1934 支成功）
- `backtest_revenue.py` — 月營收動能回測引擎（含 TWII 200MA 濾網）
- `data/revenue_cache/` — 月營收 parquet 快取（~1928 個檔案，已加入 .gitignore）
- `revenue_backtest_equity.png` — equity curve
- `revenue_backtest_trades.csv` — 16,074 筆交易記錄

**策略邏輯：**
- 訊號：每月 RevenueYoY 前 20%（流動性濾網：日均成交額 > 500 萬）
- 再平衡日：每月 11 日（下一個交易日）
- 大盤濾網：TWII < 200MA 時不持股，持現金
- 成本：買 0.1425% + 賣 0.1425% + 證交稅 0.3%

### 下一步優先事項

| 優先度 | 項目 | 說明 |
|--------|------|------|
| **HIGH** | 移除前端「T+10 勝率 75.8%」badge | 誤導性指標，應移除或改為真實數字 |
| **HIGH** | Paper trading 驗證 | 策略正式上線前需 3-6 個月模擬追蹤 |
| **MED** | 月營收策略整合至掃描器 | 每月 11 日自動推播月營收前 20% 名單 |
| **MED** | 策略穩健性測試 | 2025 AI 多頭影響有多大？嘗試排除電子股後重測 |
| **LOW** | 當沖策略研究 | 月營收策略穩定後再考慮 |

### 核心教訓

1. **勝率 ≠ 賺錢** — 任何只看勝率不看盈虧比的回測都是自欺
2. **「T+X 持有勝率」是外行指標** — 實際停損停利後會劇烈改變
3. **工具的價值在於揭露真相** — backtest_v2 寧可現在揭露-48%，不要拿真金白銀去發現
4. **不要把實盤建立在未經完整模擬的策略上** — 策略改到穩定正報酬前，一塊錢都不該進場

### 待處理（session 4 之後）
| 項目 | 優先度 | 說明 |
|------|--------|------|
| Fugle WebSocket 多人共用連線 | LOW | 目前每個使用者各開一條連線，基本用戶限 1 連線；多人用需改成後端共用一條連線 + 多訂閱 |
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
