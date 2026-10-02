Write-Host "========================================="
Write-Host "Starting Nexus Pure Local Voice AI"
Write-Host "========================================="

$ErrorActionPreference = "SilentlyContinue"
Stop-Process -Name "llama-server" -Force
Stop-Process -Name "python" -Force
$ErrorActionPreference = "Stop"

# 1. Start the Llama-cpp Server
Write-Host "`n[1] Starting Local Llama 3.2 Server on Port 8000..."
$ModelPath = "C:\Users\sb791\.cache\huggingface\hub\models--bartowski--Llama-3.2-3B-Instruct-GGUF\snapshots\5ab33fa94d1d04e903623ae72c95d1696f09f9e8\Llama-3.2-3B-Instruct-Q4_K_M.gguf"

if (-Not (Test-Path $ModelPath)) {
    Write-Error "Could not find the Llama model at $ModelPath"
    exit 1
}

Start-Process -FilePath "llama-server" -ArgumentList "-m `"$ModelPath`" --port 8000 --host 0.0.0.0" -NoNewWindow -PassThru

# Give the server a few seconds to initialize
Write-Host "Waiting 10 seconds for Llama to load..."
Start-Sleep -Seconds 10

# 2. Start the Background Incremental Scraper
Write-Host "`n[2] Starting Background Data Scraper..."
Start-Process -FilePath "python" -ArgumentList "incremental_scraper.py" -WindowStyle Hidden

# 3. Start the Standalone Python Voice Bot
Write-Host "`n[3] Starting the Microphone & Voice Bot..."
python nexus_voice.py
