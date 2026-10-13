$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build this script on Windows.' }
if (!(Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean StorePro.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Write-Host 'Output: dist\StorePro\StorePro.exe. Copy the whole StorePro folder to the target PC.'
