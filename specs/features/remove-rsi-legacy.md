# Feature Spec: 移除 RSI 舊策略

更新日期：2026-04-16

## 目標

移除或隔離 RSI 舊策略，避免使用者或 AI 把它誤認為目前可用策略。

RSI 舊策略已被判定失效，禁止實盤。

這個任務不是調參。

也不是重新研究 RSI。

目標是清理殘留，讓專案狀態更清楚。

## 背景

RSI 是相對強弱指標。

本專案曾用 RSI 做低檔反彈策略。

但目前結論是：

- 勝率不佳
- 年化報酬為負
- 最大回撤過大
- 「T+X 持有勝率」是誤導性指標

使用者已確認：RSI 可以刪除。

## 可能影響範圍

後端：

- `stock_report/api/scan.py`
- `stock_report/api/routes.py`
- `main.py`

前端：

- `frontend/lib/api.ts`
- `frontend/app/page.tsx`
- 任何使用 `fetchScan()`、`ScanResult`、`scanResults` 的地方

回測與研究檔：

- `backtest.py`
- `backtest_v2.py`
- `grid_search.py`
- `backtest_trades.csv`
- `backtest_equity.png`

文件：

- `SESSION.md`
- `specs/current-state.md`
- `specs/roadmap.md`

## 不做

本 feature 不做：

- 重新調整 RSI 參數
- 新增 RSI 改良策略
- 改月營收動能策略
- 改雙刀配對策略
- 改法人籌碼掃描
- 部署

## 建議實作順序

### Step 1：盤點引用

先用搜尋確認所有 RSI 與舊 scan 引用：

```bash
rg -n "RSI|fetchScan|/api/scan|scanResults|ScanResult" frontend stock_report backtest*.py grid_search*.py SESSION.md specs
```

目標：

- 找出前端是否還依賴 `/api/scan`
- 找出後端是否還 include 舊 router
- 找出文件是否仍把 RSI 寫成可用策略

### Step 2：前端移除舊 scan 依賴

如果首頁已改用月營收掃描，應移除未使用的：

- `fetchScan`
- `ScanResult`
- `scanResults`
- 舊 RSI 掃描初始化 effect

注意：

不要改月營收掃描 UI。

### Step 3：後端移除舊 scan API

確認前端不再依賴後，再處理：

- `stock_report/api/scan.py` 中的 RSI scan route
- `stock_report/api/routes.py` 中舊 scan router include

注意：

`stock_report/api/scan.py` 目前也包含 `/revenue-scan`。

不能整檔刪除。

如果要刪 RSI，只能移除 RSI 相關 route 與 helper，保留 revenue scan。

### Step 4：舊回測檔處理

RSI 回測檔可以移除或移到 archive。

候選：

- `backtest.py`
- `backtest_v2.py`
- `grid_search.py`
- `backtest_trades.csv`
- `backtest_equity.png`

但這一步需要使用者再次確認。

因為刪檔是破壞性動作。

### Step 5：文件同步

更新文件時要保留歷史結論：

- RSI 曾被測過
- 結果失效
- 禁止實盤
- 已移除或封存

不要把失敗教訓完全刪掉。

## 完成標準

必須同時滿足：

- 前端不再呼叫 `/api/scan`
- 前端沒有未使用的 `fetchScan` / `ScanResult` / `scanResults`
- 後端不再暴露 RSI 掃描功能
- `/api/revenue-scan` 仍正常
- 月營收掃描 UI 不受影響
- 雙刀配對 UI 不受影響
- 法人籌碼 UI 不受影響
- 文件清楚標記 RSI 已移除或封存

## 驗證指令

搜尋殘留：

```bash
rg -n "fetchScan|/api/scan|scanResults|ScanResult" frontend stock_report specs
```

前端檢查：

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

後端測試：

```bash
pytest
```

API 檢查：

```bash
curl -s https://finmind-production-23fd.up.railway.app/api/health
```

如有本機後端，也可測：

```bash
curl -s http://127.0.0.1:8000/api/revenue-scan
```

## 風險

最大風險是誤刪 `stock_report/api/scan.py` 整檔。

因為該檔同時包含月營收掃描。

正確做法是先拆清楚：

- RSI scan 是舊功能
- revenue scan 是目前主功能

不能一起刪。
