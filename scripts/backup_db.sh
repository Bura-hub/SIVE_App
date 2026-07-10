#!/usr/bin/env bash
#
# backup_db.sh — Backup verificado de la BD de SIVE (Ola 0 del plan de remediación).
#
# Corrige los defectos de los backups previos (auditoría): formato custom (pg_restore),
# NO silencia stderr, ABORTA si el dump queda vacío, y aplica retención.
#
# Uso (desde la raíz del repo, en el host):
#   ./scripts/backup_db.sh            # backup diario
#   ./scripts/backup_db.sh --weekly   # además rota una copia semanal
#
# Cron sugerido (diario 02:30; domingos con --weekly):
#   30 2 * * 1-6  cd /ruta/al/repo && ./scripts/backup_db.sh          >> logs/backup.log 2>&1
#   30 2 * * 0    cd /ruta/al/repo && ./scripts/backup_db.sh --weekly >> logs/backup.log 2>&1
#
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"
MIN_BYTES=10000          # un dump válido de esta BD pesa MB; <10 KB = fallo
KEEP_DAILY=7
KEEP_WEEKLY=4

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

# --- Leer credenciales desde .env SIN ejecutarlo ---
# (source .env rompe si algún valor tiene caracteres de shell, p.ej. la SECRET_KEY.)
[ -f .env ] || die "No se encontró .env en $(pwd). Ejecuta desde la raíz del repo."
read_env() {  # $1 = clave; imprime el valor sin comillas envolventes
    sed -n "s/^$1=//p" .env | tail -1 | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}
DB_NAME="$(read_env name_db)";        DB_NAME="${DB_NAME:-sive_db}"
DB_USER="$(read_env user_postgres)";  DB_USER="${DB_USER:-BuraHub}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date '+%Y%m%d_%H%M%S')"
outfile="$BACKUP_DIR/sive_db_${timestamp}.dump"

log "Iniciando pg_dump (-Fc) de '$DB_NAME' como '$DB_USER' -> $outfile"

# Formato custom comprimido. SIN 2>/dev/null: si falla, lo vemos y abortamos.
if ! docker compose -f "$COMPOSE_FILE" exec -T db \
        pg_dump -Fc -U "$DB_USER" "$DB_NAME" > "$outfile"; then
    rm -f "$outfile"
    die "pg_dump falló. No se generó backup."
fi

# Verificar tamaño > umbral (un pg_dump vacío/erróneo es pequeño).
size=$(stat -c%s "$outfile" 2>/dev/null || stat -f%z "$outfile")
if [ "$size" -lt "$MIN_BYTES" ]; then
    rm -f "$outfile"
    die "El dump quedó en $size bytes (< $MIN_BYTES). Se descarta como inválido."
fi

# Verificar que pg_restore puede LEER el archivo (integridad del formato custom).
if ! docker compose -f "$COMPOSE_FILE" exec -T db pg_restore --list < "$outfile" >/dev/null 2>&1; then
    rm -f "$outfile"
    die "pg_restore --list no pudo leer el dump. Archivo corrupto, se descarta."
fi

log "Backup OK: $outfile ($(numfmt --to=iec "$size" 2>/dev/null || echo "${size} bytes"))"

# --- Rotación semanal opcional ---
if [ "${1:-}" = "--weekly" ]; then
    weekly="$BACKUP_DIR/weekly_sive_db_${timestamp}.dump"
    cp "$outfile" "$weekly"
    log "Copia semanal: $weekly"
fi

# --- Retención: conservar los N más recientes de cada tipo ---
prune() {  # $1 = glob, $2 = cuántos conservar
    local pattern="$1" keep="$2"
    # ls por mtime desc; borra a partir del keep+1
    ls -1t $pattern 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do
        log "Retención: eliminando $old"
        rm -f "$old"
    done
}
prune "$BACKUP_DIR/sive_db_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly_sive_db_*.dump" "$KEEP_WEEKLY"

log "Backup finalizado correctamente."

# Recordatorio de copia off-host (no automatizado aquí a propósito): el volumen de
# Postgres vive en el mismo disco del host. Configurar un rsync/scp de $BACKUP_DIR a
# otra máquina cierra el riesgo de pérdida total por fallo de disco.
