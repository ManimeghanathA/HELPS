param([int]$Port=5000)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { py -3 -m venv .venv }
& '.venv/Scripts/python.exe' -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& '.venv/Scripts/python.exe' -m flask --app app run --host 127.0.0.1 --port $Port
