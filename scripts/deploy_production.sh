#!/bin/bash

# ================================
# MTE SIVE - Production Deployment Script (Linux/Ubuntu)
# ================================
#
# Reescrito el 22-oct-2026 para el despliegue real (proyecto compose «mtesive_app», Apache delante y puertos solo en
# 127.0.0.1). La versión anterior no servía en producción:
#   - llamaba a docker compose sin -p mtesive_app, así que creaba otro proyecto que chocaba con los container_name;
#   - su salud consultaba http://DOMAIN_NAME:3503, pero los puertos solo escuchan en 127.0.0.1: fallaba y disparaba el
#     rollback en cada despliegue;
#   - hacía «docker compose down» (bajaba también PostgreSQL y Redis) en cada despliegue y en cada rollback;
#   - su respaldo (pg_dump a .sql con 2>/dev/null) dejaba archivos vacíos dados por buenos (13 de 19 en backups/), y el
#     rollback restauraba «el último» con psql sin comprobarlo; el respaldo de media empaquetaba ./media, que está en un
#     volumen de Docker y no en el host (archivos de 117 bytes);
#   - el rollback no volvía a las imágenes anteriores: reiniciaba las mismas.
# Ahora: respaldo verificado con backup_db.sh --manual y del volumen de media, etiqueta antes-<marca> de las imágenes
# actuales, backend primero y el resto después, sin down, y un rollback que vuelve a esas imágenes. La base solo se
# restaura si se pide (rollback --con-base), con pg_restore y tras verificar el respaldo.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="mtesive_app"            # proyecto compose de producción (contenedores mte_*_prod)
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
BACKUP_DIR="./backups"
LOG_DIR="./logs"
APP_SERVICES="backend celery_worker celery_beat frontend"   # los que se construyen; db y redis no se tocan
MEDIA_VOLUME="${PROJECT_NAME}_media_data_prod"
LAST_DEPLOY_FILE="$BACKUP_DIR/ultimo_despliegue.txt"
mkdir -p "$LOG_DIR"
DEPLOYMENT_LOG="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"

# Functions
log_info() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[$timestamp] [INFO]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_success() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[$timestamp] [SUCCESS]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_warning() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[$timestamp] [WARNING]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_error() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[$timestamp] [ERROR]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

