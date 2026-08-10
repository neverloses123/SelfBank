# SelfBank 本機啟動說明

SelfBank 使用以下本機服務：

- 網站：`http://localhost:3000`
- Python API：`http://127.0.0.1:8000`
- SQL Server：`localhost:1433`
- 資料庫：`SelfBank`
- 驗證：Windows Authentication

## 一、啟動前確認

1. 確認 SQL Server Express 已啟動。
2. 確認專案位於 `C:\Users\alexl\OneDrive\桌面\project1`。
3. 確認已安裝 Node.js，且 `backend\.venv` Python 環境存在。
4. 不需要開放 1433、3000 或 8000 到外部網路。

可用 PowerShell 確認 SQL Server：

```powershell
Get-Service MSSQL`$SQLEXPRESS
```

狀態應顯示為 `Running`。

## 二、一般啟動方式

開啟 PowerShell，執行：

```powershell
cd "C:\Users\alexl\OneDrive\桌面\project1"
powershell -ExecutionPolicy Bypass -File scripts\start-selfbank.ps1
```

等待終端顯示網站已啟動後，開啟：

```text
http://localhost:3000
```

這個啟動腳本會：

1. 設定 SQL Server Windows Authentication 連線。
2. 在背景啟動 FastAPI，使用 `127.0.0.1:8000`。
3. 啟動 SelfBank 網站，使用 `localhost:3000`。
4. 關閉前端終端時，一併停止由腳本啟動的 API。

## 三、確認是否正常

API 健康檢查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

正常結果：

```text
status
------
ok
```

確認網站：

```powershell
Invoke-WebRequest http://localhost:3000 -UseBasicParsing | Select-Object StatusCode
```

正常狀態碼為 `200`。網站左側應顯示「已連接本機 SQL Server」。

## 四、停止網站

回到執行 `start-selfbank.ps1` 的 PowerShell 視窗，按：

```text
Ctrl + C
```

## 五、常見問題

### 無法連接 SQL Server

```powershell
Start-Service MSSQL`$SQLEXPRESS
Test-NetConnection localhost -Port 1433
```

`TcpTestSucceeded` 應為 `True`。

### 3000 或 8000 已被使用

```powershell
Get-NetTCPConnection -LocalPort 3000,8000 -State Listen | Select-Object LocalPort,OwningProcess
```

先確認程序確實屬於 SelfBank，再關閉原本的 SelfBank PowerShell 視窗；不要任意停止其他程式。

### Python 套件遺失

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 前端套件遺失

```powershell
npm.cmd install
```

## 六、安全提醒

- 不要將 SQL Server 1433 Port 開放到網際網路。
- 不要把銀行 PDF 密碼寫進 README、環境檔、GitHub 或程式碼。
- `.env.local` 僅保存本機 API 網址，不保存 Windows 或資料庫密碼。
- 線上 SelfBank 網址無法寫入你電腦上的 localhost SQL Server；需要記帳時請使用 `http://localhost:3000`。
