# Feature Spec: 可轉債監控

更新日期：2026-04-16

## 目標

建立可轉債監控掃描器。

此功能用來觀察距離賣回日小於 180 天、具銀行或金融機構擔保、且現價低於賣回價的可轉債。

這是套利候選監控工具。

不是財務建議，也不是實盤訊號。

## 資料來源

依序嘗試：

- MOPS 可轉債賣回資料：`https://mops.twse.com.tw/mops/web/ajax_t120sg01`
- TPEX 可轉債查詢：`https://www.tpex.org.tw/web/bond/conv_bond/cb_query.php?l=zh-tw&o=json&s=0,asc`

現價來源依序嘗試：

- TWSE CB 日報：`https://www.twse.com.tw/rwd/zh/bond/CB_DAILY?response=json&date=YYYYMMDD`
- TPEX CB 價格：`https://www.tpex.org.tw/web/bond/conv_bond/cb_price.php?l=zh-tw&o=json`

每次請求後 sleep 0.5 秒，降低被資料源阻擋的風險。

## 初版條件

全部成立才進結果：

- `0 < days_to_put < 180`
- 擔保類型含「銀行」或「金融機構」
- `cb_price > 0`
- `cb_price < put_price`
- 年化報酬大於 10%

年化報酬：

`(put_price - cb_price) / cb_price / (days_to_put / 365)`

## 回傳欄位

每筆結果：

- `bond_id`
- `stock_id`
- `stock_name`
- `put_date`
- `put_price`
- `cb_price`
- `days_to_put`
- `annualized_return`
- `guarantor`

Response 另含：

- `scanned_at`
- `total_scanned`
- `results`

## 排序

依 `annualized_return` 由大到小。

## 不做

初版不做：

- 自動下單
- 實盤建議
- 轉換價值估算
- 母股信用風險評分
- 完整回測

## 風險與停損

MOPS / TPEX 欄位可能變動。

若資料格式與預期差異過大，後端不可讓 API 500。

停損方式：

- 回傳空結果
- `total_scanned = 0`
- 保留錯誤訊息供後端 log 與 API 診斷

## 驗證方式

後端：

- `python3 -c "from stock_report.api import cb_scan; print('OK')"` 無錯誤
- `/api/cb-scan` 回傳 JSON
- 資料來源不可用時不得 500

前端：

- tab bar 出現「可轉債」
- 可刷新
- 載入中有狀態
- 空資料顯示「目前無符合條件的可轉債套利機會」
- 結果列點擊後可開母股頁
