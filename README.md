# SelfBank v1

SelfBank 是個人使用的視覺化記帳 Web App。資料預設保存在使用者目前的瀏覽器，不會要求或儲存網路銀行密碼。

## v1 功能

- 收入、支出與結餘儀表板
- 支出分類、七日趨勢與每月預算
- 新增交易及收入／支出篩選
- 手機載具條碼保存與快速出示
- 銀行 CSV 匯入（`日期,名稱,金額,類型,分類`）
- 依金額、店家與三日內載具發票自動去除重複消費
- 每月固定扣款管理、下次扣款日與每月合計
- Google／Apple 官方帳號連結的設定入口（需開發者憑證）
- 手機、平板與桌面響應式版面

## 執行

```bash
npm install
npm run dev
```

開啟 `http://localhost:3000`。正式檢查可執行 `npm test` 與 `npm run lint`。

## 安全範圍

v1 不會直接登入銀行，也尚未呼叫財政部電子發票正式 API。未來串接必須使用官方授權流程、伺服器端金鑰保存與銀行核准的 Open Banking／合作 API。

Google 帳號連結需要 OAuth Client ID。Apple 網頁登入需要 Apple Developer、Services ID、私鑰與正式網域；Apple 不提供讀取個人 Apple ID 全部 App Store 訂閱的通用 API。