# docker compose siempre con el proyecto de producción
dc() {
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

# Lee una clave del .env sin ejecutarlo (como backup_db.sh)
read_env() {
    sed -n "s/^$1=//p" "$ENV_FILE" | tail -1 | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

[ -f "$ENV_FILE" ] || { echo ".env file not found. Run from the repository root."; exit 1; }
SERVER_IP="$(read_env DOMAIN_NAME)"
FRONTEND_PORT="$(read_env FRONTEND_PORT)"; FRONTEND_PORT="${FRONTEND_PORT:-3503}"
BACKEND_PORT="$(read_env BACKEND_PORT)";   BACKEND_PORT="${BACKEND_PORT:-3504}"
DB_USER="$(read_env user_postgres)";       DB_USER="${DB_USER:-BuraHub}"
DB_NAME="$(read_env name_db)";             DB_NAME="${DB_NAME:-sive_db}"

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check if docker compose is available
    if ! docker compose version > /dev/null 2>&1; then
        log_error "docker compose is not installed or not in PATH"
        exit 1
    fi

    # El TLS lo termina Apache en el host: los contenedores no montan ./ssl, así que no se generan certificados aquí.

    # Check disk space (at least 5GB free for production)
    available_space=$(df . | tail -1 | awk '{print $4}')
    available_space_gb=$((available_space / 1024 / 1024))

    if [ "$available_space" -lt 5242880 ]; then
        log_warning "Low disk space. At least 5GB recommended for production deployment. Available: ${available_space_gb}GB"
    fi

    log_success "Pre-deployment checks passed"
}

# Create SSL certificates (solo para entornos sin Apache delante; producción no los usa)
create_ssl_certificates() {
    log_info "Creating SSL certificates for $SERVER_IP..."

    mkdir -p ssl

    if ! command -v openssl > /dev/null 2>&1; then
        log_error "OpenSSL is not installed or not in PATH. Please install OpenSSL first."
        log_info "Install with: sudo apt-get install openssl"
        exit 1
    fi

    if openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem \
        -out ssl/cert.pem \
        -subj "/C=CO/ST=Bogota/L=Bogota/O=MTE/OU=IT/CN=$SERVER_IP"; then
        log_success "SSL certificates created for $SERVER_IP (ssl/*.pem está en .gitignore)"
    else
        log_error "Failed to create SSL certificates"
        exit 1
    fi
}

# Create backup before deployment: base (verificada), volumen de media y etiqueta de las imágenes actuales.
# Si algo falla, aborta: no se despliega sin respaldo.
create_backup() {
    log_info "Creating backup before deployment..."
    mkdir -p "$BACKUP_DIR"
    mark=$(date +"%Y%m%d_%H%M%S")

    # Base: backup_db.sh --manual ya verifica tamaño y pg_restore --list, y no rota los diarios.
    if ! ./scripts/backup_db.sh --manual | tee -a "$DEPLOYMENT_LOG"; then
        log_error "Database backup failed. Aborting deployment."
        exit 1
    fi
    db_backup=$(ls -1t "$BACKUP_DIR"/manual_sive_db_*.dump | head -1)

    # Media: desde el volumen, con la imagen del backend (lleva tar), en solo lectura. tar escribe a stdout y el
    # archivo lo crea el host: el usuario del contenedor no puede escribir en backups/.
    media_backup="$BACKUP_DIR/manual_media_$mark.tar.gz"
    if ! docker run --rm --entrypoint tar -v "$MEDIA_VOLUME":/media:ro \
            "${PROJECT_NAME}-backend:latest" czf - -C /media . > "$media_backup"; then
        rm -f "$media_backup"
        log_error "Media backup failed. Aborting deployment."
        exit 1
    fi
    media_files=$(tar -tzf "$media_backup" | grep -vc '/$' || true)
    log_success "Media backup: $media_backup ($media_files files)"
    # Misma retención que los respaldos manuales de la base (KEEP_MANUAL=10 en backup_db.sh)
    ls -1t "$BACKUP_DIR"/manual_media_*.tar.gz 2>/dev/null | tail -n +11 | while read -r old; do
        log_info "Retención: eliminando $old"; rm -f "$old"
    done

    # Imágenes actuales: etiqueta antes-<marca> para el rollback.
    for svc in $APP_SERVICES; do
        docker tag "${PROJECT_NAME}-${svc}:latest" "${PROJECT_NAME}-${svc}:antes-$mark"
    done
    log_success "Current images tagged antes-$mark"

    printf 'marca=%s\nbase=%s\nmedia=%s\ncommit=%s\n' "$mark" "$db_backup" "$media_backup" \
        "$(git rev-parse --short HEAD 2>/dev/null || echo desconocido)" > "$LAST_DEPLOY_FILE"
    log_success "Rollback data written to $LAST_DEPLOY_FILE"
}

# Pull latest images (solo las externas: postgres y redis)
pull_images() {
    log_info "Checking for latest external Docker images..."
    if dc pull --quiet db redis; then
        log_success "External images updated successfully"
    else
        log_warning "Could not pull external images; using the local ones"
    fi
}

# Build new images
build_images() {
    log_info "Building new Docker images..."
    if dc build $APP_SERVICES; then
        log_success "Images built successfully"
    else
        log_error "Failed to build images"
        exit 1
    fi
}

# Espera a que un contenedor quede healthy (o falla)
wait_healthy() {
    local container="$1" tries="${2:-40}" status=""
    for _ in $(seq 1 "$tries"); do
        status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo ausente)
        [ "$status" = "healthy" ] && return 0
        sleep 5
    done
    log_error "$container is $status after $((tries * 5)) s"
    return 1
}

# Deploy services: sin down. db y redis siguen arriba; el backend (que migra al arrancar) va primero.
deploy_services() {
    log_info "Deploying services..."

    if ! dc up -d db redis; then
        log_error "Failed to start database and Redis"
        exit 1
    fi

    log_info "Starting backend (runs migrate and collectstatic on start)..."
    dc up -d --no-deps backend
    if ! wait_healthy mte_backend_prod; then
        log_error "Backend not healthy"
        rollback
        exit 1
    fi

    log_info "Starting Celery and frontend..."
    dc up -d --no-deps celery_worker celery_beat frontend
    sleep 30

    if health_check; then
        log_success "Services deployed successfully"
    else
        log_error "Some services are not healthy after deployment"
        rollback
        exit 1
    fi
}

# Health check
health_check() {
    log_info "Performing health checks..."
    all_healthy=true

    for container in $(dc ps -q); do
        name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
        status=$(docker inspect --format='{{.State.Status}}' "$container")
        if [ "$status" != "running" ]; then
            log_error "$name is not running"
            all_healthy=false
        else
            log_success "$name is running"
        fi
    done

    # Los puertos solo escuchan en el loopback (Apache proxya desde 127.0.0.1).
    if curl -f -s "http://127.0.0.1:$FRONTEND_PORT" > /dev/null 2>&1; then
        log_success "Frontend (127.0.0.1:$FRONTEND_PORT) is working"
    else
        log_error "Frontend not accessible on 127.0.0.1:$FRONTEND_PORT"
        all_healthy=false
    fi

    if curl -f -s "http://127.0.0.1:$BACKEND_PORT/health/" > /dev/null 2>&1; then
        log_success "Backend (127.0.0.1:$BACKEND_PORT/health/) is working"
    else
        log_error "Backend not accessible on 127.0.0.1:$BACKEND_PORT/health/"
        all_healthy=false
    fi

    [ "$all_healthy" = true ]
}

