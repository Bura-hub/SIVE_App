from celery import shared_task
from datetime import datetime, timedelta, timezone
from django.db.models import Sum, Avg, F, FloatField, Max, Count, Min, Q, QuerySet, Value
from django.db.models.functions import Cast, TruncDay, Greatest
import logging
import calendar
from django.utils import timezone as django_timezone
import pytz
from collections import defaultdict
import statistics
import os
import tempfile
import csv

from scada_proxy.models import (
    Device, Institution, DeviceCategory, TaskProgress,
    MeterMeasurement, InverterMeasurement, WeatherStationMeasurement,
)
from .energy import consumption_energy_kwh, generation_energy_kwh, SAMPLE_INTERVAL_HOURS
from .models import (
    MonthlyConsumptionKPI,
    DailyChartData,
    InverterIndicators,
    InverterChartData,
    WeatherStationIndicators,
    WeatherStationChartData,
    GeneratedReport,
    HourlyMeterIndicators,
    HourlyInverterIndicators,
    HourlyWeatherIndicators,
)

from core.task_locks import single_instance

logger = logging.getLogger(__name__)

# Helpers puros extraídos a services/ (Ola 5); re-exportados para no romper los imports
# existentes (`from indicators.tasks import ...`).
from indicators.services.date_ranges import (  # noqa: E402,F401
    COLOMBIA_TZ,
    colombia_day_range,
    colombia_hour_range,
    get_colombia_date,
    get_colombia_now,
)
from indicators.services.device_calc import run_over_days, run_over_months  # noqa: E402
from indicators.services.meter_calc import METER_FIELDS, compute_meter_indicators  # noqa: E402
from indicators.services.inverter_calc import (  # noqa: E402
    INVERTER_FIELDS,
    PR_REASON_NO_PLANT,
    PR_REASON_NO_STATION,
    PR_REASON_STATION_NOT_APT,
    compute_inverter_hourly_chart,
    compute_inverter_indicators,
    compute_performance_ratio,
    pr_unavailable,
)
from indicators.institution_config import config_institucion, inversor_vigente  # noqa: E402
from indicators.services.rows import _row_get  # noqa: E402,F401

@shared_task(bind=True, retry_backoff=60, max_retries=3)
@single_instance('calculate-monthly-kpi', ttl=1200)
def calculate_monthly_consumption_kpi(self):
    """
    Calcula el consumo total, la generación total, la potencia instantánea promedio,
    la temperatura promedio diaria, la humedad relativa promedio, y la velocidad del viento promedio
    para el mes actual (hasta la fecha) y el mes anterior (hasta el mismo día).
    Guarda los resultados en MonthlyConsumptionKPI.
    """
    logger.info("=== INICIANDO TAREA: calculate_monthly_consumption_kpi ===")
    try:
        # Ventanas con el MISMO tiempo transcurrido (C11): el mes en curso va del día 1 a las 00:00 hasta ahora, y el
        # mes anterior del día 1 a las 00:00 hasta el mismo instante relativo (topado al fin de ese mes). Antes el mes
        # anterior llegaba hasta el mismo día COMPLETO, y la comparación salía sesgada a la baja sin cambio real.
        now = get_colombia_now()
        today = now.date()
        cur_a = COLOMBIA_TZ.localize(datetime.combine(today.replace(day=1), datetime.min.time()))
        cur_b = now
        last_day_previous_month = today.replace(day=1) - timedelta(days=1)
        prev_a = COLOMBIA_TZ.localize(datetime.combine(last_day_previous_month.replace(day=1), datetime.min.time()))
        prev_month_end = cur_a
        prev_b = min(prev_a + (cur_b - cur_a), prev_month_end)
        logger.info(f"Ventana mes actual: {cur_a} -> {cur_b}; mes anterior: {prev_a} -> {prev_b}")

        weather_stations = Device.objects.filter(category__name__iexact='weatherStation', is_active=True)

        # --- Demanda y generación de las plantas del proyecto (C10, decisión D2) ---
        # Como en la tesis y el mercado P2P: por institución, D del circuito del Medidor 1 (reconstruida en
        # medidores netos) y G de su inversor; ver indicators/services/institution_energy.py. Antes se sumaban
        # TODOS los medidores (M1–M5 de cada sede, circuitos parciales que se solapan) y todos los inversores.
        # Campos: total_consumption = demanda D de los circuitos medidos; total_gross_consumption = energía tomada
        # de la red (D − autoconsumo); total_generation = G; avg_instantaneous_power = potencia media de la flota
        # en el periodo (W), no la media por muestra de un inversor con las noches incluidas.
        from indicators.services.institution_energy import totales_plantas
        cur = totales_plantas(cur_a, cur_b)
        prev = totales_plantas(prev_a, prev_b)

        current_month_consumption_sum = cur['d_kwh']
        previous_month_consumption_sum = prev['d_kwh']
        current_month_gross_consumption_sum = cur['red_kwh']
        previous_month_gross_consumption_sum = prev['red_kwh']
        current_month_generation_sum = cur['g_kwh']
        previous_month_generation_sum = prev['g_kwh']
        avg_instantaneous_power_current = (cur['g_kwh'] * 1000.0 / cur['horas']) if cur['horas'] else 0.0
        avg_instantaneous_power_previous = (prev['g_kwh'] * 1000.0 / prev['horas']) if prev['horas'] else 0.0
        logger.info(f"Demanda M1 - actual: {cur['d_kwh']:.2f} kWh ({cur['horas_medidor']}/{cur['horas_medidor_posibles']} h válidas), anterior: {prev['d_kwh']:.2f} kWh")
        logger.info(f"Generación - actual: {cur['g_kwh']:.2f} kWh, anterior: {prev['g_kwh']:.2f} kWh")

        # --- Métricas meteorológicas (temperatura, humedad, viento, irradiancia) ---
        # Una sola query por ventana: Avg de SQL ignora NULL por métrica, así
        # que el resultado es idéntico a los antiguos filtros isnull separados.
        logger.info("Calculando promedios meteorológicos (estaciones)...")

        def _weather_window(a, b):
            # Filtros físicos como en weather_calc (antes: Avg crudo, con 1968 W/m² y 400 km/h de lecturas
            # erróneas). La irradiancia es la media DIURNA (06:00–17:59) de las estaciones aptas: la de Udenar está
            # descalibrada (C16).
            from django.db.models.functions import ExtractHour
            from indicators.institution_config import INSTITUCIONES
            no_aptas = [c['estacion'] for c in INSTITUCIONES.values() if not c.get('estacion_apta_pr', True)]
            base = WeatherStationMeasurement.objects.filter(device__in=weather_stations, date__gte=a, date__lt=b)
            agg = base.aggregate(
                temp=Avg('temperature', filter=Q(temperature__gte=-10, temperature__lte=45)),
                humidity=Avg('humidity', filter=Q(humidity__gte=0, humidity__lte=100)),
                wind=Avg('windSpeed', filter=Q(windSpeed__gte=0, windSpeed__lte=150)),
            )
            agg.update(base.exclude(device__scada_id__in=no_aptas)
                       .annotate(h=ExtractHour('date', tzinfo=COLOMBIA_TZ))
                       .filter(h__gte=6, h__lt=18, irradiance__gte=0, irradiance__lte=1400)
                       .aggregate(irradiance=Avg('irradiance')))
            return agg

        wx_current = _weather_window(cur_a, cur_b)
        wx_previous = _weather_window(prev_a, prev_b)

        avg_daily_temp_current = wx_current['temp'] or 0.0
        avg_daily_temp_previous = wx_previous['temp'] or 0.0
        logger.info(f"Temperatura promedio diaria - Mes actual: {avg_daily_temp_current:.2f} °C, Mes anterior: {avg_daily_temp_previous:.2f} °C")

        avg_relative_humidity_current = wx_current['humidity'] or 0.0
        avg_relative_humidity_previous = wx_previous['humidity'] or 0.0
        logger.info(f"Humedad relativa promedio - Mes actual: {avg_relative_humidity_current:.2f} %RH, Mes anterior: {avg_relative_humidity_previous:.2f} %RH")

        avg_wind_speed_current = wx_current['wind'] or 0.0
        avg_wind_speed_previous = wx_previous['wind'] or 0.0
        logger.info(f"Velocidad del viento promedio - Mes actual: {avg_wind_speed_current:.2f} km/h, Mes anterior: {avg_wind_speed_previous:.2f} km/h")

        avg_irradiance_current = wx_current['irradiance'] or 0.0
        avg_irradiance_previous = wx_previous['irradiance'] or 0.0
        logger.info(f"Irradiancia solar promedio - Mes actual: {avg_irradiance_current:.2f} W/m², Mes anterior: {avg_irradiance_previous:.2f} W/m²")

        # Guardar en la base de datos
        logger.info("Guardando KPIs mensuales en la base de datos...")
        MonthlyConsumptionKPI.objects.update_or_create(
            pk=1,
            defaults={
                'total_consumption_current_month': current_month_consumption_sum,
                'total_consumption_previous_month': previous_month_consumption_sum,
                'total_gross_consumption_current_month': current_month_gross_consumption_sum,
                'total_gross_consumption_previous_month': previous_month_gross_consumption_sum,
                'total_generation_current_month': current_month_generation_sum,
                'total_generation_previous_month': previous_month_generation_sum,
                'avg_instantaneous_power_current_month': avg_instantaneous_power_current,
                'avg_instantaneous_power_previous_month': avg_instantaneous_power_previous,
                'avg_daily_temp_current_month': avg_daily_temp_current,
                'avg_daily_temp_previous_month': avg_daily_temp_previous,
                'avg_relative_humidity_current_month': avg_relative_humidity_current,
                'avg_relative_humidity_previous_month': avg_relative_humidity_previous,
                'avg_wind_speed_current_month': avg_wind_speed_current,
                'avg_wind_speed_previous_month': avg_wind_speed_previous,
                'avg_irradiance_current_month': avg_irradiance_current,
                'avg_irradiance_previous_month': avg_irradiance_previous,
            }
        )

        logger.info("=== TAREA COMPLETADA: calculate_monthly_consumption_kpi ===")
        logger.info("Todos los KPIs mensuales han sido calculados y actualizados exitosamente.")
        return "All Monthly KPIs calculated and updated successfully."

    except Exception as e:
        logger.error(f"=== ERROR EN TAREA: calculate_monthly_consumption_kpi ===")
        logger.error(f"Error calculando KPIs mensuales: {e}", exc_info=True)
        raise

