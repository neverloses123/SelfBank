# SelfBank Python API

FastAPI 與 SQLite 後端，提供交易、固定扣款及銀行 CSV 去重 API。

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt
backend/.venv/Scripts/uvicorn backend.app.main:app --reload --port 8000
```

啟動後可在 `http://localhost:8000/docs` 查看 API 文件。資料庫預設建立於 `backend/data/selfbank.db`；正式部署時應透過環境變數設定資料庫路徑與允許的前端網域。
