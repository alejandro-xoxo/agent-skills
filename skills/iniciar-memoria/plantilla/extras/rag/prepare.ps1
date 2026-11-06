# SPDX-License-Identifier: LicenseRef-Proprietary - Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
<#
.SYNOPSIS
  Turns on automatic retrieval (local RAG) for this project: Python environment, library, index, hooks and server.

.DESCRIPTION
  Run it once per project; it can be repeated safely. It does, in order:
    1. Looks for a compatible Python (3.10 to 3.13, through the "py" launcher). On the machine where it was tested,
       Python 3.15 did not work because onnxruntime did not publish a version for it.
    2. Creates the .rag\.venv environment and installs fastembed and numpy.
    3. Builds the index of the vault and of docs\. The first time it downloads the model (about 0.6 GB) to
       %USERPROFILE%\.cache\rag-models, which all projects share.
    4. Registers the Claude Code hooks in .claude\settings.local.json (merging with what is already there, with a backup).
    5. Starts the local server.
  The vectors are computed on this machine. Only the libraries and the model are downloaded.
  It needs Windows with PowerShell and the "py" launcher. The engine (rag.py) is written to work on other systems, but it was not tested on them.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .rag\prepare.ps1
#>
$ErrorActionPreference = "Stop"
$rag = $PSScriptRoot
$ragScript = Join-Path $rag "rag.py"
if (-not (Test-Path -LiteralPath $ragScript)) { throw "Cannot find rag.py in $rag" }

Write-Host "1/5 Looking for a compatible Python..."
$python = $null
foreach ($v in @("3.12", "3.13", "3.11", "3.10")) {
  try {
    $found = (& py "-$v" -c "import sys; print(sys.executable)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $found) { $python = ([string]$found).Trim(); Write-Host "    Python ${v}: $python"; break }
  } catch { }
}
if (-not $python) {
  throw "Cannot find Python 3.10 to 3.13 with the 'py' launcher. Install Python 3.12 from python.org and run this again."
}

$venv = Join-Path $rag ".venv"
$py = Join-Path $venv "Scripts\python.exe"
Write-Host "2/5 Python environment and library installation (fastembed, numpy)..."
if (-not (Test-Path -LiteralPath $py)) {
  & $python -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw "Could not create the environment in $venv" }
}
& $py -m pip install --quiet --disable-pip-version-check fastembed numpy
if ($LASTEXITCODE -ne 0) { throw "Could not install fastembed. Check the connection and run this again." }

$env:PYTHONUTF8 = "1"
Write-Host "3/5 Building the index (the first time it downloads the model and can take several minutes)..."
& $py $ragScript index
if ($LASTEXITCODE -ne 0) { throw "Building the index failed." }

Write-Host "4/5 Registering the Claude Code hooks..."
& $py $ragScript hooks
if ($LASTEXITCODE -ne 0) { throw "Could not register the hooks." }

Write-Host "5/5 Starting the local server..."
& $py $ragScript start

Write-Host ""
Write-Host "Done. Open /hooks once or restart the agent session so it loads the hooks."
Write-Host "To turn automatic retrieval off: environment variable RAG_DISABLE=1."
Write-Host "To measure its quality: copy .rag\evaluation.example.json as evaluation.json, put questions of your own in it and run 'rag.py evaluate'."