@shared_task(bind=True, retry_backoff=30, max_retries=3)
@single_instance('calculate-daily-chart', ttl=1200)
def calculate_and_save_daily_data(self, start_date_str: str = None, end_date_str: str = None):
    """
    Calcula el consumo, la generación, el balance de energía y la temperatura promedio diaria 
    para un rango de fechas.
    """
    logger.info("=== INICIANDO TAREA: calculate_and_save_daily_data ===")
    try:
        # Si no se proporcionan fechas, calcular para el día anterior en Colombia
        if not start_date_str or not end_date_str:
            yesterday = get_colombia_date() - timedelta(days=1)
            start_date_str = yesterday.isoformat()
            end_date_str = yesterday.isoformat()
            logger.info(f"No se proporcionaron fechas, calculando para el día anterior en Colombia: {yesterday}")

        # 1. Convertir strings a objetos datetime conscientes de la zona horaria de Colombia
        # localize (no replace(tzinfo=...)): con pytz, replace deja el desfase LMT de −4:56.
        start_date = COLOMBIA_TZ.localize(datetime.fromisoformat(start_date_str[:10]))
        end_date = COLOMBIA_TZ.localize(datetime.fromisoformat(end_date_str[:10]))

        logger.info(f"Rango de fechas a procesar en Colombia: {start_date.date()} -> {end_date.date()}")
        
        # 2. Obtener los dispositivos eléctricos, inversores y estaciones meteorológicas
        electric_meters: QuerySet[Device] = Device.objects.filter(category__name__iexact='electricMeter', is_active=True)
        inverters: QuerySet[Device] = Device.objects.filter(category__name__iexact='inverter', is_active=True)
        weather_stations: QuerySet[Device] = Device.objects.filter(category__name__iexact='weatherStation', is_active=True)
        
        logger.info(f"Dispositivos encontrados para cálculo diario:")
        logger.info(f"  - Medidores eléctricos: {electric_meters.count()} dispositivos")
        logger.info(f"  - Inversores: {inverters.count()} dispositivos")
        logger.info(f"  - Estaciones meteorológicas: {weather_stations.count()} dispositivos")
        
        if not electric_meters.exists() and not inverters.exists() and not weather_stations.exists():
            logger.warning("No se encontraron dispositivos activos para procesar.")
            return

        electric_meter_ids = electric_meters.values_list('id', flat=True)
        inverter_ids = inverters.values_list('id', flat=True)
        weather_station_ids = weather_stations.values_list('id', flat=True)

        # 3. Iterar día por día en el rango especificado
        current_date = start_date
        total_days_processed = 0
        total_records_created = 0
        total_records_updated = 0
        
        logger.info(f"Iniciando procesamiento de {((end_date - start_date).days + 1)} días...")
        
        # v2: 3 queries agrupadas por día de Bogotá sobre TODO el rango (antes:
        # 4 queries por CADA día). TruncDay(tzinfo=COLOMBIA_TZ) reproduce el
        # corte del antiguo `date__date=<día>` con TIME_ZONE=America/Bogota.
        range_a, range_b = colombia_day_range(start_date.date(), end_date.date())
        day_trunc = TruncDay('date', tzinfo=COLOMBIA_TZ)

        # Demanda y generación por día de las plantas del proyecto (C10, decisión D2), como el KPI mensual: D del
        # circuito del Medidor 1 de cada institución (reconstruida en medidores netos), G de su inversor y la energía
        # tomada de la red (D − autoconsumo). Antes se sumaban todos los medidores y todos los inversores.
        from indicators.services.institution_energy import energia_horaria
        from indicators.institution_config import INSTITUCIONES
        planta_by_day = defaultdict(lambda: {'d': 0.0, 'red': 0.0, 'g': 0.0})
        for scada_id in INSTITUCIONES:
            for h in energia_horaria(scada_id, start_date.date(), end_date.date()):
                acc = planta_by_day[h['hora'].date()]
                acc['g'] += h['g_kwh']
                if h['d_kwh'] is not None:
                    acc['d'] += h['d_kwh']
                    acc['red'] += h['d_kwh'] - h['autoconsumo_kwh']
        # Clima con los filtros físicos del KPI mensual; irradiancia media diurna (06–18 h) de estaciones aptas.
        from django.db.models.functions import ExtractHour
        no_aptas = [c['estacion'] for c in INSTITUCIONES.values() if not c.get('estacion_apta_pr', True)]
        w_base = WeatherStationMeasurement.objects.filter(
            device__in=weather_station_ids, date__gte=range_a, date__lt=range_b).annotate(d=day_trunc)
        weather_by_day = {
            r['d'].date(): r for r in w_base.values('d').annotate(
                temp=Avg('temperature', filter=Q(temperature__gte=-10, temperature__lte=45)),
                wind=Avg('windSpeed', filter=Q(windSpeed__gte=0, windSpeed__lte=150)),
            )
        }
        for r in (w_base.exclude(device__scada_id__in=no_aptas)
                  .annotate(h=ExtractHour('date', tzinfo=COLOMBIA_TZ))
                  .filter(h__gte=6, h__lt=18, irradiance__gte=0, irradiance__lte=1400)
                  .values('d').annotate(irr=Avg('irradiance'))):
            weather_by_day.setdefault(r['d'].date(), {})['irr'] = r['irr']

        while current_date <= end_date:
            single_date = current_date.date()
            logger.info(f"Procesando fecha en Colombia: {single_date}")

            p_day = planta_by_day.get(single_date, {'d': 0.0, 'red': 0.0, 'g': 0.0})
            w_day = weather_by_day.get(single_date, {})

            daily_temp_avg = w_day.get('temp') or 0.0
            avg_wind_speed = w_day.get('wind') or 0.0
            avg_irradiance = w_day.get('irr') or 0.0

            daily_consumption_kwh = p_day['d']          # demanda de los circuitos medidos (M1), kWh
            daily_gross_consumption_kwh = p_day['red']  # tomada de la red, kWh
            daily_generation_kwh = p_day['g']           # generación de las plantas, kWh

            # Calcular balance energético (ambos en kWh)
            daily_balance_sum = daily_generation_kwh - daily_consumption_kwh

            daily_data_obj, created = DailyChartData.objects.update_or_create(
                date=single_date,
                defaults={
                    'daily_consumption': daily_consumption_kwh,
                    'daily_gross_consumption': daily_gross_consumption_kwh,
                    'daily_generation': daily_generation_kwh,
                    'daily_balance': daily_balance_sum,
                    'avg_daily_temp': daily_temp_avg,
                    'avg_wind_speed': avg_wind_speed,
                    'avg_irradiance': avg_irradiance
                }
            )
            
            if created:
                total_records_created += 1
                action = "creado"
            else:
                total_records_updated += 1
                action = "actualizado"
                
            logger.info(f"  Dato diario {action} para {single_date}:")
            logger.info(f"    - Consumo: {daily_consumption_kwh:.2f} kWh")
            logger.info(f"    - Generación: {daily_generation_kwh:.2f} kWh")
            logger.info(f"    - Balance: {daily_balance_sum:.2f} kWh")
            logger.info(f"    - Temperatura promedio: {daily_temp_avg:.2f} °C")
            logger.info(f"    - Velocidad del viento promedio: {avg_wind_speed:.2f} km/h")
            logger.info(f"    - Irradiancia promedio: {avg_irradiance:.2f} W/m²")

            current_date += timedelta(days=1)
            total_days_processed += 1

        logger.info("=== RESUMEN DE PROCESAMIENTO ===")
        logger.info(f"Días procesados: {total_days_processed}")
        logger.info(f"Registros creados: {total_records_created}")
        logger.info(f"Registros actualizados: {total_records_updated}")
        logger.info("=== TAREA COMPLETADA: calculate_and_save_daily_data ===")

    except Exception as e:
        logger.error(f"=== ERROR EN TAREA: calculate_and_save_daily_data ===")
        logger.error(f"Error en el cálculo de datos diarios: {e}", exc_info=True)
        raise

def _calculate_hourly_consumption(measurements):
    """
    Calcula el consumo por hora del día basado en las mediciones.

    Recibe filas dict (v2: `.values('date', 'totalActivePower')`).
    """
    hourly_data = defaultdict(list)

    for row in measurements:
        hour = row['date'].hour
        power_value = _row_get(row, 'totalActivePower')
        if power_value is None:
            continue  # NULL = no medido (C9): no entra al promedio
        hourly_data[hour].append(power_value)
    
    # Calcular promedio por hora
    hourly_consumption = [0.0] * 24
    for hour in range(24):
        if hour in hourly_data:
            hourly_consumption[hour] = sum(hourly_data[hour]) / len(hourly_data[hour])
    
    return hourly_consumption

# indicators/tasks.py
@shared_task
def calculate_electric_meter_indicators(device_id, date_str, time_range='daily'):
    """
    Calcula todos los indicadores eléctricos para un medidor específico en una fecha dada.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Max, Min, Avg
        from scada_proxy.models import Device, Institution
        from .models import ElectricMeterIndicators
        
        # Parsear la fecha
        if isinstance(date_str, str):
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = date_str
        
        # Obtener el dispositivo y la institución
        device = Device.objects.get(id=device_id)
        institution = device.institution
        
        # Determinar el rango de fechas
        if time_range == 'daily':
            start_date = date
            end_date = date + timedelta(days=1)
        else:  # monthly
            start_date = date.replace(day=1)
            if date.month == 12:
                end_date = date.replace(year=date.year + 1, month=1, day=1)
            else:
                end_date = date.replace(month=date.month + 1, day=1)
        
        # Obtener todas las mediciones del período (v2: rango aware Bogotá,
        # equivalente al antiguo date__gte/lt con objetos date interpretados
        # a medianoche en TIME_ZONE=America/Bogota)
        start_dt, end_dt = colombia_day_range(start_date, end_date - timedelta(days=1))
        measurements = MeterMeasurement.objects.filter(
            device=device,
            date__gte=start_dt,
            date__lt=end_dt
        ).order_by('date')

        if not measurements.exists():
            return f"No hay mediciones para {device.name} en {date}"

        # Cálculo puro extraído a services/meter_calc.py (Ola 5).
        computed = compute_meter_indicators(
            measurements.values(*METER_FIELDS).iterator(chunk_size=2000)
        )

        # Guardar o actualizar los indicadores
        indicators, created = ElectricMeterIndicators.objects.update_or_create(
            device=device,
            institution=institution,
            date=date,
            time_range=time_range,
            defaults={
                **computed,
                'measurement_count': measurements.count(),
                'last_measurement_date': measurements.last().date if measurements.exists() else None,
            }
        )

        action = "creado" if created else "actualizado"
        return f"Indicadores eléctricos {action} para {device.name} en {date} ({time_range})"
        
    except Exception as e:
        return f"Error calculando indicadores eléctricos: {str(e)}"


@shared_task
def calculate_inverter_indicators(device_id, date_str, time_range='daily'):
    """
    Calcula todos los indicadores de inversores para un dispositivo específico en una fecha dada.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Max, Min, Avg, StdDev
        from scada_proxy.models import Device, Institution
        from .models import InverterIndicators, InverterChartData
        
        # Parsear la fecha
        if isinstance(date_str, str):
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = date_str
        
        # Obtener el dispositivo y la institución
        device = Device.objects.get(id=device_id)
        institution = device.institution
        
        # Determinar el rango de fechas
        if time_range == 'daily':
            start_date = date
            end_date = date + timedelta(days=1)
        else:  # monthly
            start_date = date.replace(day=1)
            if date.month == 12:
                end_date = date.replace(year=date.year + 1, month=1, day=1)
            else:
                end_date = date.replace(month=date.month + 1, day=1)
        
        # Obtener todas las mediciones del período (v2: rango aware Bogotá,
        # equivalente al antiguo date__gte/lt con objetos date interpretados
        # a medianoche en TIME_ZONE=America/Bogota)
        start_dt, end_dt = colombia_day_range(start_date, end_date - timedelta(days=1))
        measurements = InverterMeasurement.objects.filter(
            device=device,
            date__gte=start_dt,
            date__lt=end_dt
        ).order_by('date')

        if not measurements.exists():
            return f"No hay mediciones para {device.name} en {date}"
        
        # Cálculo puro extraído a services/inverter_calc.py (Ola 5).
        computed = compute_inverter_indicators(
            measurements.values(*INVERTER_FIELDS).iterator(chunk_size=2000)
        )
        # Performance Ratio con la estación de la institución (C4/D5).
        computed.update(_inverter_performance_ratio(
            device, start_date, end_date - timedelta(days=1), measurements))

        # Guardar o actualizar los indicadores
        indicators, created = InverterIndicators.objects.update_or_create(
            device=device,
            institution=institution,
            date=date,
            time_range=time_range,
            defaults={
                **computed,
                'measurement_count': measurements.count(),
                'last_measurement_date': measurements.last().date if measurements.exists() else None,
            }
        )

        # Gráfica horaria: solo para el diario. InverterChartData es única por (device, date) sin
        # time_range, así que la corrida mensual (date = día 1) pisaba la gráfica del día 1 con
        # medias horarias de todo el mes.
        if time_range == 'daily':
            hourly_data = _calculate_hourly_inverter_data(
                measurements.values('date', 'acPower', 'dcPower').iterator(chunk_size=2000)
            )
            InverterChartData.objects.update_or_create(
                device=device,
                institution=institution,
                date=date,
                defaults=hourly_data
            )

        action = "creado" if created else "actualizado"
        return f"Indicadores de inversor {action} para {device.name} en {date} ({time_range})"

    except Exception as e:
        # Fallar en voz alta: se registra con traza (antes solo se devolvía el texto del error).
        logger.error(f"Error calculando indicadores de inversor {device_id} {date_str} ({time_range}): {e}",
                     exc_info=True)
        return f"Error calculando indicadores de inversor: {str(e)}"


