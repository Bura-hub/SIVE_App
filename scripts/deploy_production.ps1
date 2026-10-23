# ================================
# MTE SIVE - Production Deployment Script (Windows PowerShell)
# ================================
#
# Reescrito el 22-oct-2026 con la misma lógica que deploy_production.sh (d6f6a70). La versión anterior tenía sus
# mismos defectos: docker-compose sin el proyecto «mtesive_app», salud contra DOMAIN_NAME cuando los puertos solo
# escuchan en 127.0.0.1, «down» en cada despliegue y rollback, respaldo .sql sin verificar y un rollback que no volvía
# a las imágenes anteriores. Además, los try/catch no detectan el fallo de un programa externo (docker): aquí se
# comprueba $LASTEXITCODE después de cada llamada.
#
# Diferencias con el .sh por Windows: PowerShell 5 corrompe los binarios en tuberías y redirecciones, así que el
# volcado (pg_dump -Fc) se genera dentro del contenedor y se copia con «docker compose cp», y el archivo de media se
# arma en un contenedor temporal y se copia con «docker cp». La verificación del volcado (tamaño y pg_restore --list)
# replica la de scripts/backup_db.sh.

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "health", "rollback", "backup", "ssl", "help")]
    [string]$Command = "help",

    # Solo para rollback: restaurar también la base desde el respaldo del último despliegue
    [switch]$ConBase
)

$ErrorActionPreference = "Stop"

# Configuration
$PROJECT_NAME = "mtesive_app"          # proyecto compose de producción (contenedores mte_*_prod)
$COMPOSE_FILE = "docker-compose.prod.yml"
$ENV_FILE = ".env"
$BACKUP_DIR = ".\backups"
$LOG_DIR = ".\logs"
$APP_SERVICES = @("backend", "celery_worker", "celery_beat", "frontend")   # db y redis no se tocan
$MEDIA_VOLUME = "${PROJECT_NAME}_media_data_prod"
$LAST_DEPLOY_FILE = Join-Path $BACKUP_DIR "ultimo_despliegue.txt"
$MIN_BYTES = 10000                     # como backup_db.sh: un volcado válido pesa MB
$KEEP_MANUAL = 10                      # como KEEP_MANUAL de backup_db.sh

if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }
$DEPLOYMENT_LOG = Join-Path $LOG_DIR "deployment_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Functions
function Write-Log {
    param([string]$Level, [string]$Message, [string]$Color)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $DEPLOYMENT_LOG -Value $line
}
function Write-LogInfo    { param([string]$Message) Write-Log "INFO"    $Message "Blue" }
function Write-LogSuccess { param([string]$Message) Write-Log "SUCCESS" $Message "Green" }
function Write-LogWarning { param([string]$Message) Write-Log "WARNING" $Message "Yellow" }
function Write-LogError   { param([string]$Message) Write-Log "ERROR"   $Message "Red" }

# docker compose siempre con el proyecto de producción; falla si el programa falla
function Invoke-Compose {
    & docker compose -p $PROJECT_NAME -f $COMPOSE_FILE @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose $($args -join ' ') terminó con código $LASTEXITCODE" }
}
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "docker $($args -join ' ') terminó con código $LASTEXITCODE" }
}

# Lee una clave del .env sin ejecutarlo (como backup_db.sh)
function Read-EnvValue {
    param([string]$Key, [string]$Default = "")
    $line = Get-Content $ENV_FILE | Where-Object { $_ -match "^$Key=" } | Select-Object -Last 1
    if (-not $line) { return $Default }
    $value = ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrEmpty($value)) { return $Default } else { return $value }
}

if (-not (Test-Path $ENV_FILE)) {
    Write-Host ".env file not found. Run from the repository root." -ForegroundColor Red
    exit 1
}
$SERVER_IP     = Read-EnvValue "DOMAIN_NAME"
$FRONTEND_PORT = Read-EnvValue "FRONTEND_PORT" "3503"
$BACKEND_PORT  = Read-EnvValue "BACKEND_PORT" "3504"
$DB_USER       = Read-EnvValue "user_postgres" "BuraHub"
$DB_NAME       = Read-EnvValue "name_db" "sive_db"

# Pre-deployment checks
function Test-PreDeploymentChecks {
    Write-LogInfo "Running pre-deployment checks..."

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { Write-LogError "Docker is not running. Please start Docker first."; exit 1 }

    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { Write-LogError "docker compose (v2) is not available"; exit 1 }

    # El TLS lo termina Apache delante: los contenedores no montan .\ssl, así que no se generan certificados aquí.

    $drive = (Get-Location).Drive
    if ($drive -and $drive.Free -lt 5GB) {
        Write-LogWarning "Low disk space. At least 5GB recommended. Available: $([math]::Round($drive.Free / 1GB, 2)) GB"
    }

    Write-LogSuccess "Pre-deployment checks passed"
}

