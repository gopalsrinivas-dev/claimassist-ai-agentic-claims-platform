$RepoRoot = "D:\Workspace\professional\AgenticAI\claimassist-ai-agentic-claims-platform"
$Target = Join-Path $RepoRoot "docs"
$Legacy = Join-Path $RepoRoot "doc's"
$Source = Join-Path $PSScriptRoot "docs"

if (!(Test-Path $Target)) {
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
}

Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force

if (Test-Path $Legacy) {
    Write-Host "Legacy folder still exists: $Legacy"
    Write-Host "After verifying docs/, remove the legacy doc's folder to avoid duplicate sources of truth."
}

Write-Host "ClaimAssist documentation copied to: $Target"
