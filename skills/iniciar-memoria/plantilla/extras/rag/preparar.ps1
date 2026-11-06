# SPDX-License-Identifier: MIT
# Copyright (c) 2026 alejandro-xoxo
<#
.SYNOPSIS
  Activa la recuperacion automatica (RAG local) de este proyecto: entorno de Python, libreria, indice, ganchos y servidor.

.DESCRIPTION
  Se ejecuta una vez por proyecto y se puede repetir sin problema. Hace, en orden:
    1. Busca un Python compatible (3.10 a 3.13, con el launcher "py"). En el equipo donde se probo, Python 3.15 no servia
       porque onnxruntime no publicaba version para el.
    2. Crea el entorno .rag\.venv e instala fastembed y numpy.
    3. Construye el indice del vault y de docs\. La primera vez descarga el modelo (unos 0,6 GB) a
       %USERPROFILE%\.cache\rag-modelos, que comparten todos los proyectos.
    4. Registra los ganchos de Claude Code en .claude\settings.local.json (mezcla con lo que ya haya, con copia de seguridad).
    5. Arranca el servidor local.
  Los vectores se calculan en este equipo. Solo se descargan las librerias y el modelo.
  Hace falta Windows con PowerShell y el launcher "py". El motor (rag.py) esta escrito para otros sistemas, pero no se probo en ellos.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .rag\preparar.ps1
#>
$ErrorActionPreference = "Stop"
$rag = $PSScriptRoot
$scriptRag = Join-Path $rag "rag.py"
if (-not (Test-Path -LiteralPath $scriptRag)) { throw "No encuentro rag.py en $rag" }

Write-Host "1/5 Buscando un Python compatible..."
$python = $null
foreach ($v in @("3.12", "3.13", "3.11", "3.10")) {
  try {
    $ruta = (& py "-$v" -c "import sys; print(sys.executable)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $ruta) { $python = ([string]$ruta).Trim(); Write-Host "    Python ${v}: $python"; break }
  } catch { }
}
if (-not $python) {
  throw "No encuentro Python 3.10 a 3.13 con el launcher 'py'. Instala Python 3.12 desde python.org y vuelve a ejecutar esto."
}

$venv = Join-Path $rag ".venv"
$py = Join-Path $venv "Scripts\python.exe"
Write-Host "2/5 Entorno de Python e instalacion de librerias (fastembed, numpy)..."
if (-not (Test-Path -LiteralPath $py)) {
  & $python -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno en $venv" }
}
& $py -m pip install --quiet --disable-pip-version-check fastembed numpy
if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar fastembed. Revisa la conexion y vuelve a ejecutar." }

$env:PYTHONUTF8 = "1"
Write-Host "3/5 Construyendo el indice (la primera vez descarga el modelo y puede tardar varios minutos)..."
& $py $scriptRag indexar
if ($LASTEXITCODE -ne 0) { throw "Fallo al construir el indice." }

Write-Host "4/5 Registrando los ganchos de Claude Code..."
& $py $scriptRag ganchos
if ($LASTEXITCODE -ne 0) { throw "No se pudieron registrar los ganchos." }

Write-Host "5/5 Arrancando el servidor local..."
& $py $scriptRag arrancar

Write-Host ""
Write-Host "Listo. Abre /hooks una vez o reinicia la sesion del agente para que cargue los ganchos."
Write-Host "Para apagar la recuperacion automatica: variable de entorno RAG_DESACTIVAR=1."
Write-Host "Para medir su calidad: copia .rag\evaluacion.ejemplo.json como evaluacion.json, ponle preguntas propias y ejecuta 'rag.py evaluar'."
