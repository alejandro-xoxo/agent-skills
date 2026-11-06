# SPDX-License-Identifier: LicenseRef-Proprietary - Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
<#
.SYNOPSIS
  Creates (or completes) the memory structure of a project from the template.

.DESCRIPTION
  Copies the "base" folder into the destination project and fills in the markers
  {{NAME}}, {{DESCRIPTION}}, {{STACK}}, {{VAULT}} and {{DATE}}.
  By default it does NOT overwrite files that already exist (use -Force to do so),
  so it can also be used on a project that already has files.

  The Obsidian vault goes by default in <Destination>\knowledge. With -Vault an
  external vault is used: the note structure is created there and AGENTS.md points to it.

  The parameters were Spanish in earlier versions; the old names still work as aliases
  (-Destino, -Nombre, -Descripcion, -Carpeta, -CrearVault, -SoloVault, -ConGit, -ConMcpMemoria,
  -ConGraphify, -SoloGraphify, -ConRag, -SoloRag, -Forzar).

.PARAMETER Destination
  Project folder. It is created if it does not exist.
.PARAMETER Name
  Project name (it appears in AGENTS.md and in the vault).
.PARAMETER Description
  One or two lines about what the project is.
.PARAMETER Stack
  Main technologies (optional).
.PARAMETER Vault
  Path of an existing Obsidian vault. If omitted, <Destination>\knowledge is used.
.PARAMETER Folder
  With -Vault: creates the structure in a subfolder of the vault (for a vault shared by several projects).
.PARAMETER CreateVault
  With -Vault: creates the vault folder if it does not exist (by default it is an error, to avoid creating folders because of a typo).
.PARAMETER VaultOnly
  With -Vault: creates only the note structure in the vault; does not touch the project or AGENTS.md.
.PARAMETER WithGit
  Runs "git init" if the folder is not yet a repository. It makes no commit.
.PARAMETER WithMemoryMcp
  Creates a .mcp.json with the graph-memory server (level 2, optional).
.PARAMETER WithGraphify
  Prepares, without installing anything, the code graph with Graphify: copies .graphifyignore and docs\GRAPH.md, adds a line to the
  AGENTS.md map and graphify-out/ to .gitignore. It is optional and only makes sense if the project will have a fair amount of code.
.PARAMETER GraphifyOnly
  Does only what -WithGraphify does, on a project that already exists: does not copy the base, does not create a vault or knowledge\, does not touch git.
.PARAMETER WithRag
  Prepares, without installing anything, automatic retrieval (local RAG): copies .rag\ with the engine and the prepare.ps1 script,
  adds a line to AGENTS.md and ignores .rag/ in git. Really turning it on is a separate step: run .rag\prepare.ps1.
.PARAMETER RagOnly
  Does only what -WithRag does, on a project that already exists: does not copy the base, does not create a vault or knowledge\, does not touch git.
.PARAMETER Force
  Overwrites files that already exist.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\new-project.ps1 -Destination "C:\Users\me\Documents\Projects\my-app" -Name "My App" -Description "Invoice API" -Stack "Python and FastAPI" -WithGit

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\new-project.ps1 -Destination "C:\Projects\my-app" -Name "My App" -Vault "D:\Obsidian\MyVault" -Folder "My App"
#>
param(
  [Parameter(Mandatory = $true)][Alias("Destino")][string]$Destination,
  [Parameter(Mandatory = $true)][Alias("Nombre")][string]$Name,
  [Alias("Descripcion")][string]$Description = "(describe the project in 1 or 2 lines)",
  [string]$Stack = "(to be defined)",
  [string]$Vault = "",
  [Alias("Carpeta")][string]$Folder = "",
  [Alias("CrearVault")][switch]$CreateVault,
  [Alias("SoloVault")][switch]$VaultOnly,
  [Alias("ConGit")][switch]$WithGit,
  [Alias("ConMcpMemoria")][switch]$WithMemoryMcp,
  [Alias("ConGraphify")][switch]$WithGraphify,
  [Alias("SoloGraphify")][switch]$GraphifyOnly,
  [Alias("ConRag")][switch]$WithRag,
  [Alias("SoloRag")][switch]$RagOnly,
  [Alias("Forzar")][switch]$Force
)

$ErrorActionPreference = "Stop"

