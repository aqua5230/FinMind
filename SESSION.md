# SESSION.md — FinMind 專案狀態

更新時間：2026-04-04

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
- 部署：`cd frontend && railway up`

---

## 當前階段：前端 K 線圖

| 項目 | 狀態 | 備注 |
|------|------|------|
| Railway 部署設定 | ✅ 完成 | Root Dir = frontend，移除 railway.json build 區塊 |
| 後端價格 API 快取 | ✅ 完成 | TTLCache 200 筆，10 分鐘 |
| 零價格過濾 | ✅ 完成 | OHLC 任一為 0 就丟棄 |
| K 線圖 loading skeleton | ✅ 完成 | 格線 + 假 K 棒 |
| MACD/RSI 壓縮 candle 問題 | ✅ 完成 | applyPaneHeight 直接設 _drawPanes 高度 |
| 港式 K 線（moomoo 樣式） | ✅ 完成（本地） | registerIndicator 自訂 draw |
| 空心/港式 crash 修復 | ✅ 完成（本地） | 移除 priceMark.last.compareRule，加 null 防呆 |
| K 線圖空白不顯示 | 🔄 調查中 | Codex 跑完，結果待確認 |
| 週期改 dropdown | ✅ 完成（本地） | 日/週/月 dropdown |
| 按鈕純文字風格 | ✅ 完成（本地） | 選中才有背景 |
| **Deploy 最新改動** | ❌ 未做 | crash 修 + UI 改動都還沒上 Railway |
| Header 大股價顯示 | ❌ 未做 | |
| Hover-only OHLCV tooltip | ❌ 未做 | |
| Morandi 指標線發光效果 | ❌ 未做 | |

---

## 工作流規則（嚴格執行）

- Claude 只出任務單，不讀程式碼、不自己改
- 程式碼任務 → `codex exec --full-auto --skip-git-repo-check "..."`
- 驗收 → Gemini 正確性 + Codex 範圍（參考 AI客服 的 SKILL.md）
- 不 push，需使用者確認

---

## 下一步

1. 確認 K 線空白根因（Codex 查完的結果）
2. Deploy 到 Railway（`cd frontend && railway up`）
3. 測試空心/港式不再 crash、圖表有顯示
4. 繼續 Header + Hover OHLCV
