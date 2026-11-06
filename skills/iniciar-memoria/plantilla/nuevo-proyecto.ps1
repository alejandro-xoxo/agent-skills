# SPDX-License-Identifier: MIT
# Copyright (c) 2026 alejandro-xoxo
<#
.SYNOPSIS
  Crea (o completa) la estructura de memoria de un proyecto a partir de la plantilla.

.DESCRIPTION
  Copia la carpeta "base" al proyecto destino y rellena los marcadores
  {{NOMBRE}}, {{DESCRIPCION}}, {{STACK}}, {{VAULT}} y {{FECHA}}.
  Por defecto NO sobrescribe archivos que ya existen (usa -Forzar para hacerlo),
  asi que se puede usar tambien en un proyecto que ya tiene archivos.

  El vault de Obsidian va por defecto en <Destino>\conocimiento. Con -Vault se
  usa un vault externo: la estructura de notas se crea alli y AGENTS.md apunta a el.

.PARAMETER Destino
  Carpeta del proyecto. Se crea si no existe.
.PARAMETER Nombre
  Nombre del proyecto (aparece en AGENTS.md y en el vault).
.PARAMETER Descripcion
  Una o dos lineas sobre que es el proyecto.
.PARAMETER Stack
  Tecnologias principales (opcional).
.PARAMETER Vault
  Ruta de un vault de Obsidian existente. Si se omite, se usa <Destino>\conocimiento.
.PARAMETER Carpeta
  Con -Vault: crea la estructura en una subcarpeta del vault (para un vault compartido por varios proyectos).
.PARAMETER CrearVault
  Con -Vault: crea la carpeta del vault si no existe (por defecto da error, para evitar crear carpetas por una errata).
.PARAMETER SoloVault
  Con -Vault: crea solo la estructura de notas en el vault; no toca el proyecto ni AGENTS.md.
.PARAMETER ConGit
  Ejecuta "git init" si la carpeta aun no es un repositorio. No hace commit.
.PARAMETER ConMcpMemoria
  Crea un .mcp.json con el servidor de memoria en grafo (nivel 2, opcional).
.PARAMETER ConGraphify
  Deja preparado, sin instalar nada, el grafo de codigo con Graphify: copia .graphifyignore y docs\GRAFO.md, anade una linea al
  mapa de AGENTS.md y graphify-out/ al .gitignore. Es opcional y solo tiene sentido si el proyecto va a tener bastante codigo.
.PARAMETER SoloGraphify
  Hace unicamente lo de -ConGraphify en un proyecto que ya existe: no copia la base, no crea vault ni conocimiento\, no toca git.
.PARAMETER ConRag
  Deja preparada, sin instalar nada, la recuperacion automatica (RAG local): copia .rag\ con el motor y el script preparar.ps1,
  anade una linea a AGENTS.md e ignora .rag/ en git. Activarla de verdad es un paso aparte: ejecutar .rag\preparar.ps1.
.PARAMETER SoloRag
  Hace unicamente lo de -ConRag en un proyecto que ya existe: no copia la base, no crea vault ni conocimiento\, no toca git.
.PARAMETER Forzar
  Sobrescribe archivos que ya existen.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\nuevo-proyecto.ps1 -Destino "C:\Users\yo\Documents\Proyectos\mi-app" -Nombre "Mi App" -Descripcion "API de facturas" -Stack "Python y FastAPI" -ConGit

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\nuevo-proyecto.ps1 -Destino "C:\Proyectos\mi-app" -Nombre "Mi App" -Vault "D:\Obsidian\MiVault" -Carpeta "Mi App"
#>
param(
  [Parameter(Mandatory = $true)][string]$Destino,
  [Parameter(Mandatory = $true)][string]$Nombre,
  [string]$Descripcion = "(describe el proyecto en 1 o 2 lineas)",
  [string]$Stack = "(por definir)",
  [string]$Vault = "",
  [string]$Carpeta = "",
  [switch]$CrearVault,
  [switch]$SoloVault,
  [switch]$ConGit,
  [switch]$ConMcpMemoria,
  [switch]$ConGraphify,
  [switch]$SoloGraphify,
  [switch]$ConRag,
  [switch]$SoloRag,
  [switch]$Forzar
)