# Rollback: vuelve a las imágenes etiquetadas antes del último despliegue. La base solo con --con-base.
rollback() {
    local con_base="${1:-}"
    log_warning "Rolling back deployment..."

    if [ ! -f "$LAST_DEPLOY_FILE" ]; then
        log_error "No $LAST_DEPLOY_FILE: there is no recorded deployment to roll back to."
        exit 1
    fi
    mark=$(sed -n 's/^marca=//p' "$LAST_DEPLOY_FILE")
    db_backup=$(sed -n 's/^base=//p' "$LAST_DEPLOY_FILE")

    for svc in $APP_SERVICES; do
        if ! docker image inspect "${PROJECT_NAME}-${svc}:antes-$mark" > /dev/null 2>&1; then
            log_error "Missing image ${PROJECT_NAME}-${svc}:antes-$mark. Rollback aborted."
            exit 1
        fi
    done
    for svc in $APP_SERVICES; do
        docker tag "${PROJECT_NAME}-${svc}:antes-$mark" "${PROJECT_NAME}-${svc}:latest"
    done
    log_info "Images restored to antes-$mark"

    if [ "$con_base" = "--con-base" ]; then
        # Restaurar la base descarta lo ingerido desde el respaldo: solo a pedido y con el respaldo verificado.
        if [ ! -s "$db_backup" ] || ! dc exec -T db pg_restore --list < "$db_backup" > /dev/null 2>&1; then
            log_error "Backup $db_backup is missing or unreadable. Database NOT restored."
            exit 1
        fi
        log_info "Restoring database from $db_backup..."
        dc stop backend celery_worker celery_beat
        if dc exec -T db pg_restore --clean --if-exists -U "$DB_USER" -d "$DB_NAME" < "$db_backup"; then
            log_success "Database restored from $db_backup"
        else
            log_error "pg_restore reported errors; review the log before continuing"
        fi
    else
        log_info "Database left as is (use 'rollback --con-base' to restore $db_backup)"
    fi

    dc up -d --no-deps backend
    wait_healthy mte_backend_prod || true
    dc up -d --no-deps celery_worker celery_beat frontend
    log_warning "Rollback completed to antes-$mark"
}

# Post-deployment tasks
post_deployment() {
    log_info "Running post-deployment tasks..."
    # Celery ya arrancó con la imagen nueva en deploy_services; no hace falta reiniciarlo.
    log_success "Post-deployment tasks completed"
}

# Cleanup: solo imágenes colgantes (las etiquetadas antes-* se conservan para el rollback)
cleanup() {
    log_info "Cleaning up dangling Docker images..."
    if docker image prune -f; then
        log_success "Cleanup completed"
    else
        log_warning "Cleanup failed"
    fi
}

# Main deployment function
deploy() {
    log_info "Starting production deployment process..."
    log_info "Deployment log: $DEPLOYMENT_LOG"

    pre_deployment_checks
    create_backup
    pull_images
    build_images
    deploy_services
    post_deployment
    cleanup

    log_success "Production deployment completed successfully!"
    log_info "Application (behind Apache): https://$SERVER_IP/sive/"
    log_info "Rollback: $0 rollback   (images)   |   $0 rollback --con-base   (images and database)"
}

# Show help
show_help() {
    echo -e "${CYAN}MTE SIVE Production Deployment Script (Linux/Ubuntu)${NC}"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy                Full production deployment (backup, build, backend first, then the rest)"
    echo "  health                Check service health (containers and 127.0.0.1 ports)"
    echo "  rollback              Return to the images tagged before the last deployment"
    echo "  rollback --con-base   Same, and restore the database backup taken before that deployment"
    echo "  backup                Create backup only (database, media volume and image tag)"
    echo "  ssl                   Create self-signed SSL certificates (not used in production: Apache does TLS)"
    echo "  help                  Show this help message"
    echo ""
    echo "Compose project: $PROJECT_NAME   Last deployment data: $LAST_DEPLOY_FILE"
}

# Main script logic
case "${1:-help}" in
    "deploy")
        deploy
        ;;
    "health")
        health_check
        ;;
    "rollback")
        rollback "${2:-}"
        ;;
    "backup")
        create_backup
        ;;
    "ssl")
        create_ssl_certificates
        ;;
    "help"|*)
        show_help
        ;;
esac
