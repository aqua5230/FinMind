# FinMind — 台股量化研究與掃描系統

一套台股量化研究、回測與掃描系統。以程式化策略尋找市場線索，用回測驗證期望值，
再把通過驗證的策略做成掃描器，搭配前端量化終端機輔助觀察。

> 定位為量化研究工作台，非自動下單系統，亦非財務建議工具。

---

## 功能特色

- **月營收動能掃描** — 現役主策略，掃描營收動能候選股。
- **多種研究型掃描器** — 法人籌碼（TWSE T86）、處置股、籌碼面、可轉債（TPEX）、配對策略。
- **回測框架** — 強制檢視 Sharpe、MaxDD、Profit Factor、Train/Test 分段；未通過完整回測的策略不上主掃描器。
- **個股報告與即時報價** — CLI 產生個股報告；Fugle WebSocket 即時報價。
- **量化終端機前端** — 整合所有掃描器的觀察介面與 K 線圖表。

---

## 技術棧

| 層 | 技術 |
|---|---|
| 後端 | Python · FastAPI · APScheduler · PostgreSQL |
| 前端 | Next.js · React · TypeScript · Tailwind CSS |
| 圖表 | klinecharts · lightweight-charts |
| 資料源 | TWSE · TPEX · FRED · Fugle |

---

## 系統架構

```
前端（Next.js 量化終端機）
        │ REST
        ▼
後端（FastAPI）
 ├─ api/          各掃描器 route（營收動能 / 法人 / 處置股 / 籌碼 / 可轉債 / 配對）
 ├─ data/         價格與營收同步、股票清單
 ├─ services/     策略與報告邏輯
 └─ APScheduler   每日價格同步與訊號結算、每月營收同步
        │
        ▼
   PostgreSQL（價格 / 訊號 / 月營收）
```

---

## 快速啟動

後端（需設定 `DATABASE_URL`）：

```bash
uvicorn main:app --reload
python3 -m pytest
python3 -m stock_report.cli report 2330 --year 2024   # CLI 個股報告
```

前端：

```bash
cd frontend
npm run dev
```

---

## 回測

```bash
python3 backtest_revenue.py    # 月營收動能（現役主策略）
python3 backtest_pairs.py      # 配對策略（研究中）
```

---

## 策略紀律

- 勝率不等於賺錢；策略以 Sharpe、MaxDD、Profit Factor、Train/Test 分段綜合評估。
- 未通過完整回測的策略不標記為可實盤、不上前端主掃描器。
- 事件型資料遵守公告日邏輯，不使用未來資訊。
