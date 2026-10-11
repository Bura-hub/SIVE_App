#!/usr/bin/env bash
#
# recalcular_historico.sh — Recalcula TODOS los indicadores guardados con las fórmulas vigentes, en un rango.
#
# Hace falta tras desplegar cambios de cálculo (p. ej. la corrección de octubre de 2026, C1–C16: la migración 0028
# deja en nulo el FP, la eficiencia y el PR del inversor guardados en la escala vieja). Todo es idempotente
# (update_or_create); los comandos encolan tareas en Celery, así que el trabajo sigue en el worker después de que el
# script termine: mírese `docker compose -f docker-compose.prod.yml logs -f celery_worker`.
#
# Uso (desde la raíz del repo, en el host):
#   ./scripts/recalcular_historico.sh 2025-02-01 2026-10-10
#
set -euo pipefail

DESDE="${1:?Uso: $0 DESDE(YYYY-MM-DD) HASTA(YYYY-MM-DD, inclusivo)}"
HASTA="${2:?Uso: $0 DESDE(YYYY-MM-DD) HASTA(YYYY-MM-DD, inclusivo)}"
COMPOSE_FILE="docker-compose.prod.yml"
LOG="logs/recalcular_historico_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

manage() { docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py "$@"; }

{
  echo "# orden: $0 $*"
  echo "# inicio: $(date -Is)"
  for rango in daily monthly; do
    manage calculate_historical_electrical       --start-date "$DESDE" --end-date "$HASTA" --time-range "$rango"
    manage calculate_historical_inverters        --start-date "$DESDE" --end-date "$HASTA" --time-range "$rango"
    manage calculate_historical_weather_stations --start-date "$DESDE" --end-date "$HASTA" --time-range "$rango"
  done
  manage shell -c "
from indicators.tasks import calculate_and_save_daily_data, calculate_monthly_consumption_kpi
from external_energy.tasks import calculate_energy_savings
calculate_and_save_daily_data.delay('$DESDE', '$HASTA')
calculate_monthly_consumption_kpi.delay()
calculate_energy_savings.delay(start_date_str='$DESDE', end_date_str='$HASTA')
print('chart diario, KPI mensual y ahorro encolados')"
  manage backfill_hourly_rollup --start-date "$DESDE" --end-date "$HASTA"
  echo "# fin: $(date -Is)"
} 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
echo "# código de salida: $status" | tee -a "$LOG"
exit "$status"