# Create SSL certificates (solo para entornos sin Apache delante; producción no los usa)
function New-SSLCertificates {
    Write-LogInfo "Creating SSL certificates for $SERVER_IP..."
    if (-not (Test-Path ".\ssl")) { New-Item -ItemType Directory -Path ".\ssl" | Out-Null }
    if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
        Write-LogError "OpenSSL is not installed or not in PATH. Please install OpenSSL first."
        exit 1
    }
    & openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout ssl\key.pem -out ssl\cert.pem `
        -subj "/C=CO/ST=Bogota/L=Bogota/O=MTE/OU=IT/CN=$SERVER_IP"
    if ($LASTEXITCODE -ne 0) { Write-LogError "Failed to create SSL certificates"; exit 1 }
    Write-LogSuccess "SSL certificates created for $SERVER_IP (ssl\*.pem está en .gitignore)"
}

# Create backup before deployment: base (verificada), volumen de media y etiqueta de las imágenes actuales.
# Si algo falla, aborta: no se despliega sin respaldo.
function New-Backup {
    Write-LogInfo "Creating backup before deployment..."
    if (-not (Test-Path $BACKUP_DIR)) { New-Item -ItemType Directory -Path $BACKUP_DIR | Out-Null }
    $mark = Get-Date -Format "yyyyMMdd_HHmmss"

    # Base: pg_dump -Fc dentro del contenedor, verificado con pg_restore --list, y copiado con docker compose cp
    $dbBackup = Join-Path $BACKUP_DIR "manual_sive_db_$mark.dump"
    $inner = "/tmp/manual_sive_db_$mark.dump"
    try {
        Invoke-Compose exec -T db pg_dump -Fc -U $DB_USER -f $inner $DB_NAME
        Invoke-Compose exec -T db pg_restore --list $inner | Out-Null
        Invoke-Compose cp "db:$inner" $dbBackup
    }
    catch {
        Write-LogError "Database backup failed: $_. Aborting deployment."
        exit 1
    }
    finally {
        & docker compose -p $PROJECT_NAME -f $COMPOSE_FILE exec -T db rm -f $inner *> $null
    }
    $size = (Get-Item $dbBackup).Length
    if ($size -lt $MIN_BYTES) {
        Remove-Item $dbBackup -Force
        Write-LogError "The dump is $size bytes (< $MIN_BYTES). Discarded as invalid. Aborting deployment."
        exit 1
    }
    Write-LogSuccess "Database backup: $dbBackup ($([math]::Round($size / 1MB)) MB)"

    # Media: tar del volumen en un contenedor temporal (solo lectura) y docker cp al host
    $mediaBackup = Join-Path $BACKUP_DIR "manual_media_$mark.tar.gz"
    $tmpName = "sive_media_backup_$mark"
    try {
        Invoke-Docker create --name $tmpName --entrypoint tar -v "${MEDIA_VOLUME}:/media:ro" `
            "${PROJECT_NAME}-backend:latest" czf /tmp/media.tar.gz -C /media . | Out-Null
        Invoke-Docker start -a $tmpName | Out-Null
        Invoke-Docker cp "${tmpName}:/tmp/media.tar.gz" $mediaBackup
    }
    catch {
        Write-LogError "Media backup failed: $_. Aborting deployment."
        exit 1
    }
    finally {
        & docker rm -f $tmpName *> $null
    }
    if ((Get-Item $mediaBackup).Length -eq 0) { Write-LogError "Media backup is empty. Aborting deployment."; exit 1 }
    Write-LogSuccess "Media backup: $mediaBackup"

    # Retención de los respaldos manuales (base y media), como backup_db.sh --manual
    foreach ($pattern in @("manual_sive_db_*.dump", "manual_media_*.tar.gz")) {
        Get-ChildItem -Path (Join-Path $BACKUP_DIR $pattern) | Sort-Object LastWriteTime -Descending |
            Select-Object -Skip $KEEP_MANUAL | ForEach-Object {
                Write-LogInfo "Retención: eliminando $($_.Name)"; Remove-Item $_.FullName -Force
            }
    }

    # Imágenes actuales: etiqueta antes-<marca> para el rollback
    foreach ($svc in $APP_SERVICES) {
        Invoke-Docker tag "${PROJECT_NAME}-${svc}:latest" "${PROJECT_NAME}-${svc}:antes-$mark"
    }
    Write-LogSuccess "Current images tagged antes-$mark"

    $commit = (& git rev-parse --short HEAD 2>$null); if (-not $commit) { $commit = "desconocido" }
    Set-Content -Path $LAST_DEPLOY_FILE -Value @("marca=$mark", "base=$dbBackup", "media=$mediaBackup", "commit=$commit")
    Write-LogSuccess "Rollback data written to $LAST_DEPLOY_FILE"
}