$ErrorActionPreference = "Stop"

if ($SoloVault -and -not $Vault) { throw "-SoloVault necesita -Vault." }
if ($Carpeta -and -not $Vault) { throw "-Carpeta necesita -Vault." }
if ($ConGraphify -and $SoloVault) { throw "-ConGraphify no se combina con -SoloVault (prepara el proyecto, no el vault)." }
if ($SoloGraphify) {
  if ($Vault -or $Carpeta -or $SoloVault -or $ConGit -or $ConMcpMemoria) { throw "-SoloGraphify no se combina con -Vault, -Carpeta, -SoloVault, -ConGit ni -ConMcpMemoria." }
  if (-not (Test-Path -LiteralPath $Destino)) { throw "-SoloGraphify necesita un proyecto que ya exista: $Destino" }
  $ConGraphify = $true
}
if ($ConRag -and $SoloVault) { throw "-ConRag no se combina con -SoloVault (prepara el proyecto, no el vault)." }
if ($SoloRag) {
  if ($Vault -or $Carpeta -or $SoloVault -or $ConGit -or $ConMcpMemoria) { throw "-SoloRag no se combina con -Vault, -Carpeta, -SoloVault, -ConGit ni -ConMcpMemoria." }
  if (-not (Test-Path -LiteralPath $Destino)) { throw "-SoloRag necesita un proyecto que ya exista: $Destino" }
  $ConRag = $true
}

$carpetaBase = Join-Path $PSScriptRoot "base"
if (-not (Test-Path -LiteralPath $carpetaBase)) { throw "No se encuentra la carpeta base: $carpetaBase" }
$raizBase = (Resolve-Path -LiteralPath $carpetaBase).Path

if ($SoloVault) {
  $raizDestino = $Destino
} else {
  New-Item -ItemType Directory -Force -Path $Destino | Out-Null
  $raizDestino = (Resolve-Path -LiteralPath $Destino).Path
}

# Vault: local (conocimiento) o externo
$destinoVault = $null
$rutaVaultTexto = "conocimiento/"
if ($Vault) {
  if (-not (Test-Path -LiteralPath $Vault)) {
    if ($CrearVault) { New-Item -ItemType Directory -Force -Path $Vault | Out-Null }
    else { throw "El vault no existe: $Vault (usa -CrearVault para crearlo)." }
  }
  $raizVault = (Resolve-Path -LiteralPath $Vault).Path
  $destinoVault = $raizVault
  $rutaVaultTexto = ($raizVault -replace "\\", "/")
  if ($Carpeta) {
    $destinoVault = Join-Path $raizVault $Carpeta
    $rutaVaultTexto = $rutaVaultTexto + "/" + ($Carpeta -replace "\\", "/")
  }
  New-Item -ItemType Directory -Force -Path $destinoVault | Out-Null
}

$fecha = Get-Date -Format "yyyy-MM-dd"
$utf8 = New-Object System.Text.UTF8Encoding($false)
$extTexto = @(".md", ".json", ".gitignore", ".txt")
$prefijoVault = "conocimiento\"
$ordinal = [System.StringComparison]::OrdinalIgnoreCase

function Rellenar([string]$texto) {
  return $texto.Replace("{{NOMBRE}}", $Nombre).Replace("{{DESCRIPCION}}", $Descripcion).Replace("{{STACK}}", $Stack).Replace("{{VAULT}}", $rutaVaultTexto).Replace("{{FECHA}}", $fecha)
}

