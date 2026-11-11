# Windows one-click installer / launcher. Windows PowerShell 5.1 compatible.
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Run', 'InstallRun', 'Test')]
    [string]$Mode = 'InstallRun'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

function Show-Info([string]$Message) { Write-Host "[Diagram Editor] $Message" -ForegroundColor Cyan }
function Show-OK([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }

function Invoke-Checked([string]$Executable, [string[]]$Arguments, [string]$Description) {
    Show-Info $Description
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "작업 실패 (종료 코드: $LASTEXITCODE): $Description"
    }
}

function Test-PythonCandidate([string]$Executable, [string[]]$Prefix) {
    try {
        $VersionCheck = 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)'
        & $Executable @Prefix '-c' $VersionCheck *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-SystemPython {
    $Py = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($null -ne $Py) {
        foreach ($Version in @('-3.12', '-3.13', '-3.11', '-3')) {
            if (Test-PythonCandidate $Py.Source @($Version)) {
                return @{ Exe = $Py.Source; Args = @($Version) }
            }
        }
    }
    foreach ($Name in @('python.exe', 'python3.exe')) {
        $Command = Get-Command $Name -ErrorAction SilentlyContinue
        if ($null -ne $Command -and $Command.Source -notmatch '\\WindowsApps\\' -and (Test-PythonCandidate $Command.Source @())) {
            return @{ Exe = $Command.Source; Args = @() }
        }
    }
    # winget-installed Python may not appear on PATH in an already-running shell.
    foreach ($Directory in @((Join-Path $env:LOCALAPPDATA 'Programs\Python'), $env:ProgramFiles)) {
        foreach ($Version in @('Python312', 'Python313', 'Python311', 'Python314')) {
            $Candidate = Join-Path (Join-Path $Directory $Version) 'python.exe'
            if ((Test-Path $Candidate) -and (Test-PythonCandidate $Candidate @())) {
                return @{ Exe = $Candidate; Args = @() }
            }
        }
    }
    return $null
}

function Ensure-SystemPython {
    $Python = Find-SystemPython
    if ($null -ne $Python) { return $Python }

    $Winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
    if ($null -eq $Winget) {
        throw 'Python 3.11~3.14가 없습니다. https://www.python.org/downloads/windows/ 에서 Python 3.12를 설치하거나 Windows App Installer(winget)를 설치하세요.'
    }
    Write-Host ''
    Write-Host '지원되는 Python(3.11~3.14)이 발견되지 않았습니다.' -ForegroundColor Yellow
    $Answer = Read-Host 'winget으로 Python 3.12를 설치할까요? (Y/N)'
    if ($Answer -notmatch '^(y|yes)$') {
        throw 'Python 설치가 취소되었습니다. Python 3.12를 설치한 후 다시 실행하세요.'
    }
    Invoke-Checked $Winget.Source @('install', '--id', 'Python.Python.3.12', '--exact', '--source', 'winget', '--scope', 'user', '--accept-package-agreements', '--accept-source-agreements') 'Python 3.12 설치'
    $Python = Find-SystemPython
    if ($null -eq $Python) {
        throw 'Python이 설치되었지만 현재 콘솔에서 찾지 못했습니다. Windows 터미널을 새로 열거나 로그아웃 후 BAT를 다시 실행하세요.'
    }
    return $Python
}

function Test-Environment {
    if (-not (Test-Path $VenvPython)) {
        Show-Info '가상환경 Python 실행 파일이 없습니다.'
        return $false
    }
    try {
        # Windows PowerShell 5.1 can strip embedded double quotes from Python -c
        # arguments. Use a quote-free probe and show any Python traceback.
        $Probe = 'import PyQt6.QtCore; import diagram_editor; import diagram_editor.presentation.pyqt.main_window'
        & $VenvPython '-c' $Probe
        if ($LASTEXITCODE -ne 0) {
            Write-Host '[ERROR] PyQt6 또는 프로젝트 import 검증 중 위의 Python 오류가 발생했습니다.' -ForegroundColor Red
            return $false
        }
        return $true
    } catch {
        Write-Host "[ERROR] Python 환경 검증 실패: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Ensure-Venv {
    if (Test-Path $VenvPython) { return }
    $Python = Ensure-SystemPython
    $CallArgs = @($Python.Args) + @('-m', 'venv', (Join-Path $ProjectRoot '.venv'))
    Invoke-Checked $Python.Exe $CallArgs '프로젝트 전용 Python 가상환경(.venv) 생성'
    if (-not (Test-Path $VenvPython)) {
        throw '가상환경 생성이 완료되지 않았습니다. Python 설치에 venv 모듈이 있는지 확인하세요.'
    }
}

function Install-Dependencies([bool]$IncludeTests) {
    Ensure-Venv
    $Target = if ($IncludeTests) { '.[test]' } else { '.' }
    # Editable install resolves dependencies from pyproject.toml into the local venv.
    Invoke-Checked $VenvPython @('-m', 'pip', 'install', '-e', $Target) '프로젝트와 필요한 패키지 설치/업데이트 (최초 설치 시 인터넷 필요)'
    if (-not (Test-Environment)) {
        throw '설치는 완료되었지만 PyQt6 또는 프로젝트 import 검증에 실패했습니다.'
    }
    Show-OK '설치 및 실행 환경 점검 완료'
}

try {
    if (-not (Test-Path (Join-Path $ProjectRoot 'pyproject.toml'))) {
        throw 'pyproject.toml을 찾을 수 없습니다. ZIP을 전체 압축 해제한 뒤 프로젝트 폴더 안에서 BAT를 실행하세요.'
    }
    Push-Location $ProjectRoot
    try {
        Show-Info "프로젝트: $ProjectRoot"
        switch ($Mode) {
            'Install' {
                Install-Dependencies $false
                Show-OK '설치가 완료되었습니다. Start.bat로 앱을 실행하세요.'
            }
            'Run' {
                if (-not (Test-Environment)) { Install-Dependencies $false }
                Invoke-Checked $VenvPython @('-m', 'diagram_editor.main') '다이어그램 편집기 실행'
            }
            'InstallRun' {
                Install-Dependencies $false
                Invoke-Checked $VenvPython @('-m', 'diagram_editor.main') '다이어그램 편집기 실행'
            }
            'Test' {
                Install-Dependencies $true
                Invoke-Checked $VenvPython @('-m', 'pytest', '-q', 'tests/unit', 'tests/integration') '단위/통합 테스트 실행'
                Show-OK '테스트 완료'
            }
        }
    } finally {
        Pop-Location
    }
    exit 0
} catch {
    Write-Host ''
    Write-Host '[ERROR] 설치 또는 실행에 실패했습니다.' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host '위쪽에 표시된 Python 오류(Traceback)를 확인하세요. Diagnose.bat로 각 import를 별도 검사할 수 있습니다.' -ForegroundColor Yellow
    Write-Host '설치가 이미 성공한 경우에는 Start.bat로 실행해 보세요. 재설치는 필요하지 않을 수 있습니다.' -ForegroundColor Yellow
    exit 1
}
