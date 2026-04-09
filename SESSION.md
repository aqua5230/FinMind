# SESSION.md — FinMind 專案狀態

更新時間：2026-04-09

---

## 專案結構

```
FinMind/
├── stock_report/          ← FastAPI 後端
│   └── api/routes.py      ← 主要 API endpoints
├── frontend/              ← Next.js 前端
│   └── components/chart/
│       ├── CandlestickChart.tsx  ← K 線圖主元件
│       └── KLinePanel.tsx        ← 工具列
└── SESSION.md             ← 本檔案
```

## 部署

- 後端：Railway（自動 deploy from main）
- 前端：Railway，`frontend/` 目錄，指令 `npx next start -p $PORT`
- **正確部署指令（從專案根目錄執行）：**

```bash
railway up
```

> ⚠️ **絕對不能** `cd frontend && railway up`
> Railway 設有 `NIXPACKS_PATH=frontend` env var，必須從根目錄上傳，Railway 才能正確找到 `frontend/` 子目錄。
> 從 `frontend/` 上傳 → Railway 找 `frontend/frontend/` → 找不到 → fallback 舊 git cache build → 所有改動都不生效。

---

## 當前階段：前端 K 線圖

| 項目 | 狀態 | 備注 |
|------|------|------|
| Railway 部署設定 | ✅ 完成 | Root Dir = frontend，移除 railway.json build 區塊 |
| 後端價格 API 快取 | ✅ 完成 | TTLCache 200 筆，10 分鐘 |
| 零價格過濾 | ✅ 完成 | OHLC 任一為 0 就丟棄 |
| K 線圖 loading skeleton | ✅ 完成 | 格線 + 假 K 棒 |
| MACD/RSI 壓縮 candle 問題 | ✅ 完成 | applyPaneHeight 直接設 _drawPanes 高度 |
| 空心/港式 crash 修復 | ✅ 完成 | 移除 priceMark.last.compareRule，加 null 防呆 |
| 週期改 dropdown | ✅ 完成 | 日/週/月 dropdown |
| 按鈕純文字風格 | ✅ 完成 | 選中才有背景 |
| K 線圖空白 Bug | ✅ 已修復並部署 | 見下方根因分析 |
| MACD/RSI n/a Bug | ✅ 已修復並部署 | 見下方根因分析 |
| Deploy 最新改動 | ✅ 完成 | 2026-04-05，從根目錄 `railway up` |
| 盤中即時 K 線更新 | ✅ 完成 | 2026-04-09，TWSE 免費 API + DataLoader.subscribeBar，60 秒 polling |
| Header 大股價顯示 | ❌ 未做 | |
| Hover-only OHLCV tooltip | ❌ 未做 | |
| Morandi 指標線發光效果 | ❌ 未做 | |

---

## 根因分析（2026-04-05 大 debug session）

### Bug 1：K 線圖空白（candle 不顯示）

**症狀：** production 完全空白，十字線可見，本地正常。

**根因：** Codex 之前加了 `chart.resetData()` 在 `activeIndicators` useEffect 裡（createIndicator 之後）。每次 indicator 被 toggle，整個 K 線資料就被清空。

**修復：** 從 `activeIndicators` effect 移除 `chart.resetData()` 呼叫。

---

### Bug 2：MACD / RSI 顯示 n/a

**症狀：** production MACD/RSI 顯示 n/a 或空白，本地正常。

**根因有三層：**

1. **calcParams 被清空**：`overrideIndicator({ name, calcParams: [], precision })` — `calcParams: []` 覆蓋了 MACD 的計算參數 [12, 26, 9]，導致無法計算。
   - 修復：改為 `overrideIndicator({ name, precision })`，拿掉 `calcParams`。

2. **timing bug（React Strict Mode 遮蔽）**：`activeIndicators` useEffect 在 mount 時執行，此時 `isLoading=true`，chart 尚未初始化，`chartRef.current` 為 null，整個 effect 被 early return 跳過。之後 `isLoading` 變 false、chart 完成初始化，但 `activeIndicators` effect 不在 deps 裡，不會重新跑。
   - 症狀在 dev 看不出來：React Strict Mode 會 mount→cleanup→remount，第二次 mount 時 isLoading 已經是 false，effect 正常執行，遮蓋了 bug。
   - 修復：在 `activeIndicators` effect 的 deps 加入 `isLoading`。

3. **klinecharts async TaskScheduler**：`createIndicator` 後，指標計算是非同步的（TaskScheduler + Promise.all）。若沒有強制重載資料，指標可能以錯誤時序計算。
   - 修復：新增 `anyCreated` flag，`createIndicator` 後若有新建指標，呼叫 `replaceChartData(chart, chartDataRef.current)` 強制重新計算。

---

### Bug 3：所有修復都沒上到 production

**症狀：** 每次 deploy 後 production 仍是舊行為。curl 線上 bundle 確認是 `e385cda` 舊 commit 的程式碼。

**根因：** `railway up` 從 `frontend/` 目錄執行。Railway 的 `NIXPACKS_PATH=frontend` 設定期望在上傳內容的根目錄找 `frontend/` 子目錄。從 `frontend/` 上傳時找不到 `frontend/frontend/`，fallback 到 git cache（`e385cda`），永遠用舊版 build（2.8s build time）。

**確認方法：**
- 錯誤上傳：build time 2.8s，page chunk hash `1218df118821396c`
- 正確上傳（從根目錄）：build time 4.6s，page chunk hash `6971f26ebd64b196`

**修復：** 永遠從專案根目錄 `/Users/lollapalooza/Desktop/FinMind/` 執行 `railway up`。

---

### 其他教訓

- **Railway webpack cache** (`/root/.cache`)：Railway 會在 build 之間保留 cache。`nixpacks.toml` 已設定 `rm -rf node_modules/.cache .next/cache` + `cache_directories = []` 來強制 clean build。
- **Fastly CDN cache**：Next.js 靜態頁面預設 `s-maxage=31536000`，`x-nextjs-cache: HIT` 表示命中 CDN。這是 red herring——真正問題是 webpack 根本沒有重新編譯，不是 CDN 快取。
- **Codex 無法做 production debug**：Codex 無法 curl 線上 URL、無法跨多系統迭代推理。production debug 必須由 Claude 直接動手，確認根因後才派 Codex 改 code。

---

## 工作流規則（嚴格執行）

- Claude 只出任務單，不讀程式碼、不自己改（例外：production debug 調查）
- 程式碼任務 → `codex exec --full-auto --skip-git-repo-check "..."`
- 驗收 → Gemini 正確性 + Codex 範圍
- 不 push，需使用者確認
- **部署** → 用 `./deploy.sh`（不要直接跑 `railway up`）
  - 腳本會：① 擋掉未 commit 狀態 ② railway up ③ 驗證線上 bundle
  - `railway up` 只上傳 git 已 commit 的檔案，未 commit = 舊版上線
  - Healthcheck 通過 ≠ 新版上線，必須驗證 bundle 內容

---

## 下一步

1. ✅ ~~Deploy 到 Railway（從根目錄 `railway up`）~~ — 已完成
2. ✅ ~~盤中即時 K 線更新~~ — 已完成（TWSE API + subscribeBar）
3. Header 大股價顯示
4. Hover-only OHLCV tooltip
5. Morandi 指標線發光效果