if ($VaultOnly -and -not $Vault) { throw "-VaultOnly needs -Vault." }
if ($Folder -and -not $Vault) { throw "-Folder needs -Vault." }
if ($WithGraphify -and $VaultOnly) { throw "-WithGraphify cannot be combined with -VaultOnly (it prepares the project, not the vault)." }
if ($GraphifyOnly) {
  if ($Vault -or $Folder -or $VaultOnly -or $WithGit -or $WithMemoryMcp) { throw "-GraphifyOnly cannot be combined with -Vault, -Folder, -VaultOnly, -WithGit or -WithMemoryMcp." }
  if (-not (Test-Path -LiteralPath $Destination)) { throw "-GraphifyOnly needs a project that already exists: $Destination" }
  $WithGraphify = $true
}
if ($WithRag -and $VaultOnly) { throw "-WithRag cannot be combined with -VaultOnly (it prepares the project, not the vault)." }
if ($RagOnly) {
  if ($Vault -or $Folder -or $VaultOnly -or $WithGit -or $WithMemoryMcp) { throw "-RagOnly cannot be combined with -Vault, -Folder, -VaultOnly, -WithGit or -WithMemoryMcp." }
  if (-not (Test-Path -LiteralPath $Destination)) { throw "-RagOnly needs a project that already exists: $Destination" }
  $WithRag = $true
}

$baseFolder = Join-Path $PSScriptRoot "base"
if (-not (Test-Path -LiteralPath $baseFolder)) { throw "The base folder cannot be found: $baseFolder" }
$baseRoot = (Resolve-Path -LiteralPath $baseFolder).Path

if ($VaultOnly) {
  $destinationRoot = $Destination
} else {
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $destinationRoot = (Resolve-Path -LiteralPath $Destination).Path
}

# Vault: local (knowledge) or external
$vaultTarget = $null
$vaultPathText = "knowledge/"
if ($Vault) {
  if (-not (Test-Path -LiteralPath $Vault)) {
    if ($CreateVault) { New-Item -ItemType Directory -Force -Path $Vault | Out-Null }
    else { throw "The vault does not exist: $Vault (use -CreateVault to create it)." }
  }
  $vaultRoot = (Resolve-Path -LiteralPath $Vault).Path
  $vaultTarget = $vaultRoot
  $vaultPathText = ($vaultRoot -replace "\\", "/")
  if ($Folder) {
    $vaultTarget = Join-Path $vaultRoot $Folder
    $vaultPathText = $vaultPathText + "/" + ($Folder -replace "\\", "/")
  }
  New-Item -ItemType Directory -Force -Path $vaultTarget | Out-Null
}

$today = Get-Date -Format "yyyy-MM-dd"
$utf8 = New-Object System.Text.UTF8Encoding($false)
$textExtensions = @(".md", ".json", ".gitignore", ".txt")
$vaultPrefix = "knowledge\"
$ordinal = [System.StringComparison]::OrdinalIgnoreCase

function Fill([string]$text) {
  return $text.Replace("{{NAME}}", $Name).Replace("{{DESCRIPTION}}", $Description).Replace("{{STACK}}", $Stack).Replace("{{VAULT}}", $vaultPathText).Replace("{{DATE}}", $today)
}

