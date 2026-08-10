# SelfBank Python API

FastAPI 後端，支援 SQL Server 或 SQLite，提供交易、固定扣款、密碼保護 PDF 匯入去重與交易紀錄 PDF 匯出 API。

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt
backend/.venv/Scripts/uvicorn backend.app.main:app --reload --port 8000
```

啟動後可在 `http://localhost:8000/docs` 查看 API 文件。資料庫預設建立於 `backend/data/selfbank.db`；正式部署時應透過環境變數設定資料庫路徑與允許的前端網域。

本機 SQL Server 已使用 Windows Authentication 設定為 `localhost:1433` 的 `SelfBank` 專用資料庫。從專案根目錄執行 `powershell -ExecutionPolicy Bypass -File scripts/start-selfbank.ps1`，會同時啟動 Python API 與前端；連線字串不含帳號或密碼。`master` 僅用於首次建立專用資料庫，不保存記帳資料。

前端若要使用 PDF 匯入或匯出，請設定 `NEXT_PUBLIC_SELFBANK_API_URL=http://localhost:8000` 後重新建置。PDF 密碼是每次請求的必填欄位，只在記憶體中解密該次檔案，不會保存到設定檔、資料庫或日誌。目前支援既有銀行交易明細表格，以及每列為 `YYYY/MM/DD 名稱 金額` 的通用文字 PDF；掃描影像及其他版型需另加 OCR 或專用解析規則。交易紀錄可透過 `/exports/pdf` 匯出為七欄 PDF 表格。