def _inverter_performance_ratio(device, first_day, last_day, measurements):
    """PR del inversor entre `first_day` y `last_day` (inclusive, días de Bogotá), con la estación
    de su institución según `institution_config` (D5). Devuelve los campos performance_ratio_* y
    reference_energy_kwh, con el motivo cuando el PR no se puede calcular."""
    config = config_institucion(device.institution.scada_id) if device.institution else None
    if not config or str(device.scada_id) not in config['inversores_generacion']:
        return pr_unavailable(PR_REASON_NO_PLANT)
    if not config['estacion_apta_pr']:
        return pr_unavailable(PR_REASON_STATION_NOT_APT.format(institucion=config['nombre']))
    station = Device.objects.filter(scada_id=config['estacion']).first()
    if station is None:
        return pr_unavailable(PR_REASON_NO_STATION.format(institucion=config['nombre']))

    # Mismas reglas y mismas funciones que «Indicadores Solares» (solar_kpis.calcular): irradiación diaria con
    # cobertura, tope físico y contraste con la estación de referencia (C22); energía horaria con reposición de
    # lecturas sueltas (C21), y un día solo cuenta si el inversor tiene lectura en ≥ 80 % de las horas de sol.
    # Cada planta tiene un único inversor de generación, así que para el mismo rango las dos pantallas dan el mismo
    # PR. La excepción sería un día con `respaldo_generacion` (Udenar antes del 2025-09-03), donde la planta usa
    # otro inversor; hoy no aplica porque la estación de Udenar no es apta para el PR.
    from indicators.services.institution_energy import energia_diaria_para_pr, horas_inversor, irradiacion_diaria
    irradiation = irradiacion_diaria(device.institution.scada_id, first_day, last_day)
    horas = [
        h for h in horas_inversor(measurements.values('date', 'acPower').iterator(chunk_size=2000))
        if inversor_vigente(config, device.scada_id, h['hora'].date())
    ]
    energy = energia_diaria_para_pr(horas)
    return compute_performance_ratio(energy, irradiation, config['kwp'])


def _calculate_hourly_inverter_data(measurements):
    """Datos por hora (Bogotá) para la gráfica del inversor. Ver
    `services.inverter_calc.compute_inverter_hourly_chart` (C5 y C7)."""
    return compute_inverter_hourly_chart(measurements)


@shared_task
def calculate_inverter_data(time_range='daily', start_date_str=None, end_date_str=None, institution_id=None, device_id=None):
    """
    Calcula datos de inversores para un rango de fechas y filtros específicos.
    
    Parámetros:
        time_range: 'daily' o 'monthly'
        start_date_str: fecha de inicio en formato ISO
        end_date_str: fecha de fin en formato ISO
        institution_id: ID de la institución (opcional)
        device_id: ID del dispositivo específico (opcional)
    """
    logger.info("=== INICIANDO TAREA: calculate_inverter_data ===")
    try:
        # Procesar fechas
        if not start_date_str or not end_date_str:
            # Por defecto, último mes
            end_date = get_colombia_date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()

        logger.info(f"Calculando datos para rango: {time_range}, desde {start_date} hasta {end_date}")

        # Obtener inversores filtrados
        inverters = Device.objects.filter(category__name__iexact='inverter', is_active=True)
        
        if institution_id:
            inverters = inverters.filter(institution_id=institution_id)
            logger.info(f"Filtrado por institución ID: {institution_id}")
        
        if device_id:
            inverters = inverters.filter(scada_id=device_id)
            logger.info(f"Filtrado por dispositivo ID: {device_id}")

        logger.info(f"Procesando {inverters.count()} inversores")

        total_records_created = 0
        total_records_updated = 0

        for inverter in inverters:
            logger.info(f"Procesando inversor: {inverter.name} (ID: {inverter.id}, SCADA ID: {inverter.scada_id})")
            
            if time_range == 'daily':
                records_created, records_updated = _calculate_daily_inverter_data(inverter, start_date, end_date)
            else:  # monthly
                records_created, records_updated = _calculate_monthly_inverter_data(inverter, start_date, end_date)
            
            total_records_created += records_created
            total_records_updated += records_updated

        logger.info(f"=== RESUMEN DE PROCESAMIENTO ===")
        logger.info(f"Registros creados: {total_records_created}")
        logger.info(f"Registros actualizados: {total_records_updated}")
        logger.info("=== TAREA COMPLETADA: calculate_inverter_data ===")

        return f"Procesados {inverters.count()} inversores. Creados: {total_records_created}, Actualizados: {total_records_updated}"

    except Exception as e:
        logger.error(f"=== ERROR EN TAREA: calculate_inverter_data ===")
        logger.error(f"Error calculando datos de inversores: {e}", exc_info=True)
        raise


def _calculate_daily_inverter_data(inverter, start_date, end_date):
    """Datos diarios de un inversor (itera días delegando en el cálculo por día)."""
    return run_over_days(inverter, start_date, end_date, calculate_inverter_indicators)


def _calculate_monthly_inverter_data(inverter, start_date, end_date):
    """Datos mensuales de un inversor (itera meses delegando en el cálculo mensual)."""
    return run_over_months(inverter, start_date, end_date, calculate_inverter_indicators)


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def calculate_electrical_data(self, time_range='daily', start_date_str=None, end_date_str=None, institution_id=None, device_id=None):
    """
    Calcula y actualiza indicadores eléctricos para un rango de fechas específico.
    Similar a calculate_inverter_data pero para medidores eléctricos.
    
    Args:
        time_range (str): 'daily' o 'monthly'
        start_date_str (str): Fecha de inicio en formato 'YYYY-MM-DD'
        end_date_str (str): Fecha de fin en formato 'YYYY-MM-DD'
        institution_id (int): ID de la institución (opcional)
        device_id (str): SCADA ID del dispositivo (opcional)
    """
    logger.info("=== INICIANDO TAREA: calculate_electrical_data ===")
    try:
        # Configurar fechas por defecto si no se especifican
        if not start_date_str or not end_date_str:
            # Por defecto, último mes
            end_date = get_colombia_date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()

        logger.info(f"Calculando datos eléctricos para rango: {time_range}, desde {start_date} hasta {end_date}")

        # Obtener medidores eléctricos filtrados
        electric_meters = Device.objects.filter(category__name__iexact='electricMeter', is_active=True)
        
        if institution_id:
            electric_meters = electric_meters.filter(institution_id=institution_id)
            logger.info(f"Filtrado por institución ID: {institution_id}")
        
        if device_id:
            electric_meters = electric_meters.filter(scada_id=device_id)
            logger.info(f"Filtrado por dispositivo ID: {device_id}")

        logger.info(f"Procesando {electric_meters.count()} medidores eléctricos")

        total_records_created = 0
        total_records_updated = 0

        for meter in electric_meters:
            logger.info(f"Procesando medidor: {meter.name} (ID: {meter.id}, SCADA ID: {meter.scada_id})")
            
            if time_range == 'daily':
                records_created, records_updated = _calculate_daily_electrical_data(meter, start_date, end_date)
            else:  # monthly
                records_created, records_updated = _calculate_monthly_electrical_data(meter, start_date, end_date)
            
            total_records_created += records_created
            total_records_updated += records_updated

        logger.info(f"=== RESUMEN DE PROCESAMIENTO ELÉCTRICO ===")
        logger.info(f"Registros creados: {total_records_created}")
        logger.info(f"Registros actualizados: {total_records_updated}")
        logger.info("=== TAREA COMPLETADA: calculate_electrical_data ===")

        return f"Procesados {electric_meters.count()} medidores eléctricos. Creados: {total_records_created}, Actualizados: {total_records_updated}"

    except Exception as e:
        logger.error(f"=== ERROR EN TAREA: calculate_electrical_data ===")
        logger.error(f"Error calculando datos eléctricos: {e}", exc_info=True)
        raise


def _calculate_daily_electrical_data(meter, start_date, end_date):
    """Datos diarios de un medidor eléctrico (itera días delegando en el cálculo por día)."""
    return run_over_days(meter, start_date, end_date, calculate_electric_meter_indicators)


def _calculate_monthly_electrical_data(meter, start_date, end_date):
    """Datos mensuales de un medidor eléctrico (itera meses delegando en el cálculo mensual)."""
    return run_over_months(meter, start_date, end_date, calculate_electric_meter_indicators)

@shared_task
def calculate_weather_station_indicators(time_range='daily', start_date_str=None, end_date_str=None, institution_id=None, device_id=None):
    """
    Calcula los indicadores meteorológicos para estaciones meteorológicas
    en diferentes rangos de tiempo (diario/mensual).
    
    Parámetros:
        time_range: 'daily' o 'monthly'
        start_date_str: fecha de inicio en formato ISO
        end_date_str: fecha de fin en formato ISO
        institution_id: ID de la institución (opcional)
        device_id: ID del dispositivo específico (opcional)
    """
    logger.info("=== INICIANDO TAREA: calculate_weather_station_indicators ===")
    logger.info(f"Parámetros: time_range={time_range}, start_date_str={start_date_str}, end_date_str={end_date_str}, institution_id={institution_id}, device_id={device_id}")
    
    try:
        # Paso 1: Validar y preparar fechas
        if not start_date_str or not end_date_str:
            # Por defecto, último mes
            end_date = get_colombia_date()
            if time_range == 'daily':
                start_date = end_date
            else:  # monthly
                start_date = end_date.replace(day=1)
        else:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
        
        logger.info(f"Calculando datos para rango: {time_range}, desde {start_date} hasta {end_date}")
        
        # Paso 2: Obtener dispositivos
        # Filtrar por categoría de estación meteorológica (category_id=3 según variables.json)
        weather_stations = Device.objects.filter(category__name__iexact='weatherStation', is_active=True)
        
        if institution_id:
            weather_stations = weather_stations.filter(institution_id=institution_id)
            logger.info(f"Filtrado por institución ID: {institution_id}")
        
        if device_id:
            weather_stations = weather_stations.filter(scada_id=device_id)
            logger.info(f"Filtrado por dispositivo ID: {device_id}")
        
        logger.info(f"Procesando {weather_stations.count()} estaciones meteorológicas")
        
        total_records_created = 0
        total_records_updated = 0
        
        for station in weather_stations:
            logger.info(f"Procesando estación: {station.name} (ID: {station.id}, SCADA ID: {station.scada_id})")
            
            if time_range == 'daily':
                records_created, records_updated = _calculate_daily_weather_station_data(station, start_date, end_date)
            else:  # monthly
                records_created, records_updated = _calculate_monthly_weather_station_data(station, start_date, end_date)
            
            total_records_created += records_created
            total_records_updated += records_updated
        
        logger.info(f"=== RESUMEN DE PROCESAMIENTO ===")
        logger.info(f"Registros creados: {total_records_created}")
        logger.info(f"Registros actualizados: {total_records_updated}")
        logger.info("=== TAREA COMPLETADA: calculate_weather_station_indicators ===")
        
        return f"Procesadas {weather_stations.count()} estaciones meteorológicas. Creados: {total_records_created}, Actualizados: {total_records_updated}"
        
    except Exception as e:
        logger.error(f"=== ERROR EN TAREA: calculate_weather_station_indicators ===")
        logger.error(f"Error calculando datos de estaciones meteorológicas: {e}", exc_info=True)
        raise
        



