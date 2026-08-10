# SelfBank Python API

FastAPI 與 SQLite 後端，提供交易、固定扣款、銀行 CSV 與密碼保護 PDF 去重 API。

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt
backend/.venv/Scripts/uvicorn backend.app.main:app --reload --port 8000
```

啟動後可在 `http://localhost:8000/docs` 查看 API 文件。資料庫預設建立於 `backend/data/selfbank.db`；正式部署時應透過環境變數設定資料庫路徑與允許的前端網域。

前端若要使用 PDF 匯入，請設定 `NEXT_PUBLIC_SELFBANK_API_URL=http://localhost:8000` 後重新建置。PDF 密碼是每次請求的必填欄位，只在記憶體中解密該次檔案，不會保存到設定檔、資料庫或日誌。目前支援可選取文字、每列為 `YYYY/MM/DD 名稱 金額` 的 PDF；掃描影像及不同銀行版型需另加 OCR 或專用解析規則。