# Grafo de codigo (opcional): solo deja archivos de guia y configuracion. No instala ni ejecuta Graphify.
function PrepararGraphify([string]$raizProyecto) {
  Write-Host "Grafo de codigo (Graphify): preparando el terreno, sin instalar nada"
  $extras = Join-Path $PSScriptRoot "extras\graphify"
  foreach ($par in @(@("graphifyignore.example", ".graphifyignore"), @("GRAFO.md", "docs\GRAFO.md"))) {
    $origen = Join-Path $extras $par[0]
    if (-not (Test-Path -LiteralPath $origen)) { throw "Falta $origen en la plantilla." }
    $salida = Join-Path $raizProyecto $par[1]
    if ((Test-Path -LiteralPath $salida) -and -not $Forzar) { Write-Host "  ya existe, se omite: $salida"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $salida) | Out-Null
    [System.IO.File]::WriteAllText($salida, (Rellenar ([System.IO.File]::ReadAllText($origen, $utf8))), $utf8)
    Write-Host "  creado: $salida"
  }

  # Una linea en el mapa del repositorio de AGENTS.md (solo si existe y aun no la tiene)
  $agentes = Join-Path $raizProyecto "AGENTS.md"
  if (Test-Path -LiteralPath $agentes) {
    $texto = [System.IO.File]::ReadAllText($agentes, $utf8)
    if ($texto.Contains("docs/GRAFO.md")) {
      Write-Host "  AGENTS.md ya menciona docs/GRAFO.md"
    } else {
      $eol = if ($texto.Contains("`r`n")) { "`r`n" } else { "`n" }
      $marcadorAcentos = "- (A" + [char]0x00F1 + "adir aqu" + [char]0x00ED + " las carpetas de c" + [char]0x00F3 + "digo cuando existan.)"
      $linea = '- `docs/GRAFO.md`: c' + [char]0x00F3 + 'mo activar el grafo de c' + [char]0x00F3 + 'digo (Graphify) cuando el proyecto crezca. Opcional; hoy no est' + [char]0x00E1 + ' instalado.'
      if ($texto.Contains($marcadorAcentos)) {
        $texto = $texto.Replace($marcadorAcentos, $linea + $eol + $marcadorAcentos)
      } else {
        $texto = $texto.TrimEnd() + $eol + $eol + "## Grafo de c" + [char]0x00F3 + "digo (opcional)" + $eol + $linea + $eol
      }
      [System.IO.File]::WriteAllText($agentes, $texto, $utf8)
      Write-Host "  AGENTS.md: anadida una linea que apunta a docs/GRAFO.md"
    }
  }

  # .gitignore: el grafo se regenera, no se versiona
  $gi = Join-Path $raizProyecto ".gitignore"
  if ((Test-Path -LiteralPath $gi) -or (Test-Path -LiteralPath (Join-Path $raizProyecto ".git"))) {
    $actual = ""
    if (Test-Path -LiteralPath $gi) { $actual = [System.IO.File]::ReadAllText($gi, $utf8) }
    if ($actual.Contains("graphify-out/")) {
      Write-Host "  .gitignore ya ignora graphify-out/"
    } else {
      $eol = if ($actual.Contains("`r`n")) { "`r`n" } else { "`n" }
      $sep = ""
      if ($actual.Length -gt 0 -and -not $actual.EndsWith("`n")) { $sep = $eol }
      [System.IO.File]::WriteAllText($gi, $actual + $sep + $eol + "# Grafo de c" + [char]0x00F3 + "digo generado por Graphify (se regenera)" + $eol + "graphify-out/" + $eol, $utf8)
      Write-Host "  .gitignore: graphify-out/ ignorado"
    }
  } else {
    Write-Host "  no hay .gitignore ni .git: no se toca nada (si usas git, ignora graphify-out/)"
  }
  Write-Host "  Para activarlo mas adelante: ver docs\GRAFO.md. No ejecutes 'graphify claude install' (escribe CLAUDE.md)."
}