# Pull latest images (solo las externas: postgres y redis)
function Invoke-PullImages {
    Write-LogInfo "Checking for latest external Docker images..."
    try { Invoke-Compose pull --quiet db redis; Write-LogSuccess "External images updated successfully" }
    catch { Write-LogWarning "Could not pull external images; using the local ones" }
}

# Build new images
function Invoke-BuildImages {
    Write-LogInfo "Building new Docker images..."
    try { Invoke-Compose build @APP_SERVICES; Write-LogSuccess "Images built successfully" }
    catch { Write-LogError "Failed to build images: $_"; exit 1 }
}

# Espera a que un contenedor quede healthy (o devuelve $false)
function Wait-Healthy {
    param([string]$Container, [int]$Tries = 40)
    $status = ""
    for ($i = 0; $i -lt $Tries; $i++) {
        $status = & docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Container 2>$null
        if ($status -eq "healthy") { return $true }
        Start-Sleep -Seconds 5
    }
    Write-LogError "$Container is $status after $($Tries * 5) s"
    return $false
}

# Deploy services: sin down. db y redis siguen arriba; el backend (que migra al arrancar) va primero.
function Invoke-DeployServices {
    Write-LogInfo "Deploying services..."
    try {
        # --no-recreate: no recrea postgres ni redis aunque el pull traiga una imagen nueva.
        Invoke-Compose up -d --no-recreate db redis
        Write-LogInfo "Starting backend (runs migrate and collectstatic on start)..."
        Invoke-Compose up -d --no-deps backend
    }
    catch { Write-LogError "Failed to start services: $_"; Invoke-Rollback; exit 1 }

    if (-not (Wait-Healthy "mte_backend_prod")) { Write-LogError "Backend not healthy"; Invoke-Rollback; exit 1 }

    try {
        Write-LogInfo "Starting Celery and frontend..."
        Invoke-Compose up -d --no-deps celery_worker celery_beat frontend
    }
    catch { Write-LogError "Failed to start Celery and frontend: $_"; Invoke-Rollback; exit 1 }
    Start-Sleep -Seconds 30

    if (Test-HealthCheck) { Write-LogSuccess "Services deployed successfully" }
    else { Write-LogError "Some services are not healthy after deployment"; Invoke-Rollback; exit 1 }
}

# Health check
function Test-HealthCheck {
    Write-LogInfo "Performing health checks..."
    $allHealthy = $true

    $containers = & docker compose -p $PROJECT_NAME -f $COMPOSE_FILE ps -q
    foreach ($container in $containers) {
        $name = (& docker inspect --format '{{.Name}}' $container).TrimStart('/')
        $status = & docker inspect --format '{{.State.Status}}' $container
        if ($status -ne "running") { Write-LogError "$name is not running"; $allHealthy = $false }
        else { Write-LogSuccess "$name is running" }
    }

    # Los puertos solo escuchan en el loopback (Apache proxya desde 127.0.0.1)
    foreach ($check in @(@("Frontend", "http://127.0.0.1:$FRONTEND_PORT"), @("Backend", "http://127.0.0.1:$BACKEND_PORT/health/"))) {
        try {
            $response = Invoke-WebRequest -Uri $check[1] -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) { Write-LogSuccess "$($check[0]) ($($check[1])) is working" }
            else { Write-LogError "$($check[0]) answered $($response.StatusCode) on $($check[1])"; $allHealthy = $false }
        }
        catch { Write-LogError "$($check[0]) not accessible on $($check[1])"; $allHealthy = $false }
    }

    return $allHealthy
}

