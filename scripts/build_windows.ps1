param(
    [string]$ArtifactName = "TeslaCamTelemetry-windows-portable.zip"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SpecFile = Join-Path $RepoRoot "packaging\TeslaCamTelemetry.spec"
$DistDir = Join-Path $RepoRoot "dist"
$BuildDir = Join-Path $RepoRoot "build"
$AppDir = Join-Path $DistDir "TeslaCamTelemetry"
$ExePath = Join-Path $AppDir "TeslaCamTelemetry.exe"
$ZipPath = Join-Path $DistDir $ArtifactName

Set-Location $RepoRoot

if (Test-Path $BuildDir) {
    Remove-Item $BuildDir -Recurse -Force
}
if (Test-Path $AppDir) {
    Remove-Item $AppDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

python -m PyInstaller --noconfirm --clean $SpecFile

if (-not (Test-Path $ExePath)) {
    throw "Expected packaged executable was not created: $ExePath"
}

Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $ZipPath -Force

if (-not (Test-Path $ZipPath)) {
    throw "Expected ZIP artifact was not created: $ZipPath"
}

Write-Host "Created $ZipPath"