# Recuperacion automatica (RAG local): solo copia archivos y deja la configuracion. No instala nada ni descarga el modelo.
function PrepararRag([string]$raizProyecto) {
  Write-Host "Recuperacion automatica (RAG local): preparando los archivos, sin instalar nada"
  $extras = Join-Path $PSScriptRoot "extras\rag"
  foreach ($nombre in @("rag.py", "preparar.ps1", "evaluacion.ejemplo.json", "LEEME.md")) {
    $origen = Join-Path $extras $nombre
    if (-not (Test-Path -LiteralPath $origen)) { throw "Falta $origen en la plantilla." }
    $salida = Join-Path $raizProyecto (Join-Path ".rag" $nombre)
    if ((Test-Path -LiteralPath $salida) -and -not $Forzar) { Write-Host "  ya existe, se omite: $salida"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $salida) | Out-Null
    Copy-Item -LiteralPath $origen -Destination $salida -Force
    Write-Host "  creado: $salida"
  }

  # Una linea en el bloque Memoria de AGENTS.md (solo si existe y aun no la tiene)
  $agentes = Join-Path $raizProyecto "AGENTS.md"
  if (Test-Path -LiteralPath $agentes) {
    $texto = [System.IO.File]::ReadAllText($agentes, $utf8)
    if ($texto.Contains("preparar.ps1") -or $texto.Contains("RAG_DESACTIVAR")) {
      Write-Host "  AGENTS.md ya menciona la recuperacion automatica"
    } else {
      $linea = ([System.IO.File]::ReadAllText((Join-Path $extras "linea-agents.txt"), $utf8)).TrimEnd()
      $eol = if ($texto.Contains("`r`n")) { "`r`n" } else { "`n" }
      $patron = "(?m)^- Fuera del vault:.*$"
      if ([regex]::IsMatch($texto, $patron)) {
        $texto = [regex]::Replace($texto, $patron, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $m.Value + $eol + $linea }, 1)
      } else {
        $texto = $texto.TrimEnd() + $eol + $eol + "## Recuperaci" + [char]0x00F3 + "n autom" + [char]0x00E1 + "tica (opcional)" + $eol + $linea + $eol
      }
      [System.IO.File]::WriteAllText($agentes, $texto, $utf8)
      Write-Host "  AGENTS.md: anadida una linea sobre la recuperacion automatica"
    }
  }

  # .gitignore: .rag/ (entorno, indice, servidor y modelo se regeneran)
  $gi = Join-Path $raizProyecto ".gitignore"
  if ((Test-Path -LiteralPath $gi) -or (Test-Path -LiteralPath (Join-Path $raizProyecto ".git"))) {
    $actual = ""
    if (Test-Path -LiteralPath $gi) { $actual = [System.IO.File]::ReadAllText($gi, $utf8) }
    if ($actual -match "(?m)^\.rag/") {
      Write-Host "  .gitignore ya ignora .rag/"
    } else {
      $eol = if ($actual.Contains("`r`n")) { "`r`n" } else { "`n" }
      $sep = ""
      if ($actual.Length -gt 0 -and -not $actual.EndsWith("`n")) { $sep = $eol }
      [System.IO.File]::WriteAllText($gi, $actual + $sep + $eol + "# B" + [char]0x00FA + "squeda sem" + [char]0x00E1 + "ntica local del vault (entorno, " + [char]0x00ED + "ndice y servidor; se regeneran)" + $eol + ".rag/" + $eol, $utf8)
      Write-Host "  .gitignore: .rag/ ignorado"
    }
  } else {
    Write-Host "  no hay .gitignore ni .git: no se toca nada (si usas git, ignora .rag/)"
  }
  Write-Host "  Para activarla (descarga unos 0,6 GB la primera vez y tarda varios minutos):"
  Write-Host "    powershell -NoProfile -ExecutionPolicy Bypass -File .rag\preparar.ps1"
}

if ($SoloGraphify -or $SoloRag) {
  if ($ConGraphify) { PrepararGraphify $raizDestino }
  if ($ConRag) { PrepararRag $raizDestino }
  exit 0
}

