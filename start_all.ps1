# ============================================================
#  一键启动脚本
#  服务列表：
#    [1] 主项目后端     http://127.0.0.1:5000
#    [2] 主项目前端     http://localhost:3001
#    [3] Demo 后端      http://127.0.0.1:5100
#    [4] Demo 前端      http://localhost:3002
# ============================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON = "D:\anaconda\python.exe"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  智能仿真报告生成工具 - 一键启动" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── 清理旧进程 ──────────────────────────────────────────────
Write-Host "[1/4] 清理旧进程..." -ForegroundColor Yellow

$killed = @()
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match 'python' -and (
        $_.CommandLine -match 'app_v2\.py' -or
        $_.CommandLine -match 'integration_demo.*app\.py'
    )
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $killed += $_.ProcessId
}
if ($killed.Count -gt 0) {
    Write-Host "   已终止进程: $($killed -join ', ')" -ForegroundColor Gray
} else {
    Write-Host "   无旧进程需要清理" -ForegroundColor Gray
}

Start-Sleep -Milliseconds 500

# ── 启动主项目后端 ───────────────────────────────────────────
Write-Host "[2/4] 启动主项目后端  (http://127.0.0.1:5000)..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '[ 主项目后端 ]' -ForegroundColor Cyan; & '$PYTHON' server\app_v2.py"
) -WindowStyle Normal

Start-Sleep -Milliseconds 800

# ── 启动 Demo 后端 ───────────────────────────────────────────
Write-Host "[3/4] 启动 Demo 后端  (http://127.0.0.1:5100)..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT'; Write-Host '[ Demo 后端 ]' -ForegroundColor Magenta; & '$PYTHON' integration_demo\backend\app.py"
) -WindowStyle Normal

Start-Sleep -Milliseconds 800

# ── 启动主项目前端 ───────────────────────────────────────────
Write-Host "[4/4] 启动主项目前端  (http://localhost:3001)..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT\frontend'; Write-Host '[ 主项目前端 ]' -ForegroundColor Green; npm run dev"
) -WindowStyle Normal

Start-Sleep -Milliseconds 800

# ── 启动 Demo 前端 ───────────────────────────────────────────
Write-Host "[5/4] 启动 Demo 前端  (http://localhost:3002)..." -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT\integration_demo\frontend'; Write-Host '[ Demo 前端 ]' -ForegroundColor Magenta; npm run dev"
) -WindowStyle Normal

# ── 等待后端就绪后打开浏览器 ────────────────────────────────
Write-Host ""
Write-Host "等待后端启动..." -ForegroundColor Gray
$timeout = 30
$elapsed = 0
$ready = $false
while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:5100/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}

Write-Host ""
if ($ready) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  所有服务已就绪！正在打开演示页面..." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Start-Process "http://localhost:3002"
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  服务启动中，请稍等后手动打开：" -ForegroundColor Yellow
    Write-Host "    Demo 演示入口  →  http://localhost:3002" -ForegroundColor White
    Write-Host "    主项目网页端   →  http://localhost:3001" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Yellow
}
Write-Host ""
