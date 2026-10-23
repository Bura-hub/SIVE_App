# ================================
# MTE SIVE - Quick Deployment Runner (Windows)
# ================================

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "health", "rollback", "backup", "ssl", "help")]
    [string]$Action = "help",
    # Con rollback, restaura también la base de datos del respaldo previo al despliegue
    [switch]$ConBase
)

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DeployScript = Join-Path $ScriptDir "deploy_production.ps1"

# Check if the main deployment script exists
if (-not (Test-Path $DeployScript)) {
    Write-Host "Error: deploy_production.ps1 not found in $ScriptDir" -ForegroundColor Red
    exit 1
}

# Run the deployment script with the specified action
Write-Host "Running MTE SIVE deployment: $Action" -ForegroundColor Cyan
Write-Host "Script location: $DeployScript" -ForegroundColor Gray
Write-Host ""

try {
    if ($ConBase) { & $DeployScript -Command $Action -ConBase } else { & $DeployScript -Command $Action }
}
catch {
    Write-Host "Error running deployment script: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deployment action '$Action' completed." -ForegroundColor Green