# Code graph (optional): only leaves guide and configuration files. It does not install or run Graphify.
function PrepareGraphify([string]$projectRoot) {
  Write-Host "Code graph (Graphify): preparing the ground, installing nothing"
  $extras = Join-Path $PSScriptRoot "extras\graphify"
  foreach ($pair in @(@("graphifyignore.example", ".graphifyignore"), @("GRAPH.md", "docs\GRAPH.md"))) {
    $source = Join-Path $extras $pair[0]
    if (-not (Test-Path -LiteralPath $source)) { throw "$source is missing from the template." }
    $output = Join-Path $projectRoot $pair[1]
    if ((Test-Path -LiteralPath $output) -and -not $Force) { Write-Host "  already exists, skipped: $output"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
    [System.IO.File]::WriteAllText($output, (Fill ([System.IO.File]::ReadAllText($source, $utf8))), $utf8)
    Write-Host "  created: $output"
  }

  # One line in the repository map of AGENTS.md (only if it exists and does not have it yet)
  $agents = Join-Path $projectRoot "AGENTS.md"
  if (Test-Path -LiteralPath $agents) {
    $text = [System.IO.File]::ReadAllText($agents, $utf8)
    if ($text.Contains("docs/GRAPH.md")) {
      Write-Host "  AGENTS.md already mentions docs/GRAPH.md"
    } else {
      $eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
      $marker = "- (Add the code folders here once they exist.)"
      $line = '- `docs/GRAPH.md`: how to turn on the code graph (Graphify) when the project grows. Optional; not installed today.'
      if ($text.Contains($marker)) {
        $text = $text.Replace($marker, $line + $eol + $marker)
      } else {
        $text = $text.TrimEnd() + $eol + $eol + "## Code graph (optional)" + $eol + $line + $eol
      }
      [System.IO.File]::WriteAllText($agents, $text, $utf8)
      Write-Host "  AGENTS.md: added a line pointing to docs/GRAPH.md"
    }
  }

  # .gitignore: the graph is regenerated, not versioned
  $gi = Join-Path $projectRoot ".gitignore"
  if ((Test-Path -LiteralPath $gi) -or (Test-Path -LiteralPath (Join-Path $projectRoot ".git"))) {
    $current = ""
    if (Test-Path -LiteralPath $gi) { $current = [System.IO.File]::ReadAllText($gi, $utf8) }
    if ($current.Contains("graphify-out/")) {
      Write-Host "  .gitignore already ignores graphify-out/"
    } else {
      $eol = if ($current.Contains("`r`n")) { "`r`n" } else { "`n" }
      $sep = ""
      if ($current.Length -gt 0 -and -not $current.EndsWith("`n")) { $sep = $eol }
      [System.IO.File]::WriteAllText($gi, $current + $sep + $eol + "# Code graph generated by Graphify (it is regenerated)" + $eol + "graphify-out/" + $eol, $utf8)
      Write-Host "  .gitignore: graphify-out/ ignored"
    }
  } else {
    Write-Host "  there is no .gitignore or .git: nothing is touched (if you use git, ignore graphify-out/)"
  }
  Write-Host "  To turn it on later: see docs\GRAPH.md. Do not run 'graphify claude install' (it writes CLAUDE.md)."
}

# Automatic retrieval (local RAG): only copies files and leaves the configuration. It installs nothing and does not download the model.
function PrepareRag([string]$projectRoot) {
  Write-Host "Automatic retrieval (local RAG): preparing the files, installing nothing"
  $extras = Join-Path $PSScriptRoot "extras\rag"
  foreach ($fileName in @("rag.py", "prepare.ps1", "evaluation.example.json", "README.md")) {
    $source = Join-Path $extras $fileName
    if (-not (Test-Path -LiteralPath $source)) { throw "$source is missing from the template." }
    $output = Join-Path $projectRoot (Join-Path ".rag" $fileName)
    if ((Test-Path -LiteralPath $output) -and -not $Force) { Write-Host "  already exists, skipped: $output"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
    Copy-Item -LiteralPath $source -Destination $output -Force
    Write-Host "  created: $output"
  }

  # One line in the Memory block of AGENTS.md (only if it exists and does not have it yet)
  $agents = Join-Path $projectRoot "AGENTS.md"
  if (Test-Path -LiteralPath $agents) {
    $text = [System.IO.File]::ReadAllText($agents, $utf8)
    if ($text.Contains("prepare.ps1") -or $text.Contains("RAG_DISABLE") -or $text.Contains("RAG_DESACTIVAR")) {
      Write-Host "  AGENTS.md already mentions automatic retrieval"
    } else {
      $line = ([System.IO.File]::ReadAllText((Join-Path $extras "agents-line.txt"), $utf8)).TrimEnd()
      $eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
      $pattern = "(?m)^- Outside the vault:.*$"
      if ([regex]::IsMatch($text, $pattern)) {
        $text = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $m.Value + $eol + $line }, 1)
      } else {
        $text = $text.TrimEnd() + $eol + $eol + "## Automatic retrieval (optional)" + $eol + $line + $eol
      }
      [System.IO.File]::WriteAllText($agents, $text, $utf8)
      Write-Host "  AGENTS.md: added a line about automatic retrieval"
    }
  }

  # .gitignore: .rag/ (environment, index, server and model are regenerated)
  $gi = Join-Path $projectRoot ".gitignore"
  if ((Test-Path -LiteralPath $gi) -or (Test-Path -LiteralPath (Join-Path $projectRoot ".git"))) {
    $current = ""
    if (Test-Path -LiteralPath $gi) { $current = [System.IO.File]::ReadAllText($gi, $utf8) }
    if ($current -match "(?m)^\.rag/") {
      Write-Host "  .gitignore already ignores .rag/"
    } else {
      $eol = if ($current.Contains("`r`n")) { "`r`n" } else { "`n" }
      $sep = ""
      if ($current.Length -gt 0 -and -not $current.EndsWith("`n")) { $sep = $eol }
      [System.IO.File]::WriteAllText($gi, $current + $sep + $eol + "# Local semantic search over the vault (environment, index and server; they are regenerated)" + $eol + ".rag/" + $eol, $utf8)
      Write-Host "  .gitignore: .rag/ ignored"
    }
  } else {
    Write-Host "  there is no .gitignore or .git: nothing is touched (if you use git, ignore .rag/)"
  }
  Write-Host "  To turn it on (it downloads about 0.6 GB the first time and takes several minutes):"
  Write-Host "    powershell -NoProfile -ExecutionPolicy Bypass -File .rag\prepare.ps1"
}

