# Feature Spec: 雙刀配對策略重新驗證

更新日期：2026-04-16

## 目標

重新驗證雙刀配對策略是否值得保留為策略候選。

目前掃描器已存在，回測也曾執行。

但目前結果不達標，不能直接視為可實盤策略。

## 目前狀態

已存在：

- `stock_report/api/pair_scan.py`
- `/api/pair-scan`
- `backtest_pairs.py`
- `grid_search_pairs.py`
- `pairs_backtest_trades.csv`
- `pairs_backtest_equity.png`

目前快速統計：

- 交易數：1280
- 勝率：約 44.14%
- 平均單筆報酬：約 -0.18%

2026-04-16 重新驗證：

- baseline：`python3 backtest_pairs.py`
- grid search：`python3 grid_search_pairs.py`
- 測試參數：EntryZ 1.5 / 2.0 / 2.5，MaxHold 15 / 20 / 30，StopLoss 5% / 8% / 10%

baseline Test：

- Sharpe：-0.84
- MaxDD：-19.33%
- 勝率：49.61%
- 交易數：510

grid search 最佳 Train Sharpe 組合：

- EntryZ=2.5
- MaxHold=30
- StopLoss=8%
- Train：Sharpe -0.29，MaxDD -10.1%，勝率 53.7%，交易 121 筆
- Test：Sharpe +0.01，MaxDD -5.2%，勝率 60.4%，交易 217 筆
- Test 平均單筆報酬：約 +0.49%

grid search 最佳 Test Sharpe 組合：

- EntryZ=2.5
- MaxHold=20
- StopLoss=5%
- Test Sharpe：約 +0.10
- Test MaxDD：約 -4.9%
- Test 勝率：約 60.7%
- 仍未達 Sharpe > 0.5

輸出檔：

- `pairs_backtest_trades.csv`
- `pairs_backtest_equity.png`
- `pairs_gs_results.csv`
- `pairs_gs_best_equity.png`
- `pairs_gs_best_trades.csv`

目前結論：

- 結果不達標
- 不得作為實盤訊號
- 可保留為研究工具
- 若要繼續研究，應優先檢查交易成本、放空可行性、pair selection 與產業群聚問題

## 需要驗證的問題

- 目前交易成本假設是否正確
- spread 偏離度計算是否合理
- 進場 z-score 是否太寬或太窄
- 持有天數是否太長
- stop loss 是否太鬆或太緊
- 是否有流動性不足問題
- 是否受產業群聚或單一族群污染
- 是否只在 Train 有效，Test 失效

## 參數搜尋方向

可測：

- Entry Z
- MaxHold
- StopLoss
- correlation threshold
- turnover threshold
- recent days
- lookback window

建議先跑 `grid_search_pairs.py`。

但跑之前要確認：

- 輸出檔名
- Train / Test 切分
- 成功標準
- 是否會覆蓋現有結果

## 成功標準

Test set 至少要達到：

- Sharpe > 0.5
- MaxDD < 20%
- 勝率 > 45%
- 平均單筆報酬扣成本後為正

如果只達到勝率，但平均報酬仍為負，不算通過。

如果交易數太少，也不算通過。

## 可能結果

### 通過

若通過，保留掃描器，並把策略升級為候選策略。

仍需標記不是實盤自動交易。

### 待研究

若接近通過，可保留為研究工具。

前端應避免給出太像買賣建議的文案。

### 失敗

若多組參數都不通過，應保留失敗結論。

可考慮：

- 隱藏前端 tab
- 改成研究工具
- 移除策略

## 不做

本任務不做：

- 改法人籌碼掃描
- 改月營收策略
- 改前端 UI 設計
- 直接部署
- 實盤下單

## 驗證輸出

重新驗證後至少要有：

- trades CSV
- equity curve
- summary 指標
- Train / Test 分段
- 結論：通過、待研究、失敗

結果要同步更新：

- `specs/current-state.md`
- `specs/roadmap.md`
- 必要時更新前端文案
