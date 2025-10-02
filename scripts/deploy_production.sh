#!/bin/bash

# ================================
# MTE SIVE - Production Deployment Script (Linux/Ubuntu)
# ================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="mte-sive"
ENV_FILE=".env"
BACKUP_DIR="./backups"
LOG_DIR="./logs"
DEPLOYMENT_LOG="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"

# Get server IP from .env or use default
SERVER_IP=""
if [ -f "$ENV_FILE" ]; then
    # Extract DOMAIN_NAME from .env file
    DOMAIN_LINE=$(grep "^DOMAIN_NAME=" "$ENV_FILE" | head -1)
    if [ -n "$DOMAIN_LINE" ]; then
        SERVER_IP=$(echo "$DOMAIN_LINE" | cut -d'=' -f2 | tr -d ' ')
    fi
fi

# Load environment variables from .env file
if [ -f "$ENV_FILE" ]; then
    # Load variables safely, avoiding issues with spaces and special characters
    while IFS= read -r line; do
        # Skip comments and empty lines
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
            continue
        fi
        # Export the variable
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            export "$line"
        fi
    done < "$ENV_FILE"
fi

if [ -z "$SERVER_IP" ]; then
    log_error "DOMAIN_NAME not found in .env file. Please set DOMAIN_NAME in your .env file."
    exit 1
fi

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

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found. Please create it from env.example"
        exit 1
    fi
    
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
    
    # Check SSL certificates for production
    if [ ! -d "./ssl" ] || [ ! -f "./ssl/cert.pem" ] || [ ! -f "./ssl/key.pem" ]; then
        log_warning "SSL certificates not found. Creating self-signed certificates..."
        create_ssl_certificates
    fi
    
    # Check disk space (at least 5GB free for production)
    available_space=$(df . | tail -1 | awk '{print $4}')
    available_space_gb=$((available_space / 1024 / 1024))
    
    if [ "$available_space" -lt 5242880 ]; then
        log_warning "Low disk space. At least 5GB recommended for production deployment. Available: ${available_space_gb}GB"
    fi
    
    log_success "Pre-deployment checks passed"
    log_info "Using server IP: $SERVER_IP"
}

# Create SSL certificates
create_ssl_certificates() {
    log_info "Creating SSL certificates for $SERVER_IP..."
    
    # Create ssl directory
    mkdir -p ssl
    
    # Check if OpenSSL is available
    if ! command -v openssl > /dev/null 2>&1; then
        log_error "OpenSSL is not installed or not in PATH. Please install OpenSSL first."
        log_info "Install with: sudo apt-get install openssl"
        exit 1
    fi
    
    # Generate self-signed certificate with server IP
    if openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem \
        -out ssl/cert.pem \
        -subj "/C=CO/ST=Bogota/L=Bogota/O=MTE/OU=IT/CN=$SERVER_IP" 2>/dev/null; then
        log_success "SSL certificates created for $SERVER_IP"
    else
        log_error "Failed to create SSL certificates"
        exit 1
    fi
}

# Create backup before deployment
create_backup() {
    log_info "Creating backup before deployment..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="$BACKUP_DIR/pre_deploy_backup_$timestamp.sql"
    
    # Get database credentials from .env with defaults
    user_postgres=${user_postgres:-BuraHub}
    name_db=${name_db:-sive_db}
    
    if docker compose -f docker-compose.prod.yml exec -T db pg_dump -U "$user_postgres" "$name_db" > "$backup_file" 2>/dev/null; then
        log_success "Database backup created: $backup_file"
    else
        log_warning "Could not create database backup (database might not be running)"
    fi
    
    # Backup media files
    if [ -d "./media" ]; then
        media_backup="$BACKUP_DIR/media_backup_$timestamp.tar.gz"
        if tar -czf "$media_backup" ./media 2>/dev/null; then
            log_success "Media files backup created: $media_backup"
        else
            log_warning "Failed to create media files backup"
        fi
    fi
}

# Pull latest images
pull_images() {
    log_info "Checking for latest Docker images..."
    if docker compose -f docker-compose.prod.yml pull --quiet 2>/dev/null; then
        log_success "External images updated successfully"
    else
        log_info "Some images will be built locally (this is normal for custom images)"
    fi
}

# Build new images
build_images() {
    log_info "Building new Docker images..."
    if docker compose -f docker-compose.prod.yml build --no-cache; then
        log_success "Images built successfully"
    else
        log_error "Failed to build images"
        exit 1
    fi
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    # Start only database first for migrations
    docker compose -f docker-compose.prod.yml up -d db
    sleep 10
    
    # Run migrations using a temporary backend container
    if docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate; then
        log_success "Migrations completed successfully"
    else
        log_error "Failed to run migrations"
        exit 1
    fi
}

# Collect static files
collect_static() {
    log_info "Collecting static files..."
    
    # Run collectstatic with --clear flag to avoid permission issues
    if docker compose -f docker-compose.prod.yml run --rm backend python manage.py collectstatic --noinput --clear; then
        log_success "Static files collected successfully"
    else
        log_error "Failed to collect static files"
        exit 1
    fi
}