if ($GraphifyOnly -or $RagOnly) {
  if ($WithGraphify) { PrepareGraphify $destinationRoot }
  if ($WithRag) { PrepareRag $destinationRoot }
  exit 0
}

$copied = 0
$skipped = 0
foreach ($file in Get-ChildItem -LiteralPath $baseRoot -Recurse -File -Force) {
  $relative = $file.FullName.Substring($baseRoot.Length).TrimStart("\", "/")
  $isVault = $relative.StartsWith($vaultPrefix, $ordinal)
  if ($VaultOnly -and -not $isVault) { continue }

  if ($isVault -and $vaultTarget) {
    $inside = $relative.Substring($vaultPrefix.Length)
    # In a shared vault, another Obsidian configuration is not nested
    if ($Folder -and $inside.StartsWith(".obsidian", $ordinal)) { continue }
    $output = Join-Path $vaultTarget $inside
  } else {
    $output = Join-Path $destinationRoot $relative
  }

  if ((Test-Path -LiteralPath $output) -and -not $Force) {
    Write-Host "  already exists, skipped: $output"
    $skipped++
    continue
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
  if ($textExtensions -contains $file.Extension.ToLower()) {
    $text = [System.IO.File]::ReadAllText($file.FullName, $utf8)
    [System.IO.File]::WriteAllText($output, (Fill $text), $utf8)
  } else {
    Copy-Item -LiteralPath $file.FullName -Destination $output -Force
  }
  $copied++
}

if ($WithGraphify) { PrepareGraphify $destinationRoot }
if ($WithRag) { PrepareRag $destinationRoot }

if (-not $VaultOnly) {
  if ($WithMemoryMcp) {
    $example = Join-Path $PSScriptRoot "extras\mcp.memory.example.json"
    $mcp = Join-Path $destinationRoot ".mcp.json"
    if ((Test-Path -LiteralPath $mcp) -and -not $Force) {
      Write-Host "  .mcp.json already exists, not touched. Add the 'memory' server by hand (see extras\mcp.memory.example.json)."
    } else {
      $json = [System.IO.File]::ReadAllText($example, $utf8).Replace("{{PATH}}", ($destinationRoot -replace "\\", "/"))
      [System.IO.File]::WriteAllText($mcp, $json, $utf8)
      Write-Host "  .mcp.json created. Claude Code will ask for approval the first time you open the project."
    }
  }

  if ($WithGit) {
    if (Test-Path -LiteralPath (Join-Path $destinationRoot ".git")) {
      Write-Host "  git: there is already a repository, not touched."
    } else {
      git -C $destinationRoot init | Out-Null
      Write-Host "  git init done (no commit)."
    }
  }
}

Write-Host ""
if ($VaultOnly) {
  Write-Host "Done: $copied files created and $skipped skipped in the vault: $vaultTarget"
} else {
  Write-Host "Done: $copied files created and $skipped skipped in $destinationRoot"
}
if ($Vault) {
  Write-Host "Obsidian vault: $vaultPathText"
  if ($Folder) {
    Write-Host "WARNING: shared vault. The template notes (Inbox, Glossary, Decisions...) are named the same in every project:"
    Write-Host "         if two projects use the same vault, Obsidian may resolve a link to the other one's note. Use names of your own."
  } else {
    Write-Host "If the vault is new, open it in Obsidian with 'Open folder as vault'."
  }
}
if (-not $VaultOnly) {
  Write-Host "Next steps:"
  Write-Host "  1. Fill in AGENTS.md (commands and golden rules)."
  if (-not $Vault) { Write-Host "  2. Open the 'knowledge' folder as a vault in Obsidian." }
  if ($WithGraphify) { Write-Host "  - Code graph prepared, not installed: see docs\GRAPH.md when the project has a fair amount of code." }
  if ($WithRag) { Write-Host "  - Automatic retrieval prepared, not installed: run .rag\prepare.ps1 when you want to turn it on (it downloads about 0.6 GB)." }
  Write-Host "  - Do not create CLAUDE.md or CLAUDE.local.md: Claude Code would stop reading AGENTS.md."
}
