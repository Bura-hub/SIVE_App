#!/usr/bin/env bash
#
# backfill_mediciones.sh — Recupera en SIVE las mediciones que llegaron tarde al connector
# y recalcula los indicadores del rango. Va en scripts/ del repo SIVE_App.
#
# Por qué: la ingesta horaria solo pide las últimas 3 h y refetch_and_verify_yesterday solo
# el día anterior. Las RPi guardan en cola cuando pierden conexión (UCC corta internet de
# noche y los fines de semana; HUDN y UCC enviaron por tandas con días de retraso hasta el
# 26-sep-2026), así que esas lecturas nunca entraban. Contraste del 10-oct-2026 contra la
# base del connector (mte3): faltaban 64–72 % de filas de UCC (jun–sep 2026), 43–55 % de
# HUDN (jul–sep), 17 % de Udenar (ago), 4 % de Mariana (ago) y 1,7 % de Cesmag (sep).
#
# Qué hace (todo idempotente, no borra mediciones):
#   1. backup_db.sh (respaldo verificado; aborta si falla)
#   2. resync_measurements_v2 --force del rango (upsert por (device, date))
#   3. recalcula indicadores diarios y mensuales por componente, chart diario, KPI mensual
#      y rollup horario del rango
#
# Uso (desde la raíz del repo, en el host):
#   ./scripts/backfill_mediciones.sh 2026-05-01 2026-10-11      # el segundo es exclusivo
#
set -euo pipefail

DESDE="${1:?Uso: $0 DESDE(YYYY-MM-DD) HASTA_EXCLUSIVO(YYYY-MM-DD)}"
HASTA="${2:?Uso: $0 DESDE(YYYY-MM-DD) HASTA_EXCLUSIVO(YYYY-MM-DD)}"
ULTIMO_DIA="$(date -d "$HASTA -1 day" +%F)"
COMPOSE_FILE="docker-compose.prod.yml"
LOG="logs/backfill_mediciones_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

manage() { docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py "$@"; }

{
  echo "# orden: $0 $*"
  echo "# inicio: $(date -Is)"

  echo "== 1. respaldo"
  ./scripts/backup_db.sh

  echo "== 2. backfill de mediciones $DESDE -> $HASTA"
  manage resync_measurements_v2 --from "$DESDE" --to "$HASTA" --chunk-days 7 --force

  echo "== 3. recálculo de indicadores $DESDE -> $ULTIMO_DIA"
  for rango in daily monthly; do
    manage calculate_historical_electrical       --start-date "$DESDE" --end-date "$ULTIMO_DIA" --time-range "$rango"
    manage calculate_historical_inverters        --start-date "$DESDE" --end-date "$ULTIMO_DIA" --time-range "$rango"
    manage calculate_historical_weather_stations --start-date "$DESDE" --end-date "$ULTIMO_DIA" --time-range "$rango"
  done
  manage shell -c "from indicators.tasks import calculate_and_save_daily_data, calculate_monthly_consumption_kpi; calculate_and_save_daily_data.delay('$DESDE', '$ULTIMO_DIA'); calculate_monthly_consumption_kpi.delay(); print('chart diario y KPI mensual encolados')"
  manage backfill_hourly_rollup --start-date "$DESDE" --end-date "$ULTIMO_DIA"

  echo "# fin: $(date -Is)"
} 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
echo "# código de salida: $status" | tee -a "$LOG"
exit "$status"
