# Build all workspace distributions including the latest console frontend.
# Run from repo root: pwsh -File scripts/wheel_build.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $RepoRoot

$ConsoleDir = Join-Path $RepoRoot "console"
$ConsoleDest = Join-Path $RepoRoot "packages\minions-app\src\minions\console"

Write-Host "[wheel_build] Building console frontend..."
Push-Location $ConsoleDir
try {
  npm ci
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE" }
} finally {
  Pop-Location
}

Write-Host "[wheel_build] Copying console/dist/* -> packages/minions-app/src/minions/console/..."
if (Test-Path $ConsoleDest) {
  Remove-Item -Path (Join-Path $ConsoleDest "*") -Recurse -Force -ErrorAction SilentlyContinue
} else {
  New-Item -ItemType Directory -Force -Path $ConsoleDest | Out-Null
}
$ConsoleDist = Join-Path $ConsoleDir "dist"
Copy-Item -Path (Join-Path $ConsoleDist "*") -Destination $ConsoleDest -Recurse -Force

Write-Host "[wheel_build] Bundling website docs into package..."
$DocsSrc = Join-Path $RepoRoot "website\public\docs"
$DocsDest = Join-Path $RepoRoot "packages\minions-app\src\minions\docs"
if (Test-Path $DocsDest) { Remove-Item -Recurse -Force $DocsDest }
New-Item -ItemType Directory -Force -Path $DocsDest | Out-Null
Copy-Item -Path (Join-Path $DocsSrc "*.md") -Destination $DocsDest -Force

Write-Host "[wheel_build] Building 14 wheels + sdists..."
python -m pip install --quiet build
python scripts/build_workspace.py
if ($LASTEXITCODE -ne 0) { throw "scripts/build_workspace.py failed with exit code $LASTEXITCODE" }

Write-Host "[wheel_build] Done. Workspace artifacts in: $RepoRoot\dist\"