# Deploy services
deploy_services() {
    log_info "Deploying services..."
    
    # Stop existing services
    docker compose -f docker-compose.prod.yml down
    
    # Start services in order: database first, then backend, then others
    log_info "Starting database and Redis..."
    if ! docker compose -f docker-compose.prod.yml up -d db redis; then
        log_error "Failed to start database and Redis"
        exit 1
    fi
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 15
    
    # Start backend
    log_info "Starting backend..."
    if ! docker compose -f docker-compose.prod.yml up -d backend; then
        log_error "Failed to start backend"
        exit 1
    fi
    
    # Wait for backend to be ready
    log_info "Waiting for backend to be ready..."
    sleep 10
    
    # Start remaining services
    log_info "Starting remaining services..."
    if ! docker compose -f docker-compose.prod.yml up -d; then
        log_error "Failed to start remaining services"
        exit 1
    fi
    
    # Wait for all services to be healthy
    log_info "Waiting for all services to be healthy..."
    sleep 30
    
    # Check health
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
    
    # Check if all containers are running
    containers=$(docker compose -f docker-compose.prod.yml ps -q)
    all_healthy=true
    
    for container in $containers; do
        name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
        status=$(docker inspect --format='{{.State.Status}}' "$container")
        
        if [ "$status" != "running" ]; then
            log_error "$name is not running"
            all_healthy=false
        else
            log_success "$name is running"
        fi
    done
    
    # Check direct ports (Nginx eliminado)
    FRONTEND_PORT=${FRONTEND_PORT:-3503}
    BACKEND_PORT=${BACKEND_PORT:-3504}
    DOMAIN_NAME=${DOMAIN_NAME:-$SERVER_IP}
    
    # Check if curl is available
    if ! command -v curl > /dev/null 2>&1; then
        log_warning "curl is not available, skipping port checks"
        return $([ "$all_healthy" = true ] && echo 0 || echo 1)
    fi
    
    if curl -f -s http://$DOMAIN_NAME:$FRONTEND_PORT > /dev/null 2>&1; then
        log_success "Frontend direct port ($FRONTEND_PORT) is working"
    else
        log_error "Frontend not accessible on port $FRONTEND_PORT"
        all_healthy=false
    fi
    
    if curl -f -s http://$DOMAIN_NAME:$BACKEND_PORT/health/ > /dev/null 2>&1; then
        log_success "Backend direct port ($BACKEND_PORT) is working"
    else
        log_error "Backend not accessible on port $BACKEND_PORT"
        all_healthy=false
    fi
    
    return $([ "$all_healthy" = true ] && echo 0 || echo 1)
}

# Rollback function
rollback() {
    log_warning "Rolling back deployment..."
    
    # Stop current services
    docker compose -f docker-compose.prod.yml down
    
    # Restore from backup if available
    latest_backup=$(ls -t "$BACKUP_DIR"/pre_deploy_backup_*.sql 2>/dev/null | head -1)
    if [ -n "$latest_backup" ]; then
        log_info "Restoring database from backup: $(basename "$latest_backup")"
        
        # Get database credentials from .env with defaults
        user_postgres=${user_postgres:-BuraHub}
        name_db=${name_db:-sive_db}
        
        # Start database first
        docker compose -f docker-compose.prod.yml up -d db
        sleep 10
        
        # Restore database
        if docker compose -f docker-compose.prod.yml exec -T db psql -U "$user_postgres" -d "$name_db" < "$latest_backup"; then
            log_success "Database restored from backup"
        else
            log_error "Failed to restore database from backup"
        fi
    else
        log_warning "No backup found for rollback"
    fi
    
    # Start previous version
    docker compose -f docker-compose.prod.yml up -d
    
    log_warning "Rollback completed"
}

# Post-deployment tasks
post_deployment() {
    log_info "Running post-deployment tasks..."
    
    # Clear cache
    if docker compose -f docker-compose.prod.yml exec -T backend python manage.py clear_cache 2>/dev/null; then
        log_success "Cache cleared successfully"
    else
        log_warning "Cache clear command not available"
    fi
    
    # Restart Celery workers
    docker compose -f docker-compose.prod.yml restart celery_worker celery_beat
    
    log_success "Post-deployment tasks completed"
}

# Cleanup old images
cleanup() {
    log_info "Cleaning up old Docker images..."
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
    log_info "Target server: $SERVER_IP"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    
    # Run deployment steps
    pre_deployment_checks
    create_backup
    pull_images
    build_images
    run_migrations
    collect_static
    deploy_services
    post_deployment
    cleanup
    
    log_success "Production deployment completed successfully!"
    log_info "Application is available at:"
    # Get port values from environment or use defaults
    FRONTEND_PORT=${FRONTEND_PORT:-3503}
    BACKEND_PORT=${BACKEND_PORT:-3504}
    DOMAIN_NAME=${DOMAIN_NAME:-$SERVER_IP}
    
    log_info "  Frontend: http://$DOMAIN_NAME:$FRONTEND_PORT"
    log_info "  Backend:  http://$DOMAIN_NAME:$BACKEND_PORT"
    log_info ""
    log_info "Admin panel: http://$DOMAIN_NAME:$BACKEND_PORT/admin"
    log_info "API docs: http://$DOMAIN_NAME:$BACKEND_PORT/api/schema/swagger-ui/"
}

# Show help
show_help() {
    echo -e "${CYAN}MTE SIVE Production Deployment Script (Linux/Ubuntu)${NC}"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy          Full production deployment process"
    echo "  health          Check service health"
    echo "  rollback        Rollback to previous version"
    echo "  backup          Create backup only"
    echo "  ssl             Create SSL certificates"
    echo "  help            Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  DOMAIN_NAME     Domain name for the application (default: localhost)"
    echo "  FRONTEND_PORT   Frontend port (default: 3503)"
    echo "  BACKEND_PORT    Backend port (default: 3504)"
    echo "  user_postgres   PostgreSQL username (default: BuraHub)"
    echo "  name_db         Database name (default: sive_db)"
    echo ""
    echo -e "Current server IP: ${GREEN}$SERVER_IP${NC}"
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
        rollback
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