def calculate_daily_weather_indicators(station, measurements, start_date, end_date):
    """
    Calcula indicadores meteorológicos diarios para una estación específica.
    """
    total_processed = 0
    
    # Agrupar mediciones por día (filas dict v2: measurement['date'])
    daily_measurements = {}
    for measurement in measurements:
        day = measurement['date'].astimezone(COLOMBIA_TZ).date()  # día de Bogotá (C7)
        if day not in daily_measurements:
            daily_measurements[day] = []
        daily_measurements[day].append(measurement)
    
    for day, day_measurements in daily_measurements.items():
        try:
            # Calcular indicadores para el día
            indicators = calculate_single_day_weather_indicators(day_measurements)
            
            # Guardar o actualizar indicadores
            weather_indicator, created = WeatherStationIndicators.objects.update_or_create(
                device=station,
                institution=station.institution,
                date=day,
                time_range='daily',
                defaults=indicators
            )
            
            # Calcular y guardar datos de gráficos
            chart_data = calculate_single_day_weather_chart_data(day_measurements)
            weather_chart, chart_created = WeatherStationChartData.objects.update_or_create(
                device=station,
                institution=station.institution,
                date=day,
                defaults=chart_data
            )
            
            total_processed += 1
            logger.info(f"Indicadores diarios calculados para {station.name} - {day}")
            
        except Exception as e:
            logger.error(f"Error calculando indicadores diarios para {station.name} - {day}: {str(e)}")
            continue
    
    return total_processed


def calculate_monthly_weather_indicators(station, measurements, start_date, end_date):
    """
    Calcula indicadores meteorológicos mensuales para una estación específica.
    """
    total_processed = 0
    
    # Agrupar mediciones por mes (filas dict v2: measurement['date'])
    monthly_measurements = {}
    for measurement in measurements:
        month_start = measurement['date'].astimezone(COLOMBIA_TZ).date().replace(day=1)  # C7
        if month_start not in monthly_measurements:
            monthly_measurements[month_start] = []
        monthly_measurements[month_start].append(measurement)
    
    for month_start, month_measurements in monthly_measurements.items():
        try:
            # Calcular indicadores para el mes
            indicators = calculate_single_month_weather_indicators(month_measurements)
            
            # Guardar o actualizar indicadores
            weather_indicator, created = WeatherStationIndicators.objects.update_or_create(
                device=station,
                institution=station.institution,
                date=month_start,
                time_range='monthly',
                defaults=indicators
            )
            
            total_processed += 1
            logger.info(f"Indicadores mensuales calculados para {station.name} - {month_start}")
            
        except Exception as e:
            logger.error(f"Error calculando indicadores mensuales para {station.name} - {month_start}: {str(e)}")
            continue
    
    return total_processed


# Cálculo meteorológico por día/mes/hora: extraído a services/weather_calc.py (Ola 5).
# BUG corregido (vista horaria, Etapa 2): `calculate_single_day_weather_chart_data` se
# invocaba más abajo (calculate_daily_weather_indicators / _calculate_daily_weather_station_data)
# pero NUNCA estuvo importada; el NameError quedaba enmascarado por el `except Exception`
# amplio de esas funciones, así que los datos de gráfica diaria de weather (arreglos
# `hourly_*` de WeatherStationChartData) fallaban en silencio. Se añade aquí junto con
# `calculate_single_hour_weather_indicators`, que usa el rollup horario nuevo.
from indicators.services.weather_calc import (  # noqa: E402,F401
    daily_irradiation_for_pr,
    calculate_single_day_weather_indicators,
    calculate_single_month_weather_indicators,
    calculate_single_day_weather_chart_data,
    calculate_single_hour_weather_indicators,
)


def _calculate_daily_weather_station_data(station, start_date, end_date):
    """
    Calcula datos diarios para una estación meteorológica específica
    """
    records_created = 0
    records_updated = 0
    
    current_date = start_date
    while current_date <= end_date:
        logger.info(f"  Procesando fecha: {current_date}")
        
        try:
            # Obtener mediciones para el día específico (v2: columnas tipadas,
            # rango aware Bogotá equivalente al antiguo date__date)
            day_a, day_b = colombia_day_range(current_date, current_date)
            measurements = WeatherStationMeasurement.objects.filter(
                device=station,
                date__gte=day_a, date__lt=day_b
            ).order_by('date')

            if measurements.exists():
                # Filas dict con las columnas usadas por los cálculos
                measurements_list = list(measurements.values(
                    'date', 'irradiance', 'temperature', 'humidity',
                    'windSpeed', 'windDirection', 'precipitation',
                ))
                
                # Calcular indicadores para el día
                indicators = calculate_single_day_weather_indicators(measurements_list)
                
                # Guardar o actualizar indicadores
                weather_indicator, created = WeatherStationIndicators.objects.update_or_create(
                    device=station,
                    institution=station.institution,
                    date=current_date,
                    time_range='daily',
                    defaults=indicators
                )
                
                if created:
                    records_created += 1
                else:
                    records_updated += 1
                
                # Calcular y guardar datos de gráficos
                chart_data = calculate_single_day_weather_chart_data(measurements_list)
                weather_chart, chart_created = WeatherStationChartData.objects.update_or_create(
                    device=station,
                    institution=station.institution,
                    date=current_date,
                    defaults=chart_data
                )
                
                logger.info(f"  Indicadores diarios calculados para {station.name} - {current_date}")
            else:
                logger.warning(f"  No hay mediciones para {station.name} en {current_date}")
                
        except Exception as e:
            logger.error(f"  Error calculando indicadores diarios para {station.name} - {current_date}: {str(e)}")
        
        current_date += timedelta(days=1)

    return records_created, records_updated


def _calculate_monthly_weather_station_data(station, start_date, end_date):
    """
    Calcula datos mensuales para una estación meteorológica específica
    """
    records_created = 0
    records_updated = 0
    
    # Agrupar por mes
    current_date = start_date.replace(day=1)  # Primer día del mes
    while current_date <= end_date:
        month_end = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month_end = min(month_end, end_date)
        
        logger.info(f"  Procesando mes: {current_date.strftime('%Y-%m')}")
        
        try:
            # Obtener mediciones para el mes (v2: columnas tipadas, rango aware
            # Bogotá equivalente al antiguo date__date__range)
            month_a, month_b = colombia_day_range(current_date, month_end)
            measurements = WeatherStationMeasurement.objects.filter(
                device=station,
                date__gte=month_a, date__lt=month_b
            ).order_by('date')

            if measurements.exists():
                # Filas dict con las columnas usadas por los cálculos
                measurements_list = list(measurements.values(
                    'date', 'irradiance', 'temperature', 'humidity',
                    'windSpeed', 'windDirection', 'precipitation',
                ))
                
                # Calcular indicadores para el mes
                indicators = calculate_single_month_weather_indicators(measurements_list)
                
                # Guardar o actualizar indicadores
                weather_indicator, created = WeatherStationIndicators.objects.update_or_create(
                    device=station,
                    institution=station.institution,
                    date=current_date,
                    time_range='monthly',
                    defaults=indicators
                )
                
                if created:
                    records_created += 1
                else:
                    records_updated += 1
                
                logger.info(f"  Indicadores mensuales calculados para {station.name} - {current_date.strftime('%Y-%m')}")
            else:
                logger.warning(f"  No hay mediciones para {station.name} en {current_date.strftime('%Y-%m')}")
                
        except Exception as e:
            logger.error(f"  Error calculando indicadores mensuales para {station.name} - {current_date.strftime('%Y-%m')}: {str(e)}")
        
        # Avanzar al siguiente mes
        current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)

    return records_created, records_updated

# =========================
# ROLLUP HORARIO (vista horaria, Opción B)
# =========================
# Tablas dedicadas de grano horario (HourlyMeterIndicators/HourlyInverterIndicators/
# HourlyWeatherIndicators, ver indicators/models.py). NO tocan `time_range` de las
# tablas diarias/mensuales existentes; el KPI oficial diario sigue siendo
# ElectricMeterIndicators/InverterIndicators/WeatherStationIndicators sin cambios.
# Este rollup es solo para graficar el detalle horario (endpoints time_range=hourly).


def _calculate_hourly_meter_row(meter, hour_start):
    """Calcula y guarda `HourlyMeterIndicators` de `meter` para la hora `hour_start`
    (datetime aware Bogotá, inicio de hora exacto). Idempotente: `update_or_create`
    por (device, hour) — correr dos veces sobre la misma hora no duplica filas, solo
    actualiza `calculated_at`. Devuelve 'created'/'updated'/None (sin mediciones)."""
    start_dt, end_dt = colombia_hour_range(hour_start)
    measurements = MeterMeasurement.objects.filter(
        device=meter, date__gte=start_dt, date__lt=end_dt
    ).order_by('date')
    count = measurements.count()
    if count == 0:
        return None

    # Mismo cálculo puro que el diario (compute_meter_indicators), aplicado a la
    # ventana de 1 hora: sus claves de salida coinciden 1:1 con los campos de
    # HourlyMeterIndicators, sin necesidad de renombrar nada.
    computed = compute_meter_indicators(
        measurements.values(*METER_FIELDS).iterator(chunk_size=2000)
    )

    _, created = HourlyMeterIndicators.objects.update_or_create(
        device=meter,
        hour=start_dt,
        defaults={
            **computed,
            'institution': meter.institution,
            'measurement_count': count,
        }
    )
    return 'created' if created else 'updated'


def _calculate_hourly_inverter_row(inverter, hour_start):
    """Calcula y guarda `HourlyInverterIndicators` de `inverter` para la hora
    `hour_start`. Idempotente (ver `_calculate_hourly_meter_row`). Renombra las
    claves *_daily_* de `compute_inverter_indicators` a los nombres horarios
    (energy_ac_kwh/energy_dc_kwh) y EXCLUYE avg_irradiance_wm2/avg_temperature_c
    (siempre 0 en inversor, ver diseño). `avg_power_w` no lo calcula la función pura
    (solo max/min), así que se agrega aquí con un Avg directo sobre la ventana."""
    start_dt, end_dt = colombia_hour_range(hour_start)
    measurements = InverterMeasurement.objects.filter(
        device=inverter, date__gte=start_dt, date__lt=end_dt
    ).order_by('date')
    count = measurements.count()
    if count == 0:
        return None

    computed = compute_inverter_indicators(
        measurements.values(*INVERTER_FIELDS).iterator(chunk_size=2000)
    )
    avg_power_w = measurements.aggregate(v=Avg('acPower'))['v'] or 0.0

    _, created = HourlyInverterIndicators.objects.update_or_create(
        device=inverter,
        hour=start_dt,
        defaults={
            'energy_ac_kwh': computed['energy_ac_daily_kwh'],
            'energy_dc_kwh': computed['energy_dc_daily_kwh'],
            'dc_ac_efficiency_pct': computed['dc_ac_efficiency_pct'],
            'performance_ratio_pct': computed['performance_ratio_pct'],
            'reference_energy_kwh': computed['reference_energy_kwh'],
            'avg_power_w': avg_power_w,
            'max_power_w': computed['max_power_w'],
            'min_power_w': computed['min_power_w'],
            'avg_power_factor': computed['avg_power_factor'],
            'avg_reactive_power_var': computed['avg_reactive_power_var'],
            'avg_apparent_power_va': computed['avg_apparent_power_va'],
            'avg_frequency_hz': computed['avg_frequency_hz'],
            'frequency_stability_pct': computed['frequency_stability_pct'],
            'max_voltage_unbalance_pct': computed['max_voltage_unbalance_pct'],
            'max_current_unbalance_pct': computed['max_current_unbalance_pct'],
            'anomaly_score': computed['anomaly_score'],
            'anomaly_details': computed['anomaly_details'],
            'institution': inverter.institution,
            'measurement_count': count,
        }
    )
    return 'created' if created else 'updated'


def _calculate_hourly_weather_row(station, hour_start):
    """Calcula y guarda `HourlyWeatherIndicators` de `station` para la hora
    `hour_start`. Idempotente (ver `_calculate_hourly_meter_row`). Usa
    `calculate_single_hour_weather_indicators`, cuyas claves de salida (incluido
    `measurement_count`) coinciden 1:1 con los campos del modelo."""
    start_dt, end_dt = colombia_hour_range(hour_start)
    measurements = WeatherStationMeasurement.objects.filter(
        device=station, date__gte=start_dt, date__lt=end_dt
    ).order_by('date')
    if not measurements.exists():
        return None

    measurements_list = list(measurements.values(
        'date', 'irradiance', 'temperature', 'humidity',
        'windSpeed', 'windDirection', 'precipitation',
    ))
    computed = calculate_single_hour_weather_indicators(measurements_list)

    _, created = HourlyWeatherIndicators.objects.update_or_create(
        device=station,
        hour=start_dt,
        defaults={
            **computed,
            'institution': station.institution,
        }
    )
    return 'created' if created else 'updated'


