$ErrorActionPreference = "Stop"
$projectPath = Split-Path -Parent $PSScriptRoot
$env:SELFBANK_DB_BACKEND = "sqlserver"
$env:SELFBANK_SQLSERVER_CONNECTION = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=HomeAccounting;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
$env:SELFBANK_CORS_ORIGINS = "http://localhost:3000"
$env:NEXT_PUBLIC_SELFBANK_API_URL = "http://127.0.0.1:8000"

$apiProcess = Start-Process -FilePath "$projectPath\backend\.venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $projectPath -WindowStyle Hidden -PassThru
try {
    Set-Location $projectPath
    npm.cmd run dev
}
finally {
    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
}
