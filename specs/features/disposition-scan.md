# Feature Spec: 處置股追蹤

更新日期：2026-04-16

## 目標

建立處置股追蹤掃描器。

此功能用來觀察即將解除處置、且處置期間跌幅未明顯失控的上市股票。

這是研究與追蹤工具。

不是實盤買進訊號。

## 資料來源

TWSE 免費公開資料。

使用官方處置有價證券資料：

- 指定端點：`https://www.twse.com.tw/zh/api/getDisposition?response=json`
- 目前可用 JSON 端點：`https://www.twse.com.tw/announcement/punish?response=json`

若指定端點回傳非 JSON，後端可使用同站可用端點作為 fallback。

## 初版條件

三個條件同時成立：

- 距離解除處置小於等於 5 天
- 處置期間跌幅大於 -8%
- 處置期間均量小於處置前 20 日均量的 50%

若 TWSE 處置 API 沒有量能欄位，初版固定：

- `volume_ratio = 0.0`

若價格資料不足，初版固定：

- `price_change_during = 0.0`

## 回傳欄位

- `stock_id`
- `stock_name`
- `disposition_start`
- `disposition_end`
- `days_to_release`
- `price_change_during`
- `volume_ratio`

Response 另含：

- `scanned_at`
- `total_scanned`
- `results`

## 不做

初版不做：

- 自動下單
- 實盤建議
- 上櫃處置股整合
- 處置原因細部分類
- 完整回測

## 驗證方式

後端：

- `python3 -c "from stock_report.api.disposition import router"` 無錯誤
- `/api/disposition-scan` 可回傳 JSON
- TWSE 資料為空或欄位不足時不 crash

前端：

- `disposition` tab 可切換
- 可刷新
- 載入中有狀態
- 空資料有明確提示
- 結果列點擊後可開股票頁

## 風險

處置股涉及交易限制。

沒有完整回測前，不可視為可實盤策略。