def _parse_hour_arg(value):
    """Parsea un string ISO ('YYYY-MM-DDTHH:MM[:SS]' o con offset) a un datetime
    aware truncado al INICIO de esa hora en Bogotá (reutiliza `colombia_hour_range`
    para la localización/truncado, igual criterio que el resto del módulo)."""
    dt = datetime.fromisoformat(value)
    if django_timezone.is_naive(dt):
        dt = COLOMBIA_TZ.localize(dt)
    start_dt, _ = colombia_hour_range(dt)
    return start_dt


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def calculate_hourly_rollup(self, hours_back=4, end_hour_str=None, start_hour_str=None,
                            institution_id=None, device_id=None):
    """
    Recalcula el rollup horario (HourlyMeterIndicators/HourlyInverterIndicators/
    HourlyWeatherIndicators) de horas CERRADAS de Bogotá.

    Modo normal (el que usa `run_post_ingest_pipeline` en scada_proxy/tasks.py, que
    corre ~cada hora): recomputa las `hours_back` horas cerradas más recientes,
    terminando en `end_hour_str` si se especifica, o en la última hora YA CERRADA
    respecto a "ahora" en caso contrario (la hora en curso está incompleta y nunca se
    recalcula por defecto, para no guardar un rollup parcial).

    Modo rango explícito (el que usa el comando `backfill_hourly_rollup`): si se pasa
    `start_hour_str`, se recalculan TODAS las horas cerradas en
    [start_hour_str, end_hour_str] (ambos inclusive, un único string ISO cada uno),
    ignorando `hours_back`.

    `institution_id`/`device_id` (SCADA ID) opcionales para acotar el recálculo,
    mismo patrón que `calculate_electrical_data`/`calculate_inverter_data`.

    Por cada dispositivo activo (medidor/inversor/estación) y cada hora del rango,
    aplica la función pura correspondiente sobre la ventana de `colombia_hour_range`
    y hace `update_or_create(device, hour)`: idempotente, correr dos veces sobre la
    misma hora no duplica filas.
    """
    logger.info("=== INICIANDO TAREA: calculate_hourly_rollup ===")
    try:
        now = get_colombia_now()

        if end_hour_str:
            end_hour = _parse_hour_arg(end_hour_str)
        else:
            # Última hora YA CERRADA respecto a "ahora" (ver docstring).
            end_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        if start_hour_str:
            start_hour = _parse_hour_arg(start_hour_str)
        else:
            start_hour = end_hour - timedelta(hours=max(hours_back, 1) - 1)

        if start_hour > end_hour:
            msg = f"Rango horario inválido: start_hour ({start_hour}) posterior a end_hour ({end_hour}); no se procesó nada."
            logger.warning(msg)
            return msg

        hours = []
        cursor = start_hour
        while cursor <= end_hour:
            hours.append(cursor)
            cursor += timedelta(hours=1)

        logger.info(f"Procesando {len(hours)} hora(s) cerrada(s), de {start_hour.isoformat()} a {end_hour.isoformat()}")

        electric_meters = Device.objects.filter(category__name__iexact='electricMeter', is_active=True)
        inverters = Device.objects.filter(category__name__iexact='inverter', is_active=True)
        weather_stations = Device.objects.filter(category__name__iexact='weatherStation', is_active=True)

        if institution_id:
            electric_meters = electric_meters.filter(institution_id=institution_id)
            inverters = inverters.filter(institution_id=institution_id)
            weather_stations = weather_stations.filter(institution_id=institution_id)
            logger.info(f"Filtrado por institución ID: {institution_id}")

        if device_id:
            electric_meters = electric_meters.filter(scada_id=device_id)
            inverters = inverters.filter(scada_id=device_id)
            weather_stations = weather_stations.filter(scada_id=device_id)
            logger.info(f"Filtrado por dispositivo ID: {device_id}")

        electric_meters = list(electric_meters)
        inverters = list(inverters)
        weather_stations = list(weather_stations)

        logger.info(
            f"Dispositivos a procesar: {len(electric_meters)} medidores, "
            f"{len(inverters)} inversores, {len(weather_stations)} estaciones"
        )

        created = updated = skipped = 0

        for hour_start in hours:
            for meter in electric_meters:
                result = _calculate_hourly_meter_row(meter, hour_start)
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1
                else:
                    skipped += 1

            for inverter in inverters:
                result = _calculate_hourly_inverter_row(inverter, hour_start)
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1
                else:
                    skipped += 1

            for station in weather_stations:
                result = _calculate_hourly_weather_row(station, hour_start)
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1
                else:
                    skipped += 1

        summary = (
            f"Rollup horario completado: {len(hours)} hora(s) procesada(s), "
            f"{created} fila(s) creadas, {updated} actualizadas, {skipped} omitidas (sin mediciones)."
        )
        logger.info(summary)
        logger.info("=== TAREA COMPLETADA: calculate_hourly_rollup ===")
        return summary

    except Exception as e:
        logger.error("=== ERROR EN TAREA: calculate_hourly_rollup ===")
        logger.error(f"Error calculando rollup horario: {e}", exc_info=True)
        raise


# =========================
# TAREAS PARA GENERACIÓN DE REPORTE
# =========================

@shared_task(bind=True, retry_backoff=60, max_retries=3,
             soft_time_limit=1800, time_limit=2000)
def generate_report(self, institution_id, category, devices, report_type, time_range, start_date, end_date, format, user_id):
    """
    Genera un reporte en el formato especificado
    """
    logger.info(f"=== INICIANDO GENERACIÓN DE REPORTE ===")
    logger.info(f"Tarea ID: {self.request.id}")
    logger.info(f"Parámetros: {institution_id}, {category}, {report_type}, {time_range}, {start_date} - {end_date}, {format}")
    
    try:
        # Crear registro del reporte
        from .models import GeneratedReport
        from scada_proxy.models import Institution
        
        # Obtener nombre de la institución
        try:
            institution = Institution.objects.get(id=institution_id)
            institution_name = institution.name
        except Institution.DoesNotExist:
            raise ValueError(f"Institución con ID {institution_id} no encontrada")
        
        # Crear o actualizar registro del reporte
        report_record, created = GeneratedReport.objects.get_or_create(
            task_id=self.request.id,
            defaults={
                'user_id': user_id,
                'report_type': report_type,
                'category': category,
                'institution_id': institution_id,
                'institution_name': institution_name,
                'devices': devices,
                'time_range': time_range,
                'start_date': start_date,
                'end_date': end_date,
                'format': format,
                'status': 'processing'
            }
        )
        
        if not created:
            report_record.status = 'processing'
            report_record.save()
        
        logger.info(f"Registro de reporte {'creado' if created else 'actualizado'} con ID: {report_record.id}")
        
        # Actualizar progreso de la tarea
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Iniciando generación de reporte'}
        )
        
        logger.info(f"Estado de tarea actualizado a PROGRESS")
        
        # Generar reporte según la categoría y tipo
        logger.info(f"Generando reporte para categoría: {category}")
        
        if category == 'electricMeter':
            report_data = generate_electric_meter_report(
                institution_id, devices, report_type, time_range, start_date, end_date
            )
        elif category == 'inverter':
            report_data = generate_inverter_report(
                institution_id, devices, report_type, time_range, start_date, end_date
            )
        elif category == 'weatherStation':
            report_data = generate_weather_station_report(
                institution_id, devices, report_type, time_range, start_date, end_date
            )
        else:
            raise ValueError(f"Categoría no válida: {category}")
        
        logger.info(f"Reporte generado exitosamente para categoría {category}")
        
        # Actualizar progreso
        self.update_state(
            state='PROGRESS',
            meta={'current': 50, 'total': 100, 'status': 'Generando archivo'}
        )
        
        logger.info(f"Estado de tarea actualizado a 50%")
        
        # Generar archivo en el formato especificado
        logger.info(f"Generando archivo en formato: {format}")
        
        report_context = {
            'institution_name': institution_name,
            'category': category,
            'devices': devices,
            'time_range': time_range,
            'start_date': start_date,
            'end_date': end_date,
        }
        file_path, file_size, record_count = generate_report_file(
            report_data, report_type, format, self.request.id, context=report_context
        )
        
        logger.info(f"Archivo generado: {file_path}, tamaño: {file_size}, registros: {record_count}")
        
        # Actualizar progreso
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Finalizando'}
        )
        
        logger.info(f"Estado de tarea actualizado a 90%")
        
        # Actualizar registro del reporte
        report_record.status = 'completed'
        report_record.file_path = file_path
        report_record.file_size = file_size
        report_record.record_count = record_count
        report_record.completed_at = django_timezone.now()
        report_record.save()
        
        logger.info(f"Registro de reporte actualizado a completado")
        logger.info(f"Reporte generado exitosamente: {file_path}")
        
        return {
            'status': 'completed',
            'file_path': file_path,
            'file_size': file_size,
            'record_count': record_count
        }
        
    except Exception as e:
        logger.error(f"Error generando reporte: {str(e)}")
        
        # Actualizar registro del reporte con error
        try:
            report_record = GeneratedReport.objects.get(task_id=self.request.id)
            report_record.status = 'failed'
            report_record.error_message = str(e)
            report_record.save()
        except GeneratedReport.DoesNotExist:
            pass
        
        # Reintentar si es posible
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        else:
            raise e


def _device_filter(devices):
    """Q de los dispositivos elegidos en Exportar Reportes, o None si no se eligió ninguno.

    El frontend envía el `scada_id` (UUID) de cada dispositivo; se aceptan también ids enteros. Antes se hacía
    `int(device_id)`, que fallaba con los UUID, y el `except` quitaba el filtro en silencio: el reporte traía todos
    los dispositivos de la institución.
    """
    if not devices:
        logger.info("Sin filtro de dispositivos: no se eligió ninguno")
        return None
    if not isinstance(devices, list):
        raise ValueError(f"Lista de dispositivos inválida: {devices!r}")
    ids, scada_ids = [], []
    for device in devices:
        valor = str(device).strip() if device is not None else ''
        if not valor:
            raise ValueError(f"Dispositivo vacío en la lista: {devices!r}")
        (ids if valor.isdigit() else scada_ids).append(int(valor) if valor.isdigit() else valor)
    logger.info(f"Filtro de dispositivos: ids={ids} scada_ids={scada_ids}")
    return Q(device_id__in=ids) | Q(device__scada_id__in=scada_ids)


