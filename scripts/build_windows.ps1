$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Main virtual environment not found: $python"
}

Write-Host 'Installing build requirements...'
& $python -m pip install -r (Join-Path $root 'requirements.txt') -r (Join-Path $root 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

Write-Host 'Running full test suite...'
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build aborted.' }

Write-Host 'Building Windows executable...'
& $python -m PyInstaller `
    --noconfirm --clean --windowed `
    --name SmartDrillPro `
    --add-data "$root\resources;resources" `
    --add-data "$root\THIRD_PARTY_NOTICES.md;." `
    --hidden-import PySide6.QtCore `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtWidgets `
    --hidden-import serial.tools.list_ports `
    (Join-Path $root 'main.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

Write-Host "Build complete: $root\dist\SmartDrillPro"
Write-Host 'The FlatCAM worker is NOT bundled. Install it separately as described in INSTALL.md.'