# Rollback: vuelve a las imágenes etiquetadas antes del último despliegue. La base solo con -ConBase.
function Invoke-Rollback {
    Write-LogWarning "Rolling back deployment..."

    if (-not (Test-Path $LAST_DEPLOY_FILE)) {
        Write-LogError "No ${LAST_DEPLOY_FILE}: there is no recorded deployment to roll back to."
        exit 1
    }
    $data = @{}
    Get-Content $LAST_DEPLOY_FILE | ForEach-Object { $k, $v = $_ -split "=", 2; $data[$k] = $v }
    $mark = $data["marca"]; $dbBackup = $data["base"]

    foreach ($svc in $APP_SERVICES) {
        & docker image inspect "${PROJECT_NAME}-${svc}:antes-$mark" *> $null
        if ($LASTEXITCODE -ne 0) { Write-LogError "Missing image ${PROJECT_NAME}-${svc}:antes-$mark. Rollback aborted."; exit 1 }
    }
    foreach ($svc in $APP_SERVICES) { Invoke-Docker tag "${PROJECT_NAME}-${svc}:antes-$mark" "${PROJECT_NAME}-${svc}:latest" }
    Write-LogInfo "Images restored to antes-$mark"

    if ($ConBase) {
        # Restaurar la base descarta lo ingerido desde el respaldo: solo a pedido y con el respaldo verificado
        if (-not (Test-Path $dbBackup) -or (Get-Item $dbBackup).Length -lt $MIN_BYTES) {
            Write-LogError "Backup $dbBackup is missing or too small. Database NOT restored."; exit 1
        }
        $inner = "/tmp/rollback_$mark.dump"
        try {
            Invoke-Compose cp $dbBackup "db:$inner"
            Invoke-Compose exec -T db pg_restore --list $inner | Out-Null
            Write-LogInfo "Restoring database from $dbBackup..."
            Invoke-Compose stop backend celery_worker celery_beat
            Invoke-Compose exec -T db pg_restore --clean --if-exists -U $DB_USER -d $DB_NAME $inner
            Write-LogSuccess "Database restored from $dbBackup"
        }
        catch { Write-LogError "Database restore failed: $_. Review the log before continuing." }
        finally { & docker compose -p $PROJECT_NAME -f $COMPOSE_FILE exec -T db rm -f $inner *> $null }
    }
    else {
        Write-LogInfo "Database left as is (use 'rollback -ConBase' to restore $dbBackup)"
    }

    Invoke-Compose up -d --no-deps backend
    Wait-Healthy "mte_backend_prod" | Out-Null
    Invoke-Compose up -d --no-deps celery_worker celery_beat frontend
    Write-LogWarning "Rollback completed to antes-$mark"
}

# Cleanup: solo imágenes colgantes (las etiquetadas antes-* se conservan para el rollback)
function Invoke-Cleanup {
    Write-LogInfo "Cleaning up dangling Docker images..."
    # Solo las del proyecto: un prune sin filtro borraría también las de otros proyectos.
    & docker image prune -f --filter "label=com.docker.compose.project=$PROJECT_NAME" | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-LogSuccess "Cleanup completed" } else { Write-LogWarning "Cleanup failed" }
}

# Main deployment function
function Invoke-Deploy {
    Write-LogInfo "Starting production deployment process..."
    Write-LogInfo "Deployment log: $DEPLOYMENT_LOG"

    Test-PreDeploymentChecks
    New-Backup
    Invoke-PullImages
    Invoke-BuildImages
    Invoke-DeployServices
    Invoke-Cleanup

    Write-LogSuccess "Production deployment completed successfully!"
    Write-LogInfo "Application (behind Apache): https://$SERVER_IP/sive/"
    Write-LogInfo "Rollback: .\deploy_production.ps1 rollback   (images)   |   .\deploy_production.ps1 rollback -ConBase   (images and database)"
}

# Show help
function Show-Help {
    Write-Host "MTE SIVE Production Deployment Script (Windows PowerShell)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\deploy_production.ps1 [COMMAND] [-ConBase]" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  deploy              Full production deployment (backup, build, backend first, then the rest)" -ForegroundColor White
    Write-Host "  health              Check service health (containers and 127.0.0.1 ports)" -ForegroundColor White
    Write-Host "  rollback            Return to the images tagged before the last deployment" -ForegroundColor White
    Write-Host "  rollback -ConBase   Same, and restore the database backup taken before that deployment" -ForegroundColor White
    Write-Host "  backup              Create backup only (database, media volume and image tag)" -ForegroundColor White
    Write-Host "  ssl                 Create self-signed SSL certificates (not used in production: Apache does TLS)" -ForegroundColor White
    Write-Host "  help                Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "Compose project: $PROJECT_NAME   Last deployment data: $LAST_DEPLOY_FILE" -ForegroundColor Green
}

# Main script logic
switch ($Command) {
    "deploy"   { Invoke-Deploy }
    "health"   { if (Test-HealthCheck) { exit 0 } else { exit 1 } }
    "rollback" { Invoke-Rollback }
    "backup"   { New-Backup }
    "ssl"      { New-SSLCertificates }
    default    { Show-Help }
}