def generate_electric_meter_report(institution_id, devices, report_type, time_range, start_date, end_date):
    """
    Genera datos para reportes de medidores eléctricos
    """
    from .models import ElectricMeterIndicators
    
    logger.info(f"Generando reporte de medidores eléctricos: {report_type}")
    logger.info(f"Parámetros: institution_id={institution_id}, devices={devices}, time_range={time_range}, start_date={start_date}, end_date={end_date}")
    
    # Convertir fechas
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Construir filtros base
    filters = Q(
        institution_id=institution_id,
        time_range=time_range,
        date__range=(start_date, end_date)
    )
    
    # Filtrar por los dispositivos elegidos (scada_id del frontend o id entero)
    device_filter = _device_filter(devices)
    if device_filter is not None:
        filters &= device_filter
    
    # Obtener datos según el tipo de reporte
    if report_type == 'Resumen de Consumo':
        # Repuntado a ElectricMeterIndicators (fuente única, energía saneada anti
        # roll-over) en vez de ElectricMeterEnergyConsumption, que estaba vacía.
        data = ElectricMeterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'imported_energy_kwh', 'exported_energy_kwh', 'net_energy_consumption_kwh']
        
    elif report_type == 'Análisis de Demanda':
        data = ElectricMeterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'peak_demand_kw', 'avg_demand_kw', 'load_factor_pct']
        
    elif report_type == 'Calidad de Potencia':
        data = ElectricMeterIndicators.objects.filter(filters).select_related('device')
        # TDD de corriente (IEEE 519, contra la corriente de demanda máxima) y no THD: con generación FV detrás del
        # medidor la fundamental neta cae a 1-3 A y el THD de corriente pasa del 100 % (decisión del autor, 22-oct-2026).
        columns = ['device__name', 'date', 'max_voltage_thd_pct', 'max_current_tdd_pct', 'avg_power_factor']
        
    elif report_type == 'Balance Energético':
        # Repuntado a ElectricMeterIndicators (energía saneada) en vez de la tabla vacía.
        data = ElectricMeterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'imported_energy_kwh', 'exported_energy_kwh', 'net_energy_consumption_kwh']
        
    elif report_type == 'Reporte Integral':
        data = ElectricMeterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'imported_energy_kwh', 'exported_energy_kwh', 'peak_demand_kw', 'avg_power_factor', 'max_voltage_thd_pct']
        
    else:
        raise ValueError(f"Tipo de reporte no válido: {report_type}")
    
    # Preparar datos para el reporte
    report_data = []
    for item in data:
        row = {}
        for col in columns:
            if '__' in col:
                # Campo relacionado
                parts = col.split('__')
                value = item
                for part in parts:
                    value = getattr(value, part, None)
                    if value is None:
                        break
            else:
                # Campo directo
                value = getattr(item, col, None)
            
            # Formatear valor
            if isinstance(value, (int, float)):
                if 'pct' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}%"
                elif 'kw' in col or 'kwh' in col or 'factor' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}"
                else:
                    row[col.split('__')[-1]] = value
            else:
                row[col.split('__')[-1]] = value
        
        report_data.append(row)
    
    return report_data


def generate_inverter_report(institution_id, devices, report_type, time_range, start_date, end_date):
    """
    Genera datos para reportes de inversores
    """
    from .models import InverterIndicators
    
    logger.info(f"Generando reporte de inversores: {report_type}")
    logger.info(f"Parámetros: institution_id={institution_id}, devices={devices}, time_range={time_range}, start_date={start_date}, end_date={end_date}")
    
    # Convertir fechas
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Construir filtros base
    filters = Q(
        institution_id=institution_id,
        time_range=time_range,
        date__range=(start_date, end_date)
    )
    
    # Filtrar por los dispositivos elegidos (scada_id del frontend o id entero)
    device_filter = _device_filter(devices)
    if device_filter is not None:
        filters &= device_filter
    
    # Obtener datos según el tipo de reporte
    if report_type == 'Resumen de Generación':
        data = InverterIndicators.objects.filter(filters).select_related('device')
        # Sin eficiencia DC/AC: no se calcula (C3/D6, `dcPower` mide una sola entrada MPPT).
        columns = ['device__name', 'date', 'total_generated_energy_kwh', 'energy_ac_daily_kwh', 'max_power_w']
        
    elif report_type == 'Análisis de Rendimiento':
        data = InverterIndicators.objects.filter(filters).select_related('device')
        # PR con la estación de la institución (C4/D5); el inversor no mide irradiancia ni temperatura.
        columns = ['device__name', 'date', 'performance_ratio_pct', 'reference_energy_kwh', 'performance_ratio_valid_days']
        
    elif report_type == 'Métricas Operativas':
        data = InverterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'avg_power_factor', 'avg_frequency_hz', 'frequency_stability_pct']
        
    elif report_type == 'Reporte de Anomalías':
        data = InverterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'anomaly_score', 'max_power_w', 'min_power_w']
        
    elif report_type == 'Reporte Integral':
        data = InverterIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'total_generated_energy_kwh', 'performance_ratio_pct', 'avg_power_factor']
        
    else:
        raise ValueError(f"Tipo de reporte no válido: {report_type}")
    
    # Preparar datos para el reporte
    report_data = []
    for item in data:
        row = {}
        for col in columns:
            if '__' in col:
                # Campo relacionado
                parts = col.split('__')
                value = item
                for part in parts:
                    value = getattr(value, part, None)
                    if value is None:
                        break
            else:
                # Campo directo
                value = getattr(item, col, None)
            
            # Formatear valor
            if isinstance(value, (int, float)):
                if 'pct' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}%"
                elif 'kwh' in col or 'kw' in col or 'wm2' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}"
                else:
                    row[col.split('__')[-1]] = value
            else:
                row[col.split('__')[-1]] = value
        
        report_data.append(row)
    
    return report_data


def generate_weather_station_report(institution_id, devices, report_type, time_range, start_date, end_date):
    """
    Genera datos para reportes de estaciones meteorológicas
    """
    from .models import WeatherStationIndicators
    
    logger.info(f"Generando reporte de estaciones meteorológicas: {report_type}")
    logger.info(f"Parámetros: institution_id={institution_id}, devices={devices}, time_range={time_range}, start_date={start_date}, end_date={end_date}")
    
    # Convertir fechas
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Construir filtros base
    filters = Q(
        institution_id=institution_id,
        time_range=time_range,
        date__range=(start_date, end_date)
    )
    
    # Filtrar por los dispositivos elegidos (scada_id del frontend o id entero)
    device_filter = _device_filter(devices)
    if device_filter is not None:
        filters &= device_filter
    
    # Obtener datos según el tipo de reporte
    if report_type == 'Resumen Climático':
        data = WeatherStationIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'avg_temperature_c', 'avg_humidity_pct', 'daily_precipitation_cm']
        
    elif report_type == 'Análisis Solar':
        data = WeatherStationIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'daily_irradiance_kwh_m2', 'daily_hsp_hours', 'theoretical_pv_power_w']
        
    elif report_type == 'Análisis de Viento':
        data = WeatherStationIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'avg_wind_speed_kmh', 'wind_direction_distribution', 'wind_speed_distribution']
        
    elif report_type == 'Impacto Ambiental':
        data = WeatherStationIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'avg_temperature_c', 'daily_irradiance_kwh_m2', 'theoretical_pv_power_w']
        
    elif report_type == 'Reporte Integral':
        data = WeatherStationIndicators.objects.filter(filters).select_related('device')
        columns = ['device__name', 'date', 'daily_irradiance_kwh_m2', 'avg_temperature_c', 'avg_wind_speed_kmh', 'daily_precipitation_cm']
        
    else:
        raise ValueError(f"Tipo de reporte no válido: {report_type}")
    
    # Preparar datos para el reporte
    report_data = []
    for item in data:
        row = {}
        for col in columns:
            if '__' in col:
                # Campo relacionado
                parts = col.split('__')
                value = item
                for part in parts:
                    value = getattr(value, part, None)
                    if value is None:
                        break
            else:
                # Campo directo
                value = getattr(item, col, None)
            
            # Formatear valor
            if isinstance(value, (int, float)):
                if 'pct' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}%"
                elif 'kwh' in col or 'kmh' in col or 'cm' in col:
                    row[col.split('__')[-1]] = f"{value:.2f}"
                else:
                    row[col.split('__')[-1]] = value
            else:
                row[col.split('__')[-1]] = value
        
        report_data.append(row)
    
    return report_data


def generate_report_file(report_data, report_type, format, task_id, context=None):
    """
    Genera el archivo del reporte en el formato especificado.

    `context` lleva los metadatos (institución, categoría, dispositivos, rango, time_range)
    para la marca/ficha/pie de los informes; NO cambia los datos ni el contrato de salida.
    """
    from django.conf import settings
    from indicators.reports import branding
    from indicators.services.date_ranges import get_colombia_now

    # Crear directorio para reportes si no existe
    reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    # Enriquecer el contexto con tipo de reporte y resumen ejecutivo calculado.
    context = dict(context or {})
    context['report_type'] = report_type
    context['summary'] = branding.compute_summary(report_data)

    # Nombre del archivo con hora de Colombia (antes datetime.now() del servidor).
    timestamp = get_colombia_now().strftime('%Y%m%d_%H%M%S')
    filename = f"reporte_{report_type.replace(' ', '_')}_{timestamp}_{task_id[:8]}"

    if format == 'CSV':
        file_path = os.path.join(reports_dir, f"{filename}.csv")
        file_size, record_count = generate_csv_file(report_data, file_path)

    elif format == 'Excel':
        file_path = os.path.join(reports_dir, f"{filename}.xlsx")
        file_size, record_count = generate_excel_file(report_data, file_path, report_type, context)

    elif format == 'PDF':
        file_path = os.path.join(reports_dir, f"{filename}.pdf")
        # Determinar si es un reporte ejecutivo basado en el tipo
        if 'executive' in report_type.lower() or 'ejecutivo' in report_type.lower():
            file_size, record_count = generate_executive_pdf_file(
                report_data, file_path, report_type, context
            )
        else:
            file_size, record_count = generate_pdf_file(report_data, file_path, report_type, context)

    else:
        raise ValueError(f"Formato no soportado: {format}")

    return file_path, file_size, record_count


def generate_csv_file(report_data, file_path):
    """
    Genera archivo CSV
    """
    
    if not report_data:
        # Crear archivo vacío
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['No hay datos disponibles para el período seleccionado'])
        return "0 KB", 0
    
    # Obtener columnas del primer registro
    columns = list(report_data[0].keys())
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        writer.writerows(report_data)
    
    # Calcular tamaño del archivo
    file_size = os.path.getsize(file_path)
    file_size_str = format_file_size(file_size)
    
    return file_size_str, len(report_data)


