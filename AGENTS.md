# FinMind Agent Rules

## 啟動必讀

先讀：

1. `specs/mission.md`
2. `specs/current-state.md`
3. `specs/tech-stack.md`
4. `specs/roadmap.md`
5. `specs/backtest-standards.md`

做特定功能時，再讀對應檔案：

- `specs/features/*.md`

## 專案定位

這是台股量化研究、掃描與回測系統。

目前不是自動下單系統。

也不是財務建議工具。

沒有完整回測的策略，不可標記為可實盤。

## 工作規則

- 使用繁體中文。
- 回答短句、分層、少延伸。
- 先讀規格，再改檔案。
- 不碰 `.env`、token、憑證。
- 不碰 `trading/`，除非任務明確要求。
- 不自動部署。
- 不自動刪檔。
- 不順手重構。
- 不格式化整個專案。
- 新功能先寫 feature spec，再實作。
- 回測要符合 `specs/backtest-standards.md`。

## 策略規則

- 勝率不等於賺錢。
- 沒有完整回測，不進實盤。
- 回測要看 Sharpe、MaxDD、平均單筆報酬、交易成本與 Train/Test。
- 失敗策略要明確標記，不要留下會誤導人的殘留。

## 已知狀態

- 月營收動能是目前主策略。
- 法人籌碼掃描仍視為待做，即使已有程式雛形。
- 雙刀配對已跑過回測，但目前不達標。
- RSI 舊策略已廢棄，可規劃移除。

刪 RSI 前必讀：

- `specs/features/remove-rsi-legacy.md`

## 部署限制

- 前端部署：從專案根目錄執行 `./deploy.sh`。
- 後端部署：`railway service FinMind && railway up`。
- 不要從 `frontend/` 目錄執行 `railway up`。

## AI 分工

- Claude 適合：拆任務、寫任務單、整理文字。
- Codex 適合：讀 repo、改程式、補文件、驗證。
- Gemini 適合：研究、查資料、策略或 API 正確性審查。

簡單任務不需要多 AI。
