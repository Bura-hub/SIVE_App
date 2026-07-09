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


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def calculate_energy_savings(self):
    """Calcula y persiste EnergySavings DIARIOS reales a partir de datos locales.

    Para cada fecha desde SAVINGS_BACKFILL_START hasta AYER (hora Bogotá) que aún no
    tenga registro EnergySavings:
      - consumed  = DailyChartData.daily_gross_consumption (kWh, indicators)
      - generated = DailyChartData.daily_generation (kWh)
      - price     = EnergyPrice de esa fecha; fallback: el último precio ANTERIOR.
                    Sin precio en o antes de la fecha, el día se OMITE (no se inventan
                    precios; el siguiente run lo reintenta cuando haya precio).
      - El resto de campos se calcula con la MISMA semántica del modelo EnergySavings
        (su save() los recalcula cuando consumed>0 y generated>0): el ahorro es el
        valor de la generación acotado por el costo del consumo
        (min(generated, consumed) × price), autoconsumo y excedentes coherentes.

    Idempotente: upsert por fecha; los días ya existentes no se tocan y re-ejecutar
    no duplica registros. Programada diariamente a las 03:30 (después del sync de
    precios de XM de las 03:00); ver CELERY_BEAT_SCHEDULE.
    """
    # Imports diferidos: evitan dependencias circulares entre apps al cargar el módulo.
    from indicators.models import DailyChartData
    from .models import EnergyPrice, EnergySavings

    try:
        yesterday = timezone.localdate() - timedelta(days=1)
        start = SAVINGS_BACKFILL_START
        if yesterday < start:
            return {'created': 0, 'detail': 'Rango vacío: aún no hay días que calcular'}

        existing_dates = set(
            EnergySavings.objects.filter(date__range=(start, yesterday))
            .values_list('date', flat=True)
        )
        chart_by_date = {
            row.date: row
            for row in DailyChartData.objects.filter(date__range=(start, yesterday))
        }
        # Precios ordenados por fecha para resolver "precio del día o el último anterior".
        price_dates = []
        price_values = {}
        for p in EnergyPrice.objects.filter(date__lte=yesterday).order_by('date'):
            price_dates.append(p.date)
            price_values[p.date] = p.price_per_kwh

        import bisect

        def price_for(day):
            """Precio del día o el último anterior; None si no hay ninguno <= day."""
            idx = bisect.bisect_right(price_dates, day)
            if idx == 0:
                return None
            return price_values[price_dates[idx - 1]]

        created = 0
        skipped_no_chart = 0
        skipped_no_price = 0

        day = start
        while day <= yesterday:
            if day in existing_dates:
                day += timedelta(days=1)
                continue

            chart = chart_by_date.get(day)
            if chart is None:
                skipped_no_chart += 1
                day += timedelta(days=1)
                continue

            price = price_for(day)
            if price is None:
                skipped_no_price += 1
                day += timedelta(days=1)
                continue

            consumed = Decimal(str(round(chart.daily_gross_consumption or 0.0, 2)))
            generated = Decimal(str(round(chart.daily_generation or 0.0, 2)))
            price = Decimal(price).quantize(Decimal('0.0001'))

            # Misma semántica que EnergySavings.save(): valor de la generación acotado
            # por el costo del consumo. Se calcula también aquí para cubrir los días con
            # consumo o generación en 0, donde save() no recalcula.
            consumed_cost = consumed * price
            generated_value = generated * price
            total_savings = min(generated_value, consumed_cost).quantize(Decimal('0.01'))
            savings_pct = (
                (total_savings / consumed_cost * 100).quantize(Decimal('0.01'))
                if consumed_cost > 0 else Decimal('0')
            )
            self_consumption_pct = (
                min(generated / consumed * 100, Decimal('100')).quantize(Decimal('0.01'))
                if consumed > 0 else Decimal('0')
            )
            excess = max(Decimal('0'), generated - consumed).quantize(Decimal('0.01'))

            EnergySavings.objects.update_or_create(
                date=day,
                defaults={
                    'total_consumed_kwh': consumed,
                    'total_generated_kwh': generated,
                    'average_price_kwh': price,
                    'total_savings_cop': total_savings,
                    'savings_percentage': savings_pct,
                    'self_consumption_percentage': self_consumption_pct,
                    'excess_energy_kwh': excess,
                },
            )
            created += 1
            day += timedelta(days=1)

        result = {
            'created': created,
            'already_existing': len(existing_dates),
            'skipped_no_chart_data': skipped_no_chart,
            'skipped_no_price': skipped_no_price,
            'range': {'start': start.isoformat(), 'end': yesterday.isoformat()},
        }
        logger.info("calculate_energy_savings completada: %s", result)
        return result

    except Exception as e:
        logger.error(
            "Error inesperado en la tarea calculate_energy_savings: %s", str(e),
            exc_info=True,
        )
        raise