def generate_excel_file(report_data, file_path, report_type="", context=None):
    """
    Genera un archivo Excel profesional: banda de título con logo, hoja de resumen ejecutivo,
    cabecera congelada, autofiltro, formato numérico por columna, filas zebra y autoancho.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        # Fallback a CSV si no hay openpyxl
        logger.warning("openpyxl no disponible, generando CSV en su lugar")
        return generate_csv_file(report_data, file_path.replace('.xlsx', '.csv'))

    from indicators.reports import branding
    from indicators.services.date_ranges import get_colombia_now

    if not report_data:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 'No hay datos disponibles para el período seleccionado'
        wb.save(file_path)
        return "0 KB", 0

    context = context or {}
    columns = list(report_data[0].keys())
    n = len(columns)

    thin = Side(style="thin", color=branding.GRID)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor=branding.DARK)
    zebra_fill = PatternFill("solid", fgColor=branding.ZEBRA)
    title_font = Font(bold=True, size=16, color=branding.ACCENT)

    wb = openpyxl.Workbook()
    wb.properties.creator = "SIVE — Universidad de Nariño"
    wb.properties.company = "Universidad de Nariño"
    wb.properties.title = f"Reporte: {report_type}"

    # --- Hoja de Resumen Ejecutivo (primera) ---
    summary = context.get('summary') or {}
    metrics = summary.get('metrics') or []
    if metrics:
        rs = wb.active
        rs.title = "Resumen Ejecutivo"
        rs["A1"] = "MTE · SIVE — Resumen Ejecutivo"
        rs["A1"].font = title_font
        rs["A2"] = f"Reporte: {report_type}  ·  Institución: {context.get('institution_name', '—')}"
        rs["A3"] = (f"Rango: {context.get('start_date', '')} a {context.get('end_date', '')}  ·  "
                    f"Registros: {summary.get('record_count', 0)}  ·  "
                    f"Generado: {get_colombia_now():%d/%m/%Y %H:%M} (hora Colombia)")
        agg_es = {"sum": "Total", "mean": "Promedio", "max": "Máximo", "min": "Mínimo"}
        head_row = 5
        for c, h in enumerate(["Indicador", "Valor", "Unidad", "Agregado"], 1):
            cell = rs.cell(row=head_row, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=branding.PRIMARY)
            cell.alignment = Alignment(horizontal="center")
            cell.border = border
        for i, m in enumerate(metrics):
            r = head_row + 1 + i
            rs.cell(row=r, column=1, value=m["label"]).border = border
            vcell = rs.cell(row=r, column=2, value=round(m["value"], 2))
            vcell.number_format = '#,##0.00'
            vcell.alignment = Alignment(horizontal="right")
            vcell.border = border
            rs.cell(row=r, column=3, value=m["unit"]).border = border
            rs.cell(row=r, column=4, value=agg_es.get(m["agg"], m["agg"])).border = border
            if i % 2:
                for c in range(1, 5):
                    rs.cell(row=r, column=c).fill = zebra_fill
        rs.column_dimensions["A"].width = 34
        rs.column_dimensions["B"].width = 16
        rs.column_dimensions["C"].width = 10
        rs.column_dimensions["D"].width = 12
        rs.freeze_panes = "A6"
        ws = wb.create_sheet("Datos")
    else:
        ws = wb.active
        ws.title = "Datos"

    # --- Hoja de Datos ---
    # Banda de título + logo (filas 1-3), cabecera en fila 5, datos desde fila 6.
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=max(2, n))
    ws.cell(row=1, column=2, value="MTE · SIVE — Universidad de Nariño").font = title_font
    ws.cell(row=2, column=2, value=f"Reporte: {report_type}").font = Font(bold=True, size=11, color=branding.DARK)
    ws.cell(row=3, column=2, value=(f"Rango: {context.get('start_date', '')} a {context.get('end_date', '')}  ·  "
                                    f"Registros: {len(report_data)}  ·  "
                                    f"Generado: {get_colombia_now():%d/%m/%Y %H:%M}")).font = Font(size=9, color=branding.DARK)
    try:
        logo_path = branding.resolve_logo(branding.LOGO_MTE)
        if logo_path:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(logo_path)
            img.height = 54
            img.width = int(54 * (img.width / img.height)) if img.height else 118
            ws.add_image(img, "A1")
            ws.row_dimensions[1].height = 22
    except Exception as exc:  # noqa: BLE001 - el logo es opcional
        logger.warning(f"No se pudo incrustar el logo en Excel: {exc}")

    HEADER_ROW = 5
    DATA_START = HEADER_ROW + 1

    # Detectar columnas numéricas (mayoría de valores parseables) para formatear.
    numeric_cols = set()
    for col in columns:
        vals = [branding.to_number(r.get(col)) for r in report_data[:20]]
        parsed = [v for v in vals if v is not None]
        if parsed and len(parsed) >= max(1, len(vals) // 2):
            numeric_cols.add(col)

    for c, col in enumerate(columns, 1):
        header = branding.pretty_header(col) if col in numeric_cols else col.replace('_', ' ').capitalize()
        cell = ws.cell(row=HEADER_ROW, column=c, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for i, data_row in enumerate(report_data):
        r = DATA_START + i
        for c, col in enumerate(columns, 1):
            raw = data_row.get(col, '')
            if col in numeric_cols:
                num = branding.to_number(raw)
                cell = ws.cell(row=r, column=c, value=round(num, 4) if num is not None else None)
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal="right")
            else:
                cell = ws.cell(row=r, column=c, value=raw)
                cell.alignment = Alignment(horizontal="left")
            cell.border = border
            if i % 2:
                cell.fill = zebra_fill

    # Congelar cabecera, autofiltro y títulos de impresión.
    ws.freeze_panes = ws.cell(row=DATA_START, column=1).coordinate
    last_row = DATA_START + len(report_data) - 1
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(n)}{last_row}"
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"

    # Autoancho robusto por índice de columna.
    for c, col in enumerate(columns, 1):
        header_len = len(branding.pretty_header(col))
        max_len = max([header_len] + [len(str(r.get(col, ''))) for r in report_data[:200]])
        ws.column_dimensions[get_column_letter(c)].width = min(max_len + 3, 42)

    wb.active = 0
    wb.save(file_path)

    file_size = os.path.getsize(file_path)
    return format_file_size(file_size), len(report_data)


def generate_pdf_file(report_data, file_path, report_type, context=None):
    """
    Genera archivo PDF profesional: banda con logos MTE+SIVE, ficha de parámetros, resumen
    ejecutivo real, tablas pulidas y encabezado/pie con paginación.
    """
    context = context or {}
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch, cm
        from reportlab.pdfgen import canvas
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        import io
        import numpy as np
    except ImportError as e:
        # Fallback a CSV si no hay reportlab o matplotlib
        logger.warning(f"Librerías no disponibles: {e}, generando CSV en su lugar")
        return generate_csv_file(report_data, file_path.replace('.pdf', '.csv'))
    
    from indicators.reports import branding
    from indicators.services.date_ranges import get_colombia_now

    # Crear documento PDF (topMargin holgado para la banda de logos de la 1ª página)
    doc = SimpleDocTemplate(file_path, pagesize=A4,
                          rightMargin=2*cm, leftMargin=2*cm,
                          topMargin=3.5*cm, bottomMargin=2*cm)
    on_first_page, on_later_pages = branding.make_header_footer(context)
    story = []
    
    # Estilos mejorados
    styles = getSampleStyleSheet()
    
    # Estilo para título principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1f2937'),
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#374151'),
        fontName='Helvetica-Bold',
        spaceBefore=25
    )
    
    # Estilo para texto normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#4b5563'),
        fontName='Helvetica'
    )
    
    # Estilo para información destacada
    highlight_style = ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=15,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#059669'),
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#ecfdf5'),
        borderPadding=10,
        borderWidth=1,
        borderColor=colors.HexColor('#10b981')
    )
    
    # Encabezado del reporte
    story.append(Paragraph(f"REPORTE DETALLADO: {report_type.upper()}", title_style))
    story.append(Spacer(1, 6))

    # Ficha de parámetros (institución, categoría, dispositivos, rango, agregación, generado)
    story.append(branding.build_param_table(context))
    story.append(Spacer(1, 18))

    if not report_data:
        story.append(Paragraph("No hay datos disponibles para el período seleccionado", highlight_style))
        doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        file_size = os.path.getsize(file_path)
        return format_file_size(file_size), 0

    # Resumen ejecutivo real (totales/promedios por indicador desde el valor crudo)
    summary_table = branding.build_summary_table(context.get('summary'))
    if summary_table is not None:
        story.append(Paragraph("RESUMEN EJECUTIVO", subtitle_style))
        story.append(summary_table)
        story.append(Spacer(1, 20))

    # Columnas numéricas (para gráficos) detectadas por parseo real
    numeric_columns = [c for c in report_data[0].keys()
                       if c not in ('name', 'date') and branding.to_number(report_data[0].get(c)) is not None]

    # Análisis estadístico básico (desactivado: sustituido por el RESUMEN EJECUTIVO real)
    if False:
        if numeric_columns:
            # Crear tabla de estadísticas
            stats_data = [['Métrica', 'Valor']]

            for col in numeric_columns[:5]:  # Limitar a 5 columnas para no sobrecargar
                try:
                    values = []
                    for row in report_data:
                        val = row.get(col, 0)
                        if isinstance(val, str):
                            val = float(val) if val.replace('.', '').replace('-', '').isdigit() else 0
                        if isinstance(val, (int, float)):
                            values.append(val)

                    if values:
                        stats_data.append([f'Promedio {col}', f'{np.mean(values):.2f}'])
                        stats_data.append([f'Máximo {col}', f'{np.max(values):.2f}'])
                        stats_data.append([f'Mínimo {col}', f'{np.min(values):.2f}'])
                except:
                    continue

            if len(stats_data) > 1:
                stats_table = Table(stats_data, colWidths=[4*cm, 3*cm])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
                ]))
                story.append(stats_table)
                story.append(Spacer(1, 20))
    
    # Generar gráficos si hay datos numéricos
    if len(report_data) > 1 and numeric_columns:
        story.append(Paragraph("GRÁFICOS Y VISUALIZACIONES", subtitle_style))
        
        # Gráfico de línea temporal para la primera columna numérica
        try:
            time_col = None
            for col in report_data[0].keys():
                if 'fecha' in col.lower() or 'date' in col.lower() or 'time' in col.lower():
                    time_col = col
                    break
            
            if time_col:
                # Crear gráfico de línea
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Preparar datos para el gráfico
                x_values = []
                y_values = []
                
                for row in report_data[:50]:  # Limitar a 50 puntos para el gráfico
                    try:
                        time_val = row.get(time_col, '')
                        if isinstance(time_val, str):
                            # Intentar parsear fecha
                            try:
                                parsed_time = datetime.strptime(time_val, '%Y-%m-%d %H:%M:%S')
                                x_values.append(parsed_time)
                            except:
                                x_values.append(len(x_values))
                        else:
                            x_values.append(len(x_values))
                        
                        # Valor numérico para Y
                        for num_col in numeric_columns[:1]:  # Solo primera columna numérica
                            val = row.get(num_col, 0)
                            if isinstance(val, str):
                                val = float(val) if val.replace('.', '').replace('-', '').isdigit() else 0
                            y_values.append(val if isinstance(val, (int, float)) else 0)
                            break
                    except:
                        continue
                
                if len(x_values) > 1 and len(y_values) > 1:
                    ax.plot(x_values, y_values, marker='o', linewidth=2, markersize=4)
                    ax.set_title(f'Tendencia de {numeric_columns[0]}', fontsize=14, fontweight='bold')
                    ax.set_xlabel('Tiempo', fontsize=12)
                    ax.set_ylabel(numeric_columns[0], fontsize=12)
                    ax.grid(True, alpha=0.3)
                    
                    # Formatear eje X si son fechas
                    if isinstance(x_values[0], datetime):
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(x_values)//10)))
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                    
                    plt.tight_layout()
                    
                    # Guardar gráfico en memoria
                    img_buffer = io.BytesIO()
                    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                    img_buffer.seek(0)
                    
                    # Agregar imagen al PDF
                    story.append(Image(img_buffer, width=12*cm, height=7*cm))
                    story.append(Spacer(1, 20))
                    
                    plt.close()
        except Exception as e:
            logger.warning(f"Error generando gráfico: {e}")
    
    # Datos detallados
    story.append(Paragraph("DATOS DETALLADOS", subtitle_style))
    story.append(Paragraph("A continuación se presentan los datos completos del reporte en formato tabular:", normal_style))
    story.append(Spacer(1, 15))
    
    # Obtener columnas del primer registro
    columns = list(report_data[0].keys())
    
    # Limitar columnas si son demasiadas para el PDF
    if len(columns) > 8:
        story.append(Paragraph(f"<i>Nota: Se muestran las primeras 8 columnas de {len(columns)} totales para optimizar la visualización.</i>", normal_style))
        story.append(Spacer(1, 10))
        columns = columns[:8]
    
    # Detectar columnas numéricas para alinear a la derecha y totalizar.
    # Se mira toda la columna y no solo la primera fila: un primer valor nulo (p. ej. un PR sin días válidos)
    # dejaba la cabecera en crudo («Performance ratio pct»).
    numeric_set = {c for c in columns
                   if c not in ('name', 'date')
                   and any(branding.to_number(r.get(c)) is not None for r in report_data)}
    col_index = {c: i for i, c in enumerate(columns)}

    # Cabeceras legibles (con unidad en las numéricas)
    header_row = [branding.pretty_header(c) if c in numeric_set else c.replace('_', ' ').capitalize()
                  for c in columns]
    table_data = [header_row]

    max_rows = min(60, len(report_data))
    for data_row in report_data[:max_rows]:
        row = []
        for col in columns:
            value = data_row.get(col, '')
            if isinstance(value, str) and len(value) > 40:
                value = value[:37] + '...'
            # Un dato no disponible (None) va como celda vacía, igual que en CSV y Excel, no como «None».
            row.append('' if value is None else str(value))
        table_data.append(row)

    if len(report_data) > max_rows:
        story.append(Paragraph(f"<i>Nota: Se muestran las primeras {max_rows} filas de {len(report_data)} totales (el resumen ejecutivo cubre el total).</i>", normal_style))
        story.append(Spacer(1, 10))

    # Fila de TOTAL/agregado desde el resumen (solo columnas de suma).
    summary_by_label = {}
    for m in (context.get('summary') or {}).get('metrics', []):
        summary_by_label[m['label']] = m
    total_row = [''] * len(columns)
    total_row[0] = 'TOTAL'
    has_total = False
    for col in columns:
        if col in numeric_set:
            label, unit, agg = branding._column_meta(col)
            m = summary_by_label.get(label)
            if m and agg == 'sum':
                total_row[col_index[col]] = branding.fmt_value(m['value'], unit)
                has_total = True
    if has_total:
        table_data.append(total_row)

    # Anchos: reparte el ancho útil (~17cm) entre columnas
    usable = 17.0
    col_w = max(1.6, usable / len(columns))
    table = Table(table_data, colWidths=[col_w * cm] * len(columns), repeatRows=1)
    style = [
        # Encabezados
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#' + branding.DARK)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        # Datos
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#' + branding.GRID)),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#' + branding.ZEBRA)]),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]
    # Números a la derecha por columna
    for col in numeric_set:
        ci = col_index[col]
        style.append(('ALIGN', (ci, 1), (ci, -1), 'RIGHT'))
    # Estilo de la fila TOTAL
    if has_total:
        style += [
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#' + branding.TOTALS)),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#' + branding.PRIMARY)),
        ]
    table.setStyle(TableStyle(style))

    story.append(table)

    # Construir el PDF con encabezado/pie y paginación
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    
    # Calcular tamaño del archivo
    file_size = os.path.getsize(file_path)
    file_size_str = format_file_size(file_size)
    
    return file_size_str, len(report_data)


def generate_executive_pdf_file(report_data, file_path, report_type, context=None):
    """
    Genera un PDF ejecutivo con formato profesional y resumido
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch, cm
        from reportlab.pdfgen import canvas
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        import io
        import numpy as np
    except ImportError as e:
        logger.warning(f"Librerías no disponibles: {e}, usando función básica")
        return generate_pdf_file(report_data, file_path, report_type, context)

    from indicators.reports import branding
    from indicators.services.date_ranges import get_colombia_now

    context = context or {}
    institution_name = context.get('institution_name', '')
    period_info = branding.period_label(context)

    # Crear documento PDF (topMargin holgado para la banda de logos)
    doc = SimpleDocTemplate(file_path, pagesize=A4,
                          rightMargin=1.5*cm, leftMargin=1.5*cm,
                          topMargin=3.5*cm, bottomMargin=2*cm)
    on_first_page, on_later_pages = branding.make_header_footer(context)
    story = []
    
    # Estilos ejecutivos
    styles = getSampleStyleSheet()
    
    # Estilo para título principal ejecutivo
    executive_title_style = ParagraphStyle(
        'ExecutiveTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=25,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af'),
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos ejecutivos
    executive_subtitle_style = ParagraphStyle(
        'ExecutiveSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#1e293b'),
        fontName='Helvetica-Bold',
        spaceBefore=20
    )
    
    # Estilo para texto ejecutivo
    executive_text_style = ParagraphStyle(
        'ExecutiveText',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#334155'),
        fontName='Helvetica'
    )
    
    # Estilo para métricas destacadas
    metric_style = ParagraphStyle(
        'Metric',
        parent=styles['Normal'],
        fontSize=13,
        spaceAfter=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#059669'),
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#f0fdf4'),
        borderPadding=8,
        borderWidth=1,
        borderColor=colors.HexColor('#22c55e')
    )
    
    # Encabezado ejecutivo
    story.append(Paragraph("MTE - SIVE", executive_title_style))
    story.append(Paragraph("SISTEMA DE MONITOREO INTEGRAL", executive_title_style))
    story.append(Spacer(1, 15))
    
    # Información del reporte ejecutivo (ficha de parámetros)
    story.append(Paragraph(f"<b>REPORTE EJECUTIVO:</b> {report_type.upper()}", executive_subtitle_style))
    story.append(branding.build_param_table(context))
    story.append(Spacer(1, 18))

    if not report_data:
        story.append(Paragraph("No hay datos disponibles para el período seleccionado", metric_style))
        doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        file_size = os.path.getsize(file_path)
        return format_file_size(file_size), 0

    # Resumen ejecutivo real (totales/promedios por indicador)
    _summary_table = branding.build_summary_table(context.get('summary'))
    if _summary_table is not None:
        story.append(Paragraph("RESUMEN EJECUTIVO", executive_subtitle_style))
        story.append(_summary_table)
        story.append(Spacer(1, 15))
    
    # KPIs principales
    if len(report_data) > 0:
        story.append(Paragraph("INDICADORES CLAVE (KPIs)", executive_subtitle_style))
        
        # Obtener columnas numéricas para análisis
        numeric_columns = []
        for col in report_data[0].keys():
            try:
                sample_value = report_data[0][col]
                if isinstance(sample_value, (int, float)) or (isinstance(sample_value, str) and sample_value.replace('.', '').replace('-', '').isdigit()):
                    numeric_columns.append(col)
            except:
                continue
        
        if numeric_columns:
            # Crear tabla de KPIs ejecutivos
            kpi_data = [['Indicador', 'Valor', 'Tendencia']]
            
            for col in numeric_columns[:3]:  # Solo 3 KPIs principales
                try:
                    values = []
                    for row in report_data:
                        val = row.get(col, 0)
                        if isinstance(val, str):
                            val = float(val) if val.replace('.', '').replace('-', '').isdigit() else 0
                        if isinstance(val, (int, float)):
                            values.append(val)
                    
                    if values:
                        avg_val = np.mean(values)
                        max_val = np.max(values)
                        min_val = np.min(values)
                        
                        # Determinar tendencia
                        if len(values) > 1:
                            trend = "↗️" if values[-1] > values[0] else "↘️" if values[-1] < values[0] else "➡️"
                        else:
                            trend = "➡️"
                        
                        kpi_data.append([f'{col}', f'{avg_val:.2f}', trend])
                except:
                    continue
            
            if len(kpi_data) > 1:
                kpi_table = Table(kpi_data, colWidths=[5*cm, 3*cm, 2*cm])
                kpi_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                    ('FONTSIZE', (0, 1), (-1, -1), 11),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
                ]))
                story.append(kpi_table)
                story.append(Spacer(1, 20))
    
    # Gráfico ejecutivo simplificado
    if len(report_data) > 1 and numeric_columns:
        story.append(Paragraph("VISUALIZACIÓN EJECUTIVA", executive_subtitle_style))
        
        try:
            time_col = None
            for col in report_data[0].keys():
                if 'fecha' in col.lower() or 'date' in col.lower() or 'time' in col.lower():
                    time_col = col
                    break
            
            if time_col:
                # Crear gráfico ejecutivo
                fig, ax = plt.subplots(figsize=(8, 5))
                
                x_values = []
                y_values = []
                
                for row in report_data[:30]:  # Solo 30 puntos para gráfico ejecutivo
                    try:
                        time_val = row.get(time_col, '')
                        if isinstance(time_val, str):
                            try:
                                parsed_time = datetime.strptime(time_val, '%Y-%m-%d %H:%M:%S')
                                x_values.append(parsed_time)
                            except:
                                x_values.append(len(x_values))
                        else:
                            x_values.append(len(x_values))
                        
                        for num_col in numeric_columns[:1]:
                            val = row.get(num_col, 0)
                            if isinstance(val, str):
                                val = float(val) if val.replace('.', '').replace('-', '').isdigit() else 0
                            y_values.append(val if isinstance(val, (int, float)) else 0)
                            break
                    except:
                        continue
                
                if len(x_values) > 1 and len(y_values) > 1:
                    ax.plot(x_values, y_values, linewidth=3, color='#1e40af', alpha=0.8)
                    ax.fill_between(x_values, y_values, alpha=0.3, color='#1e40af')
                    ax.set_title(f'Tendencia de {numeric_columns[0]}', fontsize=14, fontweight='bold', color='#1e293b')
                    ax.set_xlabel('Tiempo', fontsize=11, color='#475569')
                    ax.set_ylabel(numeric_columns[0], fontsize=11, color='#475569')
                    ax.grid(True, alpha=0.2)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    
                    if isinstance(x_values[0], datetime):
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(x_values)//8)))
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=9)
                    
                    plt.tight_layout()
                    
                    img_buffer = io.BytesIO()
                    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', 
                              facecolor='white', edgecolor='none')
                    img_buffer.seek(0)
                    
                    story.append(Image(img_buffer, width=10*cm, height=6*cm))
                    story.append(Spacer(1, 20))
                    
                    plt.close()
        except Exception as e:
            logger.warning(f"Error generando gráfico ejecutivo: {e}")
    
    # Conclusiones ejecutivas
    story.append(Paragraph("CONCLUSIONES EJECUTIVAS", executive_subtitle_style))
    story.append(Paragraph("• Los datos analizados muestran patrones consistentes en el período evaluado", executive_text_style))
    story.append(Paragraph("• Se identifican oportunidades de optimización basadas en las métricas clave", executive_text_style))
    story.append(Paragraph("• Se recomienda continuar el monitoreo para validar tendencias", executive_text_style))
    story.append(Spacer(1, 20))
    
    # Construir el PDF con encabezado/pie y paginación
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    
    # Calcular tamaño del archivo
    file_size = os.path.getsize(file_path)
    file_size_str = format_file_size(file_size)
    
    return file_size_str, len(report_data)


