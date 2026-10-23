import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

from .services import XMEnergyService

logger = logging.getLogger(__name__)

# Inicio del backfill de ahorros: primera fecha con datos reales agregados en
# DailyChartData (indicators). Antes de esta fecha no hay consumo/generación medidos.
SAVINGS_BACKFILL_START = date(2025, 2, 25)


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def sync_external_energy_data(self):
    """Sincroniza datos externos de energía (XM) fuera del ciclo request/response de Django.

    Persiste los precios de XM agregados a nivel diario (ver `XMEnergyService.sync_all_data`).
    Ejecutar las llamadas a XM dentro de una tarea Celery evita bloquear las vistas HTTP con
    peticiones de red potencialmente lentas.
    """
    try:
        service = XMEnergyService()
        result = service.sync_all_data()

        if 'error' in result:
            logger.error(
                "Sincronización XM finalizó con error: %s", result['error']
            )
        else:
            logger.info(
                "Sincronización XM completada: %s precios (%s nuevos, %s actualizados)",
                result.get('prices_synced', 0),
                result.get('prices_created', 0),
                result.get('prices_updated', 0),
            )
        return result

    except Exception as e:
        logger.error(
            "Error inesperado en la tarea sync_external_energy_data: %s", str(e),
            exc_info=True,
        )
        raise


SAVINGS_RECALC_DAYS = 40


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def calculate_energy_savings(self, recalc_days=SAVINGS_RECALC_DAYS, start_date_str=None, end_date_str=None):
    """Ahorro DIARIO de las plantas del proyecto con la tarifa al usuario.

    Para cada día y cada institución configurada (indicators/institution_config.py):
      - consumed  = demanda del circuito del Medidor 1 (kWh, misma convención que el mercado P2P)
      - generated = generación del inversor de la planta (kWh)
      - ahorro    = energía AUTOCONSUMIDA × CU mensual del comercializador (ASC nivel 2 para Udenar,
                    Mariana, UCC y HUDN; Cedenar nivel 2 para Cesmag; indicators/data/tarifas_cu.csv).
                    Los meses sin tarifa publicada usan la última disponible (tarifa extrapolada).
    Se guarda la suma de las instituciones; average_price_kwh es el CU efectivo (ahorro / autoconsumo).
    self_consumption_percentage = autoconsumo / generación; excess_energy_kwh = energía exportada;
    savings_percentage = autoconsumo / demanda (fracción de la demanda que no se compró a la red).

    Antes: min(generación, consumo bruto de TODOS los medidores) × PRECIO DE BOLSA de XM. El precio de bolsa no
    es lo que paga una institución (el CU es 2–3 veces mayor), y los días ya calculados no se recalculaban nunca,
    aunque llegaran lecturas tardías. Ahora se recalculan siempre los últimos `recalc_days` días, más los que
    falten desde SAVINGS_BACKFILL_START (o el rango explícito start/end, para un recálculo completo).
    """
    from datetime import datetime as _dt
    from collections import defaultdict
    from indicators.institution_config import INSTITUCIONES
    from indicators.services.institution_energy import energia_horaria
    from indicators.services.solar_kpis import cargar_tarifas, cu_del_mes
    from .models import EnergySavings

    yesterday = timezone.localdate() - timedelta(days=1)
    if start_date_str and end_date_str:
        desde = _dt.strptime(start_date_str, '%Y-%m-%d').date()
        hasta = _dt.strptime(end_date_str, '%Y-%m-%d').date()
        dias = {desde + timedelta(days=i) for i in range((hasta - desde).days + 1)}
    else:
        if yesterday < SAVINGS_BACKFILL_START:
            return {'created': 0, 'detail': 'Rango vacío: aún no hay días que calcular'}
        existentes = set(EnergySavings.objects.filter(date__range=(SAVINGS_BACKFILL_START, yesterday))
                         .values_list('date', flat=True))
        todos = {SAVINGS_BACKFILL_START + timedelta(days=i)
                 for i in range((yesterday - SAVINGS_BACKFILL_START).days + 1)}
        recientes = {yesterday - timedelta(days=i) for i in range(recalc_days)}
        dias = (todos - existentes) | (recientes & todos)
    if not dias:
        return {'created': 0, 'updated': 0}

    tarifas = cargar_tarifas()
    por_dia = defaultdict(lambda: {'d': 0.0, 'g': 0.0, 'auto': 0.0, 'exp': 0.0, 'ahorro': 0.0, 'extrap': False})
    desde, hasta = min(dias), max(dias)
    for scada_id, cfg in INSTITUCIONES.items():
        tarifas_com = tarifas[cfg['comercializador']]
        for h in energia_horaria(scada_id, desde, hasta):
            dia = h['hora'].date()
            if dia not in dias:
                continue
            acc = por_dia[dia]
            acc['g'] += h['g_kwh']
            if h['d_kwh'] is None:
                continue
            cu, extrap = cu_del_mes(tarifas_com, dia.strftime('%Y-%m'))
            acc['d'] += h['d_kwh']
            acc['auto'] += h['autoconsumo_kwh']
            acc['exp'] += h['export_kwh']
            acc['ahorro'] += h['autoconsumo_kwh'] * cu
            acc['extrap'] |= extrap

    def dec(x, q='0.01'):
        return Decimal(str(x)).quantize(Decimal(q))

    creados = actualizados = 0
    for dia in sorted(dias):
        acc = por_dia.get(dia)
        if acc is None or (acc['d'] == 0 and acc['g'] == 0):
            continue
        _, nuevo = EnergySavings.objects.update_or_create(date=dia, defaults={
            'total_consumed_kwh': dec(acc['d']),
            'total_generated_kwh': dec(acc['g']),
            'average_price_kwh': dec(acc['ahorro'] / acc['auto'], '0.0001') if acc['auto'] else Decimal('0'),
            'total_savings_cop': dec(acc['ahorro']),
            'savings_percentage': dec(min(100.0, 100 * acc['auto'] / acc['d'])) if acc['d'] else Decimal('0'),
            'self_consumption_percentage': dec(min(100.0, 100 * acc['auto'] / acc['g'])) if acc['g'] else Decimal('0'),
            'excess_energy_kwh': dec(acc['exp']),
        })
        creados += int(nuevo)
        actualizados += int(not nuevo)
    resultado = {'created': creados, 'updated': actualizados,
                 'range': {'start': desde.isoformat(), 'end': hasta.isoformat()}}
    logger.info("calculate_energy_savings completada: %s", resultado)
    return resultado