$copiados = 0
$omitidos = 0
foreach ($archivo in Get-ChildItem -LiteralPath $raizBase -Recurse -File -Force) {
  $relativa = $archivo.FullName.Substring($raizBase.Length).TrimStart("\", "/")
  $esVault = $relativa.StartsWith($prefijoVault, $ordinal)
  if ($SoloVault -and -not $esVault) { continue }

  if ($esVault -and $destinoVault) {
    $dentro = $relativa.Substring($prefijoVault.Length)
    # En un vault compartido no se anida otra configuracion de Obsidian
    if ($Carpeta -and $dentro.StartsWith(".obsidian", $ordinal)) { continue }
    $salida = Join-Path $destinoVault $dentro
  } else {
    $salida = Join-Path $raizDestino $relativa
  }

  if ((Test-Path -LiteralPath $salida) -and -not $Forzar) {
    Write-Host "  ya existe, se omite: $salida"
    $omitidos++
    continue
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $salida) | Out-Null
  if ($extTexto -contains $archivo.Extension.ToLower()) {
    $texto = [System.IO.File]::ReadAllText($archivo.FullName, $utf8)
    [System.IO.File]::WriteAllText($salida, (Rellenar $texto), $utf8)
  } else {
    Copy-Item -LiteralPath $archivo.FullName -Destination $salida -Force
  }
  $copiados++
}

if ($ConGraphify) { PrepararGraphify $raizDestino }
if ($ConRag) { PrepararRag $raizDestino }

if (-not $SoloVault) {
  if ($ConMcpMemoria) {
    $ejemplo = Join-Path $PSScriptRoot "extras\mcp.memory.example.json"
    $mcp = Join-Path $raizDestino ".mcp.json"
    if ((Test-Path -LiteralPath $mcp) -and -not $Forzar) {
      Write-Host "  ya existe .mcp.json, no se toca. Anade el servidor 'memory' a mano (ver extras\mcp.memory.example.json)."
    } else {
      $json = [System.IO.File]::ReadAllText($ejemplo, $utf8).Replace("{{RUTA}}", ($raizDestino -replace "\\", "/"))
      [System.IO.File]::WriteAllText($mcp, $json, $utf8)
      Write-Host "  .mcp.json creado. Claude Code pedira aprobacion la primera vez que abras el proyecto."
    }
  }

  if ($ConGit) {
    if (Test-Path -LiteralPath (Join-Path $raizDestino ".git")) {
      Write-Host "  git: ya hay un repositorio, no se toca."
    } else {
      git -C $raizDestino init | Out-Null
      Write-Host "  git init hecho (sin commit)."
    }
  }
}

Write-Host ""
if ($SoloVault) {
  Write-Host "Listo: $copiados archivos creados y $omitidos omitidos en el vault: $destinoVault"
} else {
  Write-Host "Listo: $copiados archivos creados y $omitidos omitidos en $raizDestino"
}
if ($Vault) {
  Write-Host "Vault de Obsidian: $rutaVaultTexto"
  if ($Carpeta) {
    Write-Host "AVISO: vault compartido. Las notas de la plantilla (Inbox, Glosario, Decisiones...) se llaman igual en cada proyecto:"
    Write-Host "       si dos proyectos usan el mismo vault, Obsidian puede resolver un enlace a la nota del otro. Usa nombres propios."
  } else {
    Write-Host "Si el vault es nuevo, abrelo en Obsidian con 'Abrir carpeta como boveda'."
  }
}
if (-not $SoloVault) {
  Write-Host "Siguientes pasos:"
  Write-Host "  1. Completa AGENTS.md (comandos y reglas de oro)."
  if (-not $Vault) { Write-Host "  2. Abre la carpeta 'conocimiento' como boveda en Obsidian." }
  if ($ConGraphify) { Write-Host "  - Grafo de codigo preparado, no instalado: ver docs\GRAFO.md cuando el proyecto tenga bastante codigo." }
  if ($ConRag) { Write-Host "  - Recuperacion automatica preparada, no instalada: ejecuta .rag\preparar.ps1 cuando quieras activarla (descarga unos 0,6 GB)." }
  Write-Host "  - No crees CLAUDE.md ni CLAUDE.local.md: Claude Code dejaria de leer AGENTS.md."
}