def format_file_size(size_bytes):
    """
    Formatea el tamaño del archivo en formato legible
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def get_report_status(task_id, user_id=None):
    """
    Obtiene el estado de un reporte.

    Si se pasa user_id, el reporte debe pertenecer a ese usuario (evita IDOR:
    que un usuario consulte el estado/URL de reportes de otro por task_id).
    """
    try:
        lookup = {'task_id': task_id}
        if user_id is not None:
            lookup['user_id'] = user_id
        report = GeneratedReport.objects.get(**lookup)
        
        status_info = {
            'task_id': report.task_id,
            'status': report.status,
            'progress': 0,
            'download_url': None,
            'error': None,
            # Tamaño y registros del reporte terminado: el historial los muestra sin recargar la página.
            'file_size': None,
            'record_count': None,
        }
        
        if report.status == 'pending':
            status_info['progress'] = 0
        elif report.status == 'processing':
            status_info['progress'] = 50
        elif report.status == 'completed':
            status_info['progress'] = 100
            status_info['download_url'] = f"/api/reports/download/?task_id={task_id}"
            status_info['file_size'] = report.file_size
            status_info['record_count'] = report.record_count
        elif report.status == 'failed':
            status_info['progress'] = 0
            status_info['error'] = report.error_message
        
        return status_info
        
    except GeneratedReport.DoesNotExist:
        return None


def get_report_file(task_id, user_id=None):
    """
    Obtiene la información del archivo de un reporte.

    Si se pasa user_id, el reporte debe pertenecer a ese usuario (evita IDOR:
    que un usuario descargue reportes de otro conociendo el task_id).
    """
    try:
        lookup = {'task_id': task_id, 'status': 'completed'}
        if user_id is not None:
            lookup['user_id'] = user_id
        report = GeneratedReport.objects.get(**lookup)
        
        if not report.file_path or not os.path.exists(report.file_path):
            return None
        
        return {
            'file_path': report.file_path,
            'file_size': report.file_size,
            'record_count': report.record_count
        }
        
    except GeneratedReport.DoesNotExist:
        return None

@shared_task(bind=True, soft_time_limit=1800, time_limit=2000)
@single_instance('warm-solar-cache', ttl=2100)
def warm_solar_cache(self, desde_str='2024-12-01'):
    """Recalcula y guarda en caché, mes a mes, la energía horaria y la irradiación diaria de todas las instituciones
    configuradas (indicators/services/institution_energy.py). Programada tras la reconciliación nocturna para que la
    pantalla «Indicadores Solares» y el inicio respondan en milisegundos desde la primera consulta del día."""
    from indicators.institution_config import INSTITUCIONES
    from indicators.services.institution_energy import energia_horaria, irradiacion_diaria
    desde = datetime.strptime(desde_str, '%Y-%m-%d').date()
    hoy = get_colombia_date()
    for scada_id, cfg in INSTITUCIONES.items():
        energia_horaria(scada_id, desde, hoy, forzar=True)
        irradiacion_diaria(scada_id, desde, hoy, forzar=True)
        logger.info(f"warm_solar_cache: {cfg['nombre']} {desde} → {hoy} en caché")
    return f'{len(INSTITUCIONES)} instituciones en caché ({desde} → {hoy})'
