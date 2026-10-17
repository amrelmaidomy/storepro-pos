$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if ($env:OS -ne 'Windows_NT') {
    throw 'Build this script on Windows.'
}

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (!(Test-Path $python)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create the Python environment.'
    }
}

# Install development and build requirements.
& $python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) {
    throw 'Dependency installation failed.'
}

# Run business-service tests together.
Write-Host "`nRunning business-service tests..."

& $python -m pytest -q `
    --ignore=tests/test_ui.py `
    --ignore=tests/test_pos_redesign.py

if ($LASTEXITCODE -ne 0) {
    throw 'Business-service tests failed.'
}

# Collect every GUI test, including parameterized cases.
Write-Host "`nCollecting GUI tests..."

$collection = @(
    & $python -m pytest `
        tests/test_ui.py `
        tests/test_pos_redesign.py `
        --collect-only -q
)

if ($LASTEXITCODE -ne 0) {
    $collection | ForEach-Object { Write-Host $_ }
    throw 'GUI test collection failed.'
}

$guiTests = @(
    $collection | Where-Object {
        $_ -match '^[^\s]+\.py::'
    }
)

if ($guiTests.Count -eq 0) {
    throw 'No GUI tests were collected.'
}

# Each GUI test gets a fresh Python/Tcl process.
$number = 0

foreach ($test in $guiTests) {
    $number++
    Write-Host "`nGUI test $number/$($guiTests.Count): $test"

    & $python -m pytest -q $test

    if ($LASTEXITCODE -ne 0) {
        throw "GUI test failed: $test"
    }
}

# Build only after all tests pass.
Write-Host "`nAll tests passed. Building StorePro..."

& $python -m PyInstaller --noconfirm --clean StorePro.spec

if ($LASTEXITCODE -ne 0) {
    throw 'Executable build failed.'
}

$exe = Join-Path $PSScriptRoot 'dist\StorePro\StorePro.exe'

if (!(Test-Path $exe)) {
    throw 'Build finished without the expected executable.'
}

Write-Host "`nBuild completed successfully."
Write-Host "EXE: $exe"
Write-Host 'Copy the entire dist\StorePro folder when transferring the app.'