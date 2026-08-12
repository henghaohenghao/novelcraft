param(
    [switch]$Install,
    [switch]$NoCheck,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step {
    param([string]$Message)
    Write-Host ">>> $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-Port {
    param([string]$ServiceName, [string]$HostName, [int]$Port, [bool]$Required = $false)
    try {
        $conn = New-Object System.Net.Sockets.TcpClient
        $conn.Connect($HostName, $Port)
        $conn.Close()
        Write-Host "  [OK] $ServiceName ($HostName`:$Port)" -ForegroundColor Green
        return $true
    } catch {
        if ($Required) {
            Write-Host "  [X]  $ServiceName ($HostName`:$Port) 未运行（必需）" -ForegroundColor Red
        } else {
            Write-Host "  [-]  $ServiceName ($HostName`:$Port) 未运行（可选，将降级）" -ForegroundColor DarkYellow
        }
        return $false
    }
}

if ($Install) {
    Write-Step "检查依赖..."

    if (-not (Test-Command "python")) {
        Write-Host "[X] 请先安装 Python 3.11+: https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
    Write-Step "已安装: $(python --version 2>&1)"

    if (-not (Test-Command "node")) {
        Write-Host "[X] 请先安装 Node.js 18+: https://nodejs.org/" -ForegroundColor Red
        exit 1
    }
    Write-Step "已安装: Node.js $(node --version)"

    Write-Step "升级 pip..."
    python -m pip install --upgrade pip

    Write-Step "安装 Python 依赖（首次会下载 PyTorch / sentence-transformers，耗时较久）..."
    pip install -r "$ProjectRoot\requirements.txt"

    Write-Step "安装前端依赖..."
    Push-Location "$ProjectRoot\frontend"
    npm install
    Pop-Location

    Write-Step "依赖安装完成。下一步：编辑 .env 填入 NOVELCRAFT_LLM_API_KEY，然后运行 .\start_windows.ps1"
    exit 0
}

if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Step "创建 .env 配置文件..."
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-Warn "请编辑 .env，至少填写 NOVELCRAFT_LLM_API_KEY 后再启动"
    exit 0
}

Write-Step "===== NovelCraft V1.0 Windows 启动 ====="

if (-not $NoCheck) {
    Write-Step "检查可选服务（未启动会自动降级，不影响 SQLite 模式跑通）..."
    [void](Test-Port -ServiceName "PostgreSQL" -HostName "localhost" -Port 5432)
    [void](Test-Port -ServiceName "Neo4j"      -HostName "localhost" -Port 7687)
    [void](Test-Port -ServiceName "Qdrant"     -HostName "localhost" -Port 6333)
    [void](Test-Port -ServiceName "Redis"      -HostName "localhost" -Port 6379)
    Write-Host ""
}

if (-not $FrontendOnly) {
    Write-Step "在新窗口启动后端 (FastAPI on :8000)..."
    $backendCmd = "cd /d `"$ProjectRoot`" && set PYTHONPATH=$ProjectRoot && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCmd
}

if (-not $BackendOnly) {
    Start-Sleep -Seconds 2
    Write-Step "在新窗口启动前端 (Next.js on :3000)..."
    $frontendCmd = "cd /d `"$ProjectRoot\frontend`" && npm run dev"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCmd
}

Write-Host ""
Write-Step "============================================================"
Write-Step "  NovelCraft V1.0 已在新窗口启动！"
Write-Step "  前端:    http://localhost:3000"
Write-Step "  后端:    http://localhost:8000"
Write-Step "  API 文档: http://localhost:8000/docs"
Write-Step "  健康检查: http://localhost:8000/api/health"
Write-Step "============================================================"
Write-Host ""
Write-Step "关闭对应的命令行窗口即可停止服务。"
