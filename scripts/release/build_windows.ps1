param(
    [switch]$OneFile,
    [switch]$Console
)
$ErrorActionPreference = 'Stop'

# Choose a venv that has project deps installed (prefers one with PySide6)
$venvCandidates = @(
    '.venv313/Scripts/python.exe',
    '.venv/Scripts/python.exe'
)
$venv = $null
foreach ($py in $venvCandidates) {
    if (Test-Path $py) {
        try { & $py -c "import PySide6; print('ok')" | Out-Null; $venv = $py; break } catch {}
    }
}
if (-not $venv) {
    # fallback to any existing venv python
    foreach ($py in $venvCandidates) { if (Test-Path $py) { $venv = $py; break } }
}
if (-not $venv) { throw 'No virtual environment found (.venv or .venv313). Create one first.' }

# Ensure PyInstaller is available
$pyi_ok = $false
try { & $venv -c "import PyInstaller" | Out-Null; $pyi_ok = $true } catch {}
if (-not $pyi_ok) {
    Write-Host 'Installing PyInstaller into selected venv...'
    & $venv -m pip install -U pip wheel setuptools PyInstaller
}

# Build argument list
$opts = @('--clean','--noconfirm','--name','IncidentManagementAssistant','--paths','.')
if (-not $Console) { $opts += '--noconsole' }
if ($OneFile) { $opts += '--onefile' }

# Ensure Qt/PySide6 resources get collected
$opts += @('--collect-all','PySide6')

# Add data directories if present
$datadirs = @('data','profiles','settings','styles','reports','qml','notifications/assets')
foreach ($d in $datadirs) { if (Test-Path $d) { $opts += @('--add-data', "$d;$d") } }
if (Test-Path 'settings.json') { $opts += @('--add-data','settings.json;.') }

# Run PyInstaller
Write-Host "Using venv: $venv"
Write-Host 'Running PyInstaller...'
& $venv -m PyInstaller @opts 'main.py'

Write-Host "`nBuild complete. Output: dist/IncidentManagementAssistant/IncidentManagementAssistant.exe"