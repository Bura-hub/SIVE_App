# Importaciones existentes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiRequest, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import logging
from datetime import datetime, timedelta, timezone, date
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
import uuid 
import requests
import calendar
import pytz

# Importa los modelos de indicadores
from .models import ElectricMeterEnergyConsumption, MonthlyConsumptionKPI, DailyChartData, ElectricMeterConsumption, ElectricMeterChartData, ElectricMeterIndicators, InverterIndicators, InverterChartData, WeatherStationIndicators, WeatherStationChartData
# Importa el cliente SCADA y los modelos DeviceCategory, Measurement, Device de scada_proxy
from scada_proxy.scada_client import ScadaConnectorClient
from scada_proxy.views import check_scada_connection
from scada_proxy.models import DeviceCategory, Device, Institution
# Importa las tareas de Celery
from .tasks import calculate_monthly_consumption_kpi, calculate_and_save_daily_data

# Importaciones adicionales para los nuevos modelos - CORREGIDAS
from django.db.models import Q, Sum, Avg, Max, F, FloatField, Count, Min
from django.db.models.functions import Cast
from .serializers import ElectricMeterEnergySerializer, MonthlyConsumptionKPISerializer, DailyChartDataSerializer, ElectricMeterConsumptionSerializer, ElectricMeterChartDataSerializer, ElectricMeterCalculationRequestSerializer, ElectricMeterCalculationResponseSerializer, ElectricMeterIndicatorsSerializer, InverterIndicatorsSerializer, InverterChartDataSerializer, InverterCalculationRequestSerializer, InverterCalculationResponseSerializer, WeatherStationIndicatorsSerializer, WeatherStationChartDataSerializer, WeatherStationCalculationRequestSerializer, WeatherStationCalculationResponseSerializer
from collections import defaultdict

logger = logging.getLogger(__name__)

scada_client = ScadaConnectorClient() 

# Zona horaria de Colombia
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def get_colombia_now():
    """Obtiene la fecha y hora actual en zona horaria de Colombia"""
    from django.utils import timezone as dj_timezone
    return dj_timezone.now().astimezone(COLOMBIA_TZ)

def get_colombia_date():
    """Obtiene la fecha actual en zona horaria de Colombia"""
    return get_colombia_now().date()


# Ventana por defecto y tope del rango de fechas para los endpoints de indicadores.
# Lo que realmente acota el payload de estos endpoints es el rango de fechas (no la
# paginación): sin rango explícito se sirven los últimos 31 días y ningún rango puede
# superar 366 días.
INDICATORS_DEFAULT_RANGE_DAYS = 31
INDICATORS_MAX_RANGE_DAYS = 366


def resolve_indicators_date_range(start_date_str, end_date_str):
    """Resuelve el rango de fechas efectivo de los endpoints de indicadores.

    Devuelve una tupla (start_date, end_date, error):
    - Sin start_date ni end_date: últimos INDICATORS_DEFAULT_RANGE_DAYS días.
    - Solo end_date: ventana por defecto hacia atrás desde end_date.
    - Solo start_date: end_date = hoy (hora Colombia).
    - Rango mayor a INDICATORS_MAX_RANGE_DAYS días, fechas invertidas o formato
      inválido: error con mensaje en español (la vista debe responder 400).
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return None, None, "Formato de fecha inválido. Use YYYY-MM-DD en 'start_date' y 'end_date'."

    if end_date is None:
        end_date = get_colombia_date()
    if start_date is None:
        start_date = end_date - timedelta(days=INDICATORS_DEFAULT_RANGE_DAYS)

    if start_date > end_date:
        return None, None, "La fecha de inicio no puede ser posterior a la fecha de fin."

    if (end_date - start_date).days > INDICATORS_MAX_RANGE_DAYS:
        return None, None, (
            f"El rango de fechas solicitado supera el máximo permitido de "
            f"{INDICATORS_MAX_RANGE_DAYS} días. Reduzca el rango e intente de nuevo."
        )

    return start_date, end_date, None

@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ConsumptionSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_scada_token(self):
        try:
            return scada_client.get_token()
        except EnvironmentError as e:
            logger.error(f"SCADA configuration error: {e}")
            return Response({"detail": "SCADA server configuration error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting SCADA token: {e}")
            return Response({"detail": "No se pudo autenticar con la API SCADA. Revise las credenciales."}, status=status.HTTP_502_BAD_GATEWAY)

    @extend_schema(
        summary="Obtener resumen de consumo, generación y balance energético",
        description="Obtiene el resumen de consumo, generación y balance energético mensual",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "totalConsumption": {"type": "object"},
                    "totalGeneration": {"type": "object"},
                    "energyBalance": {"type": "object"},
                    "averageInstantaneousPower": {"type": "object"},
                    "avgDailyTemp": {"type": "object"},
                    "relativeHumidity": {"type": "object"},
                    "windSpeed": {"type": "object"},
                    "irradiance": {"type": "object"},
                    "activeInverters": {"type": "object"},
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Dashboard"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/dashboard/summary/
        
        Obtiene el resumen de consumo, generación y balance energético mensual.
        """
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token

        try:
            # Obtener el registro de KPI pre-calculado
            kpi_record = MonthlyConsumptionKPI.objects.first()
            if not kpi_record:
                logger.warning("MonthlyConsumptionKPI record not found. Task might not have run yet.")
                # Si el registro no existe, devolvemos valores por defecto en lugar de un error.
                kpi_record = MonthlyConsumptionKPI()

            # --- Consumo Total (NETO: importación − exportación, net metering) ---
            total_consumption_current_month = kpi_record.total_consumption_current_month
            total_consumption_previous_month = kpi_record.total_consumption_previous_month

            # --- Consumo Bruto (solo energía tomada de la red; inyección clampeada a 0) ---
            total_gross_consumption_current_month = kpi_record.total_gross_consumption_current_month
            total_gross_consumption_previous_month = kpi_record.total_gross_consumption_previous_month
            
            # --- Generación Total ---
            total_generation_current_month = kpi_record.total_generation_current_month
            total_generation_previous_month = kpi_record.total_generation_previous_month

            # --- Balance Energético (Generación - Consumo) ---
            # Ahora ambos valores están en kWh
            net_balance_current_month = total_generation_current_month - total_consumption_current_month
            net_balance_previous_month = total_generation_previous_month - total_consumption_previous_month

            logger.info(f"Retrieved pre-calculated KPIs: Consumption (C:{total_consumption_current_month}, P:{total_consumption_previous_month}), Generation (C:{total_generation_current_month}, P:{total_generation_previous_month}), Balance (C:{net_balance_current_month}, P:{net_balance_previous_month})")

            # --- Potencia Instantánea Promedio (Inversores) ---
            avg_instantaneous_power_current = kpi_record.avg_instantaneous_power_current_month
            avg_instantaneous_power_previous = kpi_record.avg_instantaneous_power_previous_month

            logger.info(f"Avg Instantaneous Power: Current: {avg_instantaneous_power_current} W, Previous: {avg_instantaneous_power_previous} W")

            # --- Temperatura Promedio Diaria ---
            avg_daily_temp_current = kpi_record.avg_daily_temp_current_month
            avg_daily_temp_previous = kpi_record.avg_daily_temp_previous_month
            logger.info(f"Avg Daily Temperature: Current: {avg_daily_temp_current} °C, Previous: {avg_daily_temp_previous} °C")

            # --- Humedad Relativa Promedio ---
            avg_relative_humidity_current = kpi_record.avg_relative_humidity_current_month
            avg_relative_humidity_previous = kpi_record.avg_relative_humidity_previous_month
            logger.info(f"Avg Relative Humidity: Current: {avg_relative_humidity_current} %RH, Previous: {avg_relative_humidity_previous} %RH")

            # --- Velocidad del Viento Promedio ---
            avg_wind_speed_current = kpi_record.avg_wind_speed_current_month
            avg_wind_speed_previous = kpi_record.avg_wind_speed_previous_month
            logger.info(f"Avg Wind Speed: Current: {avg_wind_speed_current} km/h, Previous: {avg_wind_speed_previous} km/h")

            # --- Irradiancia Solar Promedio ---
            avg_irradiance_current = kpi_record.avg_irradiance_current_month
            avg_irradiance_previous = kpi_record.avg_irradiance_previous_month
            logger.info(f"Avg Irradiance: Current: {avg_irradiance_current} W/m², Previous: {avg_irradiance_previous} W/m²")

            # --- Inversores Activos (Real-time from SCADA API) ---
            active_inverters_count = 0
            total_inverters_count = 0
            inverter_status_text = "normal"
            inverter_description_text = "Cargando..."

            try:
                inverter_category_obj = DeviceCategory.objects.get(name='inverter')
                inverter_scada_id = inverter_category_obj.scada_id

                scada_inverters_response = scada_client.get_devices(token, category_scada_id=inverter_scada_id) 
                scada_inverters = scada_inverters_response.get('data', [])

                total_inverters_count = len(scada_inverters)
                online_inverters_count = 0

                for inverter in scada_inverters:
                    if inverter.get('status') == 'online':
                        online_inverters_count += 1
                
                active_inverters_count = online_inverters_count
                inactive_inverters_count = total_inverters_count - active_inverters_count

                if total_inverters_count > 0:
                    if inactive_inverters_count > 0:
                        inverter_status_text = "critico"
                        inverter_description_text = f"{inactive_inverters_count} inactivos"
                    else:
                        inverter_status_text = "estable"
                        inverter_description_text = "Todos activos"
                else:
                    inverter_status_text = "normal"
                    inverter_description_text = "Sin inversores registrados"

                logger.info(f"Inverters: Active: {active_inverters_count}, Total: {total_inverters_count}")

            except DeviceCategory.DoesNotExist:
                logger.error("Inverter category not found in local DB. Cannot fetch real-time inverters from SCADA.")
                inverter_status_text = "error"
                inverter_description_text = "Categoría 'inverter' no encontrada localmente."
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting real-time inverter data from SCADA: {e}")
                inverter_status_text = "error"
                inverter_description_text = "Error de conexión SCADA"
            except Exception as e:
                logger.error(f"Error processing real-time inverter data: {e}", exc_info=True)
                inverter_status_text = "error"
                inverter_description_text = "Error interno"

            # Función de conversión de unidades
            def format_energy_value(value_base_unit, base_unit_name="kWh"):
                # Manejar valores negativos para el equilibrio energético
                is_negative = value_base_unit < 0
                abs_value = abs(value_base_unit)
                
                if base_unit_name == "kWh":
                    if abs_value >= 1_000_000:
                        formatted_value = abs_value / 1_000_000
                        unit = "GWh"
                    elif abs_value >= 1_000:
                        formatted_value = abs_value / 1_000
                        unit = "MWh"
                    else:
                        formatted_value = abs_value
                        unit = "kWh"
                    
                    # Aplicar signo negativo si es necesario
                    if is_negative:
                        return f"-{formatted_value:.2f}", unit
                    else:
                        return f"{formatted_value:.2f}", unit
                elif base_unit_name == "W":
                    if abs_value >= 1_000_000:
                        formatted_value = abs_value / 1_000_000
                        unit = "MW"
                    elif abs_value >= 1_000:
                        formatted_value = abs_value / 1_000
                        unit = "kW"
                    else:
                        formatted_value = abs_value
                        unit = "W"
                    
                    # Aplicar signo negativo si es necesario
                    if is_negative:
                        return f"-{formatted_value:.2f}", unit
                    else:
                        return f"{formatted_value:.2f}", unit
                elif base_unit_name == "°C": 
                    return f"{value_base_unit:.1f}", "°C" 
                elif base_unit_name == "%RH": 
                    return f"{value_base_unit:.1f}", "%" 
                elif base_unit_name == "km/h":
                    return f"{value_base_unit:.1f}", "km/h"
                elif base_unit_name == "W/m²":
                    return f"{value_base_unit:.1f}", "W/m²"
                return f"{value_base_unit:.2f}", base_unit_name

            def calculate_kpi_metrics(current_value, previous_value, title, base_unit_name, is_balance=False, is_average_power=False, is_temperature=False, is_humidity=False, is_wind_speed=False, is_irradiance=False):
                formatted_value, unit = format_energy_value(current_value, base_unit_name)
                change_percentage = 0.0
                status_text = "normal"
                description_text = ""

                if previous_value != 0:
                    change_percentage = ((current_value - previous_value) / previous_value) * 100
                elif current_value != 0:
                    change_percentage = 100.0 if current_value > 0 else -100.0

                if is_balance:
                    if current_value > 0:
                        description_text = "Superávit"
                        status_text = "positivo"
                    elif current_value < 0:
                        description_text = "Déficit"
                        status_text = "negativo"
                    else:
                        description_text = "Equilibrio"
                        status_text = "normal"
                elif is_average_power:
                    if current_value > 0:
                        description_text = "Generando"
                        status_text = "estable"
                    else:
                        description_text = "Sin generación"
                        status_text = "normal" 
                    
                    if change_percentage > 0:
                        description_text += f" (+{change_percentage:.2f}%)"
                    elif change_percentage < 0:
                        description_text += f" ({change_percentage:.2f}%)"
                elif is_temperature: 
                    description_text = "Rango normal"
                    status_text = "normal" 
                    
                    if change_percentage > 0:
                        description_text += f" (+{change_percentage:.1f}%)" 
                    elif change_percentage < 0:
                        description_text += f" ({change_percentage:.1f}%)"
                elif is_humidity: 
                    if 40 <= current_value <= 60: 
                        description_text = "Óptimo"
                        status_text = "optimo"
                    elif current_value > 60:
                        description_text = "Alta"
                        status_text = "critico" 
                    else:
                        description_text = "Baja"
                        status_text = "critico" 

                    if change_percentage > 0:
                        description_text += f" (+{change_percentage:.1f}%)"
                    elif change_percentage < 0:
                        description_text += f" ({change_percentage:.1f}%)"
                elif is_wind_speed:
                    if current_value < 10:
                        description_text = "Bajo"
                        status_text = "normal"
                    elif 10 <= current_value <= 30:
                        description_text = "Moderado"
                        status_text = "moderado"
                    else:
                        description_text = "Alto"
                        status_text = "critico"

                    if change_percentage > 0:
                        description_text += f" (+{change_percentage:.1f}%)"
                    elif change_percentage < 0:
                        description_text += f" ({change_percentage:.1f}%)"
                elif is_irradiance:
                    if current_value < 200:
                        description_text = "Baja"
                        status_text = "normal"
                    elif 200 <= current_value <= 800:
                        description_text = "Moderada"
                        status_text = "moderado"
                    else:
                        description_text = "Alta"
                        status_text = "optimo"

                    if change_percentage > 0:
                        description_text += f" (+{change_percentage:.1f}%)"
                    elif change_percentage < 0:
                        description_text += f" ({change_percentage:.1f}%)"
                    
                else: # Para consumo y generación
                    if change_percentage > 0:
                        status_text = "positivo"
                    elif change_percentage < 0:
                        status_text = "negativo"
                    else:
                        status_text = "normal"
                    
                    description_text = f"{'+' if change_percentage >= 0 else ''}{change_percentage:.2f}% vs mes pasado"

                change_text = f"{'+' if change_percentage >= 0 else ''}{change_percentage:.2f}% vs mes pasado"
                
                return {
                    "title": title,
                    "value": formatted_value,
                    "unit": unit,
                    "change": change_text,
                    "description": description_text,
                    "status": status_text,
                    "previousMonthValue": previous_value,
                    "previousMonthUnit": base_unit_name
                }

            # KPI de Consumo Total (NETO)
            consumption_kpi = calculate_kpi_metrics(
                total_consumption_current_month,
                total_consumption_previous_month,
                "Consumo total",
                "kWh"
            )

            # KPI de Consumo Bruto (solo importación de red)
            gross_consumption_kpi = calculate_kpi_metrics(
                total_gross_consumption_current_month,
                total_gross_consumption_previous_month,
                "Consumo bruto (red)",
                "kWh"
            )

            # KPI de Generación Total
            generation_kpi = calculate_kpi_metrics(
                total_generation_current_month,
                total_generation_previous_month,
                "Generación total",
                "kWh" 
            )

            # KPI de Equilibrio Energético (Generación - Consumo)
            energy_balance_kpi = calculate_kpi_metrics(
                net_balance_current_month,
                net_balance_previous_month, 
                "Equilibrio energético",
                "kWh", 
                is_balance=True
            )

            # KPI de Potencia Instantánea Promedio
            avg_power_kpi = calculate_kpi_metrics(
                avg_instantaneous_power_current,
                avg_instantaneous_power_previous,
                "Pot. instan. promedio", 
                "W", 
                is_average_power=True 
            )

            # KPI de Temperatura Promedio Diaria
            avg_daily_temp_kpi = calculate_kpi_metrics(
                avg_daily_temp_current,
                avg_daily_temp_previous,
                "Temp. prom. diaria",
                "°C",
                is_temperature=True 
            )

            # KPI de Humedad Relativa Promedio
            avg_relative_humidity_kpi = calculate_kpi_metrics(
                avg_relative_humidity_current,
                avg_relative_humidity_previous,
                "Humedad relativa", 
                "%RH", 
                is_humidity=True 
            )

            # Nuevo KPI de Velocidad del Viento Promedio
            avg_wind_speed_kpi = calculate_kpi_metrics(
                avg_wind_speed_current,
                avg_wind_speed_previous,
                "Velocidad del viento",
                "km/h",
                is_wind_speed=True
            )

            # KPI de Irradiancia Solar
            avg_irradiance_kpi = calculate_kpi_metrics(
                avg_irradiance_current,
                avg_irradiance_previous,
                "Irradiancia solar",
                "W/m²",
                is_irradiance=True
            )

            # KPI de Inversores Activos
            active_inverters_kpi = {
                "title": "Inversores activos",
                "value": str(active_inverters_count),
                "unit": f"/{total_inverters_count}",
                "description": inverter_description_text,
                "status": inverter_status_text
            }

            # Indicador de si hay datos precalculados (registro existente y al menos un valor no cero)
            has_data = bool(getattr(kpi_record, 'pk', None)) and any([
                total_consumption_current_month,
                total_generation_current_month,
                avg_instantaneous_power_current,
                avg_daily_temp_current,
                avg_relative_humidity_current,
                avg_wind_speed_current,
                avg_irradiance_current,
            ])
            scada_connected, scada_message = check_scada_connection()

            kpi_data = {
                "totalConsumption": consumption_kpi,
                "grossConsumption": gross_consumption_kpi,
                "totalGeneration": generation_kpi,
                "energyBalance": energy_balance_kpi,
                "averageInstantaneousPower": avg_power_kpi,
                "avgDailyTemp": avg_daily_temp_kpi,
                "relativeHumidity": avg_relative_humidity_kpi,
                "windSpeed": avg_wind_speed_kpi,
                "irradiance": avg_irradiance_kpi,
                "activeInverters": active_inverters_kpi,
                "hasData": has_data,
                "scadaConnection": {"connected": scada_connected, "message": scada_message},
            }
            return Response(kpi_data)

        except Exception as e:
            logger.error(f"Internal error processing KPIs from local DB or SCADA: {e}", exc_info=True)
            return Response({"detail": f"Internal server error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- NUEVA CLASE PARA LOS DATOS DEL GRÁFICO (REEMPLAZA A LA FUNCIÓN) ---

# Modificar la vista ChartDataView para incluir unidades automáticas
@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ChartDataView(APIView):
    permission_classes = [IsAuthenticated]

    def format_energy_value(self, value_base_unit, base_unit_name="kWh"):
        # Manejar valores negativos para el equilibrio energético
        is_negative = value_base_unit < 0
        abs_value = abs(value_base_unit)
        
        if base_unit_name == "kWh":
            if abs_value >= 1_000_000:
                formatted_value = abs_value / 1_000_000
                unit = "GWh"
            elif abs_value >= 1_000:
                formatted_value = abs_value / 1_000
                unit = "MWh"
            else:
                formatted_value = abs_value
                unit = "kWh"
            
            # Aplicar signo negativo si es necesario
            if is_negative:
                return f"-{formatted_value:.2f}", unit
            else:
                return f"{formatted_value:.2f}", unit
        else:
            return f"{value_base_unit:.2f}", base_unit_name

    @extend_schema(
        summary="Obtener datos diarios de consumo, generación, balance, temperatura, velocidad del viento e irradiancia",
        description="Obtiene datos diarios de consumo, generación, balance, temperatura, velocidad del viento e irradiancia para gráficos.",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de inicio en formato YYYY-MM-DD",
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de fin en formato YYYY-MM-DD",
                required=False
            ),
        ],
        responses={
            200: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "daily_consumption": {"type": "number"},
                        "daily_generation": {"type": "number"},
                        "daily_balance": {"type": "number"},
                        "avg_daily_temp": {"type": "number"},
                        "avg_wind_speed": {"type": "number"},
                        "avg_irradiance": {"type": "number"},
                    }
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Dashboard"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/dashboard/chart-data/
        
        Obtiene datos diarios de consumo, generación, balance, temperatura, velocidad del viento e irradiancia para gráficos.
        Por defecto, retorna los datos de los últimos 60 días.
        """
        try:
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            # Si no se proporcionan fechas, se usa los últimos 60 días por defecto
            if not start_date_str or not end_date_str:
                end_date = get_colombia_now().date()
                start_date = end_date - timedelta(days=60)
            else:
                # Parsear fechas y asegurar que estén en zona horaria de Colombia
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                
                # Localizar las fechas en zona horaria de Colombia
                end_date = COLOMBIA_TZ.localize(end_date).date()
                start_date = COLOMBIA_TZ.localize(start_date).date()

            # Consultar el modelo DailyChartData para obtener los datos precalculados
            chart_data = DailyChartData.objects.filter(
                date__range=(start_date, end_date)
            ).order_by('date').values('date', 'daily_consumption', 'daily_generation', 'daily_balance', 'avg_daily_temp', 'avg_wind_speed', 'avg_irradiance')

            # Calcular unidades automáticas basadas en los valores
            consumption_values = [item['daily_consumption'] for item in chart_data if item['daily_consumption'] is not None]
            generation_values = [item['daily_generation'] for item in chart_data if item['daily_generation'] is not None]
            balance_values = [item['daily_balance'] for item in chart_data if item['daily_balance'] is not None]
            
            # Determinar unidades automáticas
            max_consumption = max(consumption_values) if consumption_values else 0
            max_generation = max(generation_values) if generation_values else 0
            max_balance = max(abs(min(balance_values)) if balance_values else 0, abs(max(balance_values)) if balance_values else 0)
            
            # IMPORTANTE: Los datos ya están convertidos a kWh en las tareas de Celery
            # Consumo: totalActivePower (kW) → kWh (ya convertido en tasks.py)
            # Generación: acPower (W) → kWh (ya convertido en tasks.py)

            # Determinar unidades para consumo (usar la misma lógica que format_energy_value)
            if max_consumption >= 1_000_000:
                consumption_unit = "GWh"
                consumption_divider = 1_000_000
            elif max_consumption >= 1_000:
                consumption_unit = "MWh"
                consumption_divider = 1_000
            else:
                consumption_unit = "kWh"
                consumption_divider = 1

            # Determinar unidades para generación (usar la misma lógica)
            if max_generation >= 1_000_000:
                generation_unit = "GWh"
                generation_divider = 1_000_000
            elif max_generation >= 1_000:
                generation_unit = "MWh"
                generation_divider = 1_000
            else:
                generation_unit = "kWh"
                generation_divider = 1

            # Determinar unidades para balance (usar la misma lógica)
            if max_balance >= 1_000_000:
                balance_unit = "GWh"
                balance_divider = 1_000_000
            elif max_balance >= 1_000:
                balance_unit = "MWh"
                balance_divider = 1_000
            else:
                balance_unit = "kWh"
                balance_divider = 1

            # Formatear el queryset a una lista de diccionarios con fechas en formato string
            response_data = [
                {
                    'date': item['date'].isoformat(),
                    'daily_consumption': item['daily_consumption'] / consumption_divider if item['daily_consumption'] is not None else 0,
                    'daily_generation': item['daily_generation'] / generation_divider if item['daily_generation'] is not None else 0,
                    'daily_balance': item['daily_balance'] / balance_divider if item['daily_balance'] is not None else 0,
                    'avg_daily_temp': item['avg_daily_temp'],
                    'avg_wind_speed': item['avg_wind_speed'] if item['avg_wind_speed'] is not None else 0,
                    'avg_irradiance': item['avg_irradiance'] if item['avg_irradiance'] is not None else 0,
                    'units': {
                        'consumption': consumption_unit,
                        'generation': generation_unit,
                        'balance': balance_unit,
                        'temperature': '°C',
                        'wind_speed': 'km/h',
                        'irradiance': 'W/m²'
                    }
                }
                for item in chart_data
            ]
            
            return Response(response_data)
        except Exception as e:
            logger.error(f"Error al obtener los datos del gráfico: {e}", exc_info=True)
            return Response({'error': 'Ocurrió un error inesperado al procesar la solicitud.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- NUEVAS VISTAS PARA EJECUTAR TAREAS MANUALMENTE ---

class CalculateKPIsView(APIView):
    """
    Vista para ejecutar manualmente la tarea de cálculo de KPIs mensuales
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Ejecutar cálculo de KPIs mensuales",
        description="Ejecuta manualmente el cálculo de KPIs mensuales.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "task_result": {"type": "string"},
                    "status": {"type": "string"},
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Dashboard"]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/dashboard/calculate-kpis/
        
        Ejecuta manualmente la tarea de cálculo de KPIs mensuales.
        """
        try:
            logger.info("=== INICIANDO CÁLCULO MANUAL DE KPIs ===")
            
            # Ejecutar la tarea de cálculo de KPIs
            task_result = calculate_monthly_consumption_kpi()
            
            logger.info("=== CÁLCULO MANUAL DE KPIs COMPLETADO ===")
            
            return Response({
                "message": "Cálculo de KPIs mensuales iniciado exitosamente",
                "task_result": task_result,
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al ejecutar cálculo de KPIs: {e}", exc_info=True)
            return Response({
                "message": f"Error al ejecutar cálculo de KPIs: {str(e)}",
                "status": "error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CalculateDailyDataView(APIView):
    """
    Vista para ejecutar manualmente la tarea de cálculo de datos diarios
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Ejecutar cálculo de datos diarios",
        description="Ejecuta manualmente el cálculo de datos diarios.",
        request={
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Número de días hacia atrás para calcular",
                    "default": 3
                }
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "task_result": {"type": "string"},
                    "status": {"type": "string"},
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Dashboard"]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/dashboard/calculate-daily-data/
        
        Ejecuta manualmente la tarea de cálculo de datos diarios.
        
        Cuerpo de la petición:
        - days_back: número de días hacia atrás para calcular (por defecto: 3)
        """
        try:
            logger.info("=== INICIANDO CÁLCULO MANUAL DE DATOS DIARIOS ===")
            
            # Obtener parámetros del request
            days_back = request.data.get('days_back', 3)  # Por defecto 3 días
            
            # Calcular fechas en zona horaria de Colombia
            end_date = get_colombia_now()
            start_date = end_date - timedelta(days=days_back)
            
            logger.info(f"Calculando datos diarios desde {start_date.date()} hasta {end_date.date()} (hora Colombia)")
            
            # Ejecutar la tarea de cálculo de datos diarios
            task_result = calculate_and_save_daily_data(
                start_date_str=start_date.isoformat(),
                end_date_str=end_date.isoformat()
            )
            
            logger.info("=== CÁLCULO MANUAL DE DATOS DIARIOS COMPLETADO ===")
            
            return Response({
                "message": f"Cálculo de datos diarios iniciado exitosamente para los últimos {days_back} días",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "task_result": task_result,
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error al ejecutar cálculo de datos diarios: {e}", exc_info=True)
            return Response({
                "message": f"Error al ejecutar cálculo de datos diarios: {str(e)}",
                "status": "error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ElectricMeterIndicatorsView(APIView):
    """
    Vista para obtener indicadores de medidores eléctricos filtrados por:
    - Rango de tiempo (diario/mensual)
    - Institución (Udenar, Cesmag, Mariana, UCC, HUDN)
    - Medidor específico
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener indicadores de medidores eléctricos",
        description="Obtiene indicadores de consumo de medidores eléctricos filtrados por institución, rango de tiempo y medidor específico",
        parameters=[
            OpenApiParameter(
                name='time_range',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Rango de tiempo para los datos (daily/monthly)",
                enum=['daily', 'monthly'],
                default='daily'
            ),
            OpenApiParameter(
                name='institution_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="ID de la institución (requerido)",
                required=True
            ),
            OpenApiParameter(
                name='device_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="ID específico del medidor (opcional)"
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de inicio en formato YYYY-MM-DD"
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Fecha de fin en formato YYYY-MM-DD"
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "time_range": {"type": "string"},
                    "institution_id": {"type": "string"},
                    "institution_name": {"type": "string"},
                    "device_id": {"type": "string", "nullable": True},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "consumption_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "device_id": {"type": "integer"},
                                "device_name": {"type": "string"},
                                "institution_name": {"type": "string"},
                                "cumulative_active_power": {"type": "number"},
                                "total_active_power": {"type": "number"},
                                "peak_demand": {"type": "number"},
                                "avg_demand": {"type": "number"},
                                "measurement_count": {"type": "integer"},
                                "last_measurement_date": {"type": "string", "nullable": True},
                            }
                        }
                    },
                    "chart_data": {"type": "array", "items": {"type": "object"}},
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_consumption": {"type": "number"},
                            "avg_daily_consumption": {"type": "number"},
                            "peak_demand": {"type": "number"},
                            "total_devices": {"type": "integer"},
                            "active_devices": {"type": "integer"},
                            "days_processed": {"type": "integer"},
                        }
                    },
                }
            },
            400: {"description": "Parámetros inválidos"},
            404: {"description": "Institución no encontrada"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Medidores Eléctricos"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/electric-meters/
        
        Obtiene indicadores de consumo de medidores eléctricos filtrados por institución, 
        rango de tiempo y medidor específico.
        
        Parámetros de consulta:
        - time_range: 'daily' o 'monthly' (por defecto: 'daily')
        - institution_id: ID de la institución (requerido)
        - device_id: ID del medidor específico (opcional)
        - start_date: fecha de inicio (YYYY-MM-DD)
        - end_date: fecha de fin (YYYY-MM-DD)
        """
        try:
            # Obtener parámetros de consulta
            time_range = request.query_params.get('time_range', 'daily')
            institution_id = request.query_params.get('institution_id')
            device_id = request.query_params.get('device_id')
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            # Validar parámetros
            if time_range not in ['daily', 'monthly']:
                return Response(
                    {"detail": "time_range debe ser 'daily' o 'monthly'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not institution_id:
                return Response(
                    {"detail": "institution_id es requerido"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Procesar fechas
            if not start_date_str or not end_date_str:
                # Por defecto, último mes
                end_date = get_colombia_now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Obtener la institución
            try:
                institution = Institution.objects.get(id=institution_id)
            except Institution.DoesNotExist:
                return Response(
                    {"detail": "Institución no encontrada"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Construir filtros para datos locales
            filters = {
                'time_range': time_range,
                'date__range': (start_date, end_date),
                'institution': institution
            }

            if device_id:
                filters['device__scada_id'] = device_id

            # Obtener datos de consumo locales
            consumption_data = ElectricMeterConsumption.objects.filter(**filters).select_related(
                'device', 'institution'
            ).order_by('date')

            # Obtener datos de gráficos si es necesario
            chart_data = None
            if time_range == 'daily':
                chart_filters = {
                    'date__range': (start_date, end_date),
                    'institution': institution
                }
                if device_id:
                    chart_filters['device__scada_id'] = device_id

                chart_data = ElectricMeterChartData.objects.filter(**chart_filters).select_related(
                    'device', 'institution'
                ).order_by('date')

            # Formatear respuesta
            response_data = {
                'time_range': time_range,
                'institution_id': institution_id,
                'institution_name': institution.name,
                'device_id': device_id,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'consumption_data': [],
                'chart_data': [],
                'summary': {
                    'total_consumption': 0.0,
                    'avg_daily_consumption': 0.0,
                    'peak_demand': 0.0,
                    'total_devices': 0,
                    'active_devices': 0
                }
            }

            # Procesar datos de consumo
            total_consumption = 0.0
            peak_demand = 0.0
            devices_processed = set()

            for record in consumption_data:
                devices_processed.add(record.device_id)
                total_consumption += record.total_active_power
                peak_demand = max(peak_demand, record.peak_demand)

                response_data['consumption_data'].append({
                    'date': record.date.isoformat(),
                    'device_id': record.device_id,
                    'device_name': record.device.name,
                    'institution_name': record.institution.name,
                    'cumulative_active_power': record.cumulative_active_power,
                    'total_active_power': record.total_active_power,
                    'peak_demand': record.peak_demand,
                    'avg_demand': record.avg_demand,
                    'measurement_count': record.measurement_count,
                    'last_measurement_date': record.last_measurement_date.isoformat() if record.last_measurement_date else None
                })

            # Procesar datos de gráficos
            if chart_data:
                for record in chart_data:
                    response_data['chart_data'].append({
                        'date': record.date.isoformat(),
                        'device_id': record.device_id,
                        'device_name': record.device.name,
                        'institution_name': record.institution.name,
                        'hourly_consumption': record.hourly_consumption,
                        'daily_consumption': record.daily_consumption,
                        'peak_hour': record.peak_hour,
                        'peak_value': record.peak_value
                    })

            # Calcular resumen
            days_count = (end_date - start_date).days + 1
            response_data['summary'] = {
                'total_consumption': total_consumption,
                'avg_daily_consumption': total_consumption / days_count if days_count > 0 else 0.0,
                'peak_demand': peak_demand,
                'total_devices': len(devices_processed),
                'active_devices': len(devices_processed),
                'days_processed': days_count
            }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error en ElectricMeterIndicatorsView: {e}", exc_info=True)
            return Response(
                {"detail": f"Error interno del servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class InstitutionsListView(APIView):
    """
    Vista para obtener la lista de instituciones disponibles
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener lista de instituciones",
        description="Obtiene la lista de todas las instituciones disponibles en el sistema",
        responses={
            200: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "scada_id": {"type": "string"},
                    }
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Instituciones"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/institutions/
        
        Obtiene la lista de todas las instituciones disponibles en el sistema.
        """
        try:
            institutions = Institution.objects.all().values('id', 'name', 'scada_id')
            return Response(list(institutions))
        except Exception as e:
            logger.error(f"Error en InstitutionsListView: {e}", exc_info=True)
            return Response(
                {"detail": f"Error interno del servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ElectricMetersListView(APIView):
    """
    Vista para obtener la lista de medidores eléctricos por institución
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener lista de medidores eléctricos",
        description="Obtiene la lista de medidores eléctricos, opcionalmente filtrados por institución",
        parameters=[
            OpenApiParameter(
                name='institution_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="ID de la institución para filtrar medidores (opcional)"
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "institution_id": {"type": "integer", "nullable": True},
                    "devices": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "scada_id": {"type": "string"},
                                "name": {"type": "string"},
                                "institution_id": {"type": "string"},
                                "institution_name": {"type": "string"},
                                "status": {"type": "string"},
                                "is_active": {"type": "boolean"},
                                "description": {"type": "string"},
                                "location": {"type": "object"},
                            }
                        }
                    },
                    "total_count": {"type": "integer"},
                }
            },
            404: {"description": "Institución no encontrada"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Medidores Eléctricos"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/electric-meters/list/
        
        Obtiene la lista de medidores eléctricos, opcionalmente filtrados por institución.
        
        Parámetros de consulta:
        - institution_id: ID de la institución (opcional)
        """
        try:
            institution_id = request.query_params.get('institution_id')
            
            # Obtener medidores eléctricos directamente de la base de datos local
            try:
                # Obtener la categoría de medidores eléctricos
                electric_meter_category = DeviceCategory.objects.get(name='electricMeter')
                
                # Obtener todos los dispositivos de esta categoría
                local_devices = Device.objects.filter(
                    category=electric_meter_category,
                    is_active=True
                ).select_related('institution')
                
                logger.info(f"Dispositivos encontrados en BD local: {local_devices.count()}")
                
            except DeviceCategory.DoesNotExist:
                logger.error("Categoría 'electricMeter' no encontrada")
                return Response(
                    {"detail": "Categoría de medidores eléctricos no encontrada"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Error obteniendo dispositivos de BD local: {e}")
                return Response(
                    {"detail": f"Error obteniendo dispositivos: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Filtrar por institución si se especifica
            if institution_id:
                try:
                    institution = Institution.objects.get(id=institution_id)
                    local_devices = local_devices.filter(institution=institution)
                    logger.info(f"Dispositivos filtrados por institución {institution.name}: {local_devices.count()}")
                except Institution.DoesNotExist:
                    return Response(
                        {"detail": "Institución no encontrada"},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # Formatear respuesta
            devices_list = []
            for device in local_devices:
                devices_list.append({
                    'scada_id': device.scada_id,
                    'name': device.name,
                    'institution_id': device.institution.scada_id if device.institution else None,
                    'institution_name': device.institution.name if device.institution else 'Sin institución',
                    'status': device.status or 'unknown',
                    'is_active': device.is_active,
                    'description': device.name,  # Usar el nombre como descripción
                    'location': {}  # No tenemos datos de ubicación en el modelo local
                })

            logger.info(f"Respuesta formateada con {len(devices_list)} dispositivos")

            return Response({
                'institution_id': institution_id,
                'devices': devices_list,
                'total_count': len(devices_list)
            })

        except Exception as e:
            logger.error(f"Error en ElectricMetersListView: {e}", exc_info=True)
            return Response(
                {"detail": f"Error interno del servidor: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CalculateElectricMeterDataView(APIView):
    """
    Vista para ejecutar manualmente el cálculo de datos de medidores eléctricos
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Calcular datos de medidores eléctricos",
        description="Ejecuta manualmente el cálculo de datos de medidores eléctricos para un rango de tiempo específico. "
                   "Este endpoint inicia una tarea asíncrona que procesa los datos de consumo de energía "
                   "para los medidores eléctricos de la institución especificada.",
        request=ElectricMeterCalculationRequestSerializer,
        responses={
            200: ElectricMeterCalculationResponseSerializer,
            400: OpenApiResponse(
                description="Datos de entrada inválidos",
                examples=[
                    OpenApiExample(
                        "Error de validación",
                        value={
                            "detail": "Los datos proporcionados no son válidos",
                            "errors": {
                                "institution_id": ["Este campo es requerido."],
                                "start_date": ["Fecha de inicio debe ser anterior a fecha de fin."]
                            }
                        }
                    )
                ]
            ),
            500: OpenApiResponse(
                description="Error interno del servidor",
                examples=[
                    OpenApiExample(
                        "Error de cálculo",
                        value={
                            "detail": "Error al procesar los datos de medidores eléctricos",
                            "error": "No se pudieron obtener datos del servidor SCADA"
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Cálculo diario",
                value={
                    "time_range": "daily",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "institution_id": 1
                },
                description="Ejemplo de cálculo diario para una institución"
            ),
            OpenApiExample(
                "Cálculo mensual con medidor específico",
                value={
                    "time_range": "monthly",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "institution_id": 2,
                    "device_id": "3ccb420f-e6a0-4461-8dc6-e8568bd699f0"
                },
                description="Ejemplo de cálculo mensual para un medidor específico"
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/electric-meters/calculate/
        
        Ejecuta el cálculo de datos de medidores eléctricos.
        
        Headers requeridos:
        - Authorization: Token <token>
        - Content-Type: application/json
        
        Body requerido:
        - time_range: 'daily' o 'monthly'
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        - institution_id: integer
        - device_id: string (opcional)
        """
        try:
            # Validar datos de entrada
            serializer = ElectricMeterCalculationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "detail": "Los datos proporcionados no son válidos",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Ejecutar tarea de cálculo
            from .tasks import calculate_electric_meter_energy_consumption
            task = calculate_electric_meter_energy_consumption.delay(
                time_range=validated_data['time_range'],
                start_date_str=validated_data['start_date'].isoformat(),
                end_date_str=validated_data['end_date'].isoformat(),
                institution_id=validated_data['institution_id'],
                device_id=validated_data.get('device_id')
            )
            
            logger.info(f"Tarea de cálculo iniciada: {task.id} para institución {validated_data['institution_id']}")
            
            return Response({
                "success": True,
                "message": "Cálculo de datos de medidores eléctricos iniciado correctamente",
                "task_id": task.id,
                "processed_devices": 0,  # Se actualizará cuando termine la tarea
                "total_consumption": 0.0  # Se actualizará cuando termine la tarea
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en cálculo de medidores eléctricos: {str(e)}")
            return Response({
                "success": False,
                "detail": "Error al procesar los datos de medidores eléctricos",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TriggerElectricMeterCalculationView(APIView):
    """
    Vista para disparar el cálculo de datos de medidores eléctricos
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Disparar cálculo de datos de medidores eléctricos",
        description="Inicia el cálculo de datos de medidores eléctricos para los filtros especificados",
        request=ElectricMeterCalculationRequestSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "task_id": {"type": "string"},
                }
            },
            400: {"description": "Datos de entrada inválidos"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Medidores Eléctricos"]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/electric-meters/trigger-calculation/
        
        Dispara el cálculo de datos de medidores eléctricos.
        """
        try:
            # Validar datos de entrada
            serializer = ElectricMeterCalculationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "detail": "Los datos proporcionados no son válidos",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Ejecutar tarea de cálculo
            from .tasks import calculate_electric_meter_energy_consumption
            task = calculate_electric_meter_energy_consumption.delay(
                time_range=validated_data['time_range'],
                start_date_str=validated_data['start_date'].isoformat(),
                end_date_str=validated_data['end_date'].isoformat(),
                institution_id=validated_data['institution_id'],
                device_id=validated_data.get('device_id')
            )
            
            logger.info(f"Tarea de cálculo disparada: {task.id}")
            
            return Response({
                "success": True,
                "message": "Cálculo de datos iniciado correctamente",
                "task_id": task.id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error disparando cálculo de medidores eléctricos: {str(e)}")
            return Response({
                "success": False,
                "detail": "Error al iniciar el cálculo",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
# indicators/views.py
class ElectricMeterEnergyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API para datos de energía de medidores eléctricos
    """
    serializer_class = ElectricMeterEnergySerializer
    
    def get_queryset(self):
        queryset = ElectricMeterEnergyConsumption.objects.all()

        # Filtros
        time_range = self.request.query_params.get('time_range', 'daily')
        institution_id = self.request.query_params.get('institution_id')
        device_id = self.request.query_params.get('device_id')
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        if time_range:
            queryset = queryset.filter(time_range=time_range)
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        if device_id:
            # Aceptar tanto el id entero local como el scada_id (UUID/string)
            if str(device_id).isdigit():
                queryset = queryset.filter(device_id=int(device_id))
            else:
                queryset = queryset.filter(device__scada_id=device_id)
        # Parseo seguro de fechas (YYYY-MM-DD)
        from datetime import datetime
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date__lte=end_date)
            except ValueError:
                pass

        return queryset.order_by('date')

@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ElectricMeterIndicatorsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Vista para obtener indicadores eléctricos de medidores.
    """
    serializer_class = ElectricMeterIndicatorsSerializer
    permission_classes = [IsAuthenticated]
    # Contrato con el frontend: ElectricalDetails.js consume {'summary', 'results'} con
    # 'results' como la lista COMPLETA del rango pedido. La paginación global de DRF no
    # debe alterar ese shape; el payload se acota por rango de fechas (31 días por
    # defecto, máximo 366) en lugar de por páginas.
    pagination_class = None

    def get_queryset(self):
        # select_related evita el N+1 sobre device/institution al serializar.
        queryset = ElectricMeterIndicators.objects.select_related('device', 'institution').all()

        # Filtros
        institution_id = self.request.query_params.get('institution_id')
        device_id = self.request.query_params.get('device_id')
        time_range = self.request.query_params.get('time_range', 'daily')
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)

        if device_id:
            # Aceptar tanto el id entero local como el scada_id (UUID/string)
            if str(device_id).isdigit():
                queryset = queryset.filter(device_id=int(device_id))
            else:
                queryset = queryset.filter(device__scada_id=device_id)

        if time_range:
            queryset = queryset.filter(time_range=time_range)

        # La acción list SIEMPRE acota por rango de fechas (por defecto: últimos 31 días).
        # retrieve (detalle por pk) no se restringe por fecha para no romper accesos directos.
        if self.action == 'list':
            start_date, end_date, error = resolve_indicators_date_range(start_date_str, end_date_str)
            if error is None:
                queryset = queryset.filter(date__gte=start_date, date__lte=end_date)

        return queryset.order_by('-date', 'device__name')

    def list(self, request, *args, **kwargs):
        """
        Lista los indicadores eléctricos con opciones de filtrado.
        """
        # Validar el rango de fechas antes de consultar (400 si es inválido o excesivo).
        _, _, error = resolve_indicators_date_range(
            request.query_params.get('start_date'),
            request.query_params.get('end_date'),
        )
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset()

        # Agregar información de resumen
        summary = {
            'total_records': queryset.count(),
            'institutions': list(queryset.values('institution__name').distinct()),
            'devices': list(queryset.values('device__name').distinct()),
            'date_range': {
                'min_date': queryset.aggregate(Min('date'))['date__min'],
                'max_date': queryset.aggregate(Max('date'))['date__max']
            }
        }

        # Sin paginación (pagination_class = None): se conserva el contrato
        # {'summary', 'results'} que espera el frontend.
        serializer = self.get_serializer(queryset, many=True)
        response_data = {
            'summary': summary,
            'results': serializer.data
        }
        return Response(response_data)

# ========================= Vistas para Indicadores de Inversores =========================

@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
@extend_schema(
    tags=["Inversores"],
    description="Lista todos los indicadores de inversores con opciones de filtrado.",
    parameters=[
        OpenApiParameter("institution_id", int, OpenApiParameter.QUERY, description="ID de la institución"),
        OpenApiParameter("device_id", str, OpenApiParameter.QUERY, description="ID del inversor específico"),
        OpenApiParameter("time_range", str, OpenApiParameter.QUERY, description="Rango de tiempo: 'daily' o 'monthly'"),
        OpenApiParameter("start_date", str, OpenApiParameter.QUERY, description="Fecha de inicio (YYYY-MM-DD). Sin rango: últimos 31 días"),
        OpenApiParameter("end_date", str, OpenApiParameter.QUERY, description="Fecha de fin (YYYY-MM-DD). Rango máximo: 366 días"),
    ],
    responses={200: InverterIndicatorsSerializer(many=True)}
)
class InverterIndicatorsView(APIView):
    """
    Vista para obtener indicadores de inversores.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        GET /api/inverter-indicators/

        Lista los indicadores de inversores con opciones de filtrado.
        """
        try:
            # Obtener parámetros de filtrado
            institution_id = request.query_params.get('institution_id')
            device_id = request.query_params.get('device_id')
            time_range = request.query_params.get('time_range', 'daily')
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            # Validar parámetros requeridos
            if not institution_id:
                return Response({
                    "detail": "El parámetro 'institution_id' es requerido"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Rango de fechas efectivo: últimos 31 días por defecto, máximo 366 días.
            start_date, end_date, error = resolve_indicators_date_range(start_date_str, end_date_str)
            if error:
                return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

            # Construir queryset base (select_related evita el N+1 sobre device/institution).
            from .models import InverterIndicators
            queryset = InverterIndicators.objects.select_related('device', 'institution').all()

            # Aplicar filtros
            if institution_id:
                queryset = queryset.filter(institution_id=institution_id)

            if device_id:
                # Aceptar tanto el id entero local como el scada_id (UUID/string)
                if str(device_id).isdigit():
                    queryset = queryset.filter(device_id=int(device_id))
                else:
                    queryset = queryset.filter(device__scada_id=device_id)

            if time_range:
                queryset = queryset.filter(time_range=time_range)

            queryset = queryset.filter(date__gte=start_date, date__lte=end_date)

            # Ordenar por fecha descendente y nombre del dispositivo
            queryset = queryset.order_by('-date', 'device__name')
            
            # Agregar información de resumen
            summary = {
                'total_records': queryset.count(),
                'institutions': list(queryset.values('institution__name').distinct()),
                'devices': list(queryset.values('device__name').distinct()),
                'date_range': {
                    'min_date': queryset.aggregate(Min('date'))['date__min'],
                    'max_date': queryset.aggregate(Max('date'))['date__max']
                }
            }
            
            # Serializar datos
            from .serializers import InverterIndicatorsSerializer
            serializer = InverterIndicatorsSerializer(queryset, many=True)
            
            response_data = {
                'summary': summary,
                'results': serializer.data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo indicadores de inversores: {str(e)}")
            return Response({
                "detail": "Error al obtener indicadores de inversores",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Inversores"],
    description="Lista todos los datos de gráficos de inversores con opciones de filtrado.",
    parameters=[
        OpenApiParameter("institution_id", int, OpenApiParameter.QUERY, description="ID de la institución"),
        OpenApiParameter("device_id", str, OpenApiParameter.QUERY, description="ID del inversor específico"),
        OpenApiParameter("start_date", str, OpenApiParameter.QUERY, description="Fecha de inicio (YYYY-MM-DD)"),
        OpenApiParameter("end_date", str, OpenApiParameter.QUERY, description="Fecha de fin (YYYY-MM-DD)"),
    ],
    responses={200: InverterChartDataSerializer(many=True)}
)
class InverterChartDataView(APIView):
    """
    Vista para obtener datos de gráficos de inversores.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """
        GET /api/inverter-chart-data/
        
        Lista los datos de gráficos de inversores con opciones de filtrado.
        """
        try:
            # Obtener parámetros de filtrado
            institution_id = request.query_params.get('institution_id')
            device_id = request.query_params.get('device_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            # Validar parámetros requeridos
            if not institution_id:
                return Response({
                    "detail": "El parámetro 'institution_id' es requerido"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Construir queryset base
            from .models import InverterChartData
            queryset = InverterChartData.objects.all()
            
            # Aplicar filtros
            if institution_id:
                queryset = queryset.filter(institution_id=institution_id)
            
            if device_id:
                # Aceptar tanto el id entero local como el scada_id (UUID/string)
                if str(device_id).isdigit():
                    queryset = queryset.filter(device_id=int(device_id))
                else:
                    queryset = queryset.filter(device__scada_id=device_id)
            
            if start_date:
                queryset = queryset.filter(date__gte=start_date)
            
            if end_date:
                queryset = queryset.filter(date__lte=end_date)
            
            # Ordenar por fecha descendente y nombre del dispositivo
            queryset = queryset.order_by('-date', 'device__name')
            
            # Serializar datos
            from .serializers import InverterChartDataSerializer
            serializer = InverterChartDataSerializer(queryset, many=True)
            
            response_data = {
                'total_records': queryset.count(),
                'results': serializer.data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de gráficos de inversores: {str(e)}")
            return Response({
                "detail": "Error al obtener datos de gráficos de inversores",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Inversores"],
    description="Ejecuta el cálculo de indicadores de inversores.",
    request=InverterCalculationRequestSerializer,
    responses={
        200: InverterCalculationResponseSerializer,
        400: {"description": "Datos de entrada inválidos"},
        500: {"description": "Error interno del servidor"},
    }
)
class CalculateInverterDataView(APIView):
    """
    Vista para ejecutar el cálculo de indicadores de inversores.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        POST /api/inverters/calculate/
        
        Ejecuta el cálculo de indicadores de inversores.
        
        Headers requeridos:
        - Authorization: Token <token>
        - Content-Type: application/json
        
        Body requerido:
        - time_range: 'daily' o 'monthly'
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        - institution_id: integer
        - device_id: string (opcional)
        """
        try:
            # Validar datos de entrada
            from .serializers import InverterCalculationRequestSerializer
            serializer = InverterCalculationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "detail": "Los datos proporcionados no son válidos",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Ejecutar tarea de cálculo
            from .tasks import calculate_inverter_data
            task = calculate_inverter_data.delay(
                time_range=validated_data['time_range'],
                start_date_str=validated_data['start_date'].isoformat(),
                end_date_str=validated_data['end_date'].isoformat(),
                institution_id=validated_data['institution_id'],
                device_id=validated_data.get('device_id')
            )
            
            logger.info(f"Tarea de cálculo de inversores iniciada: {task.id} para institución {validated_data['institution_id']}")
            
            return Response({
                "success": True,
                "message": "Cálculo de indicadores de inversores iniciado correctamente",
                "task_id": task.id,
                "processed_records": 0,  # Se actualizará cuando termine la tarea
                "estimated_completion_time": "Variable según la cantidad de datos"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en cálculo de indicadores de inversores: {str(e)}")
            return Response({
                "success": False,
                "detail": "Error al procesar los indicadores de inversores",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Medidores Eléctricos"],
    description="Ejecuta el cálculo de indicadores eléctricos.",
    request=InverterCalculationRequestSerializer,  # Reutilizamos el mismo serializer
    responses={
        200: InverterCalculationResponseSerializer,
        400: {"description": "Datos de entrada inválidos"},
        500: {"description": "Error interno del servidor"},
    }
)
class CalculateElectricalDataView(APIView):
    """
    Vista para ejecutar el cálculo de indicadores eléctricos.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        POST /api/electric-meters/calculate/
        
        Ejecuta el cálculo de indicadores eléctricos.
        
        Headers requeridos:
        - Authorization: Token <token>
        - Content-Type: application/json
        
        Body requerido:
        - time_range: 'daily' o 'monthly'
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        - institution_id: integer
        - device_id: string (opcional)
        """
        try:
            # Validar datos de entrada
            from .serializers import InverterCalculationRequestSerializer
            serializer = InverterCalculationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "detail": "Los datos proporcionados no son válidos",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            
            # Ejecutar tarea de cálculo
            from .tasks import calculate_electrical_data
            task = calculate_electrical_data.delay(
                time_range=validated_data['time_range'],
                start_date_str=validated_data['start_date'].isoformat(),
                end_date_str=validated_data['end_date'].isoformat(),
                institution_id=validated_data['institution_id'],
                device_id=validated_data.get('device_id')
            )
            
            logger.info(f"Tarea de cálculo eléctrico iniciada: {task.id} para institución {validated_data['institution_id']}")
            
            return Response({
                "success": True,
                "message": "Cálculo de indicadores eléctricos iniciado correctamente",
                "task_id": task.id,
                "processed_records": 0,  # Se actualizará cuando termine la tarea
                "estimated_completion_time": "Variable según la cantidad de datos"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en cálculo de indicadores eléctricos: {str(e)}")
            return Response({
                "success": False,
                "detail": "Error al procesar los indicadores eléctricos",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Inversores"],
    description="Lista inversores filtrados por institución.",
    parameters=[
        OpenApiParameter("institution_id", int, OpenApiParameter.QUERY, description="ID de la institución"),
    ],
    responses={200: {"type": "object", "properties": {"devices": {"type": "array"}, "total_count": {"type": "integer"}}}}
)
class InvertersListView(APIView):
    """
    Vista para listar inversores filtrados por institución.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """
        GET /api/inverters/list/
        
        Lista inversores filtrados por institución.
        """
        try:
            institution_id = request.query_params.get('institution_id')
            
            if not institution_id:
                return Response({
                    "detail": "El parámetro 'institution_id' es requerido"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtener inversores de la institución
            from scada_proxy.models import Device
            inverters = Device.objects.filter(
                category__name='inverter',
                institution_id=institution_id,
                is_active=True
            ).select_related('institution')
            
            # Serializar datos
            from scada_proxy.serializers import DeviceSerializer
            serializer = DeviceSerializer(inverters, many=True)
            
            response_data = {
                "devices": serializer.data,
                "total_count": inverters.count()
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error obteniendo lista de inversores: {str(e)}")
            return Response(
                {"detail": "Error al obtener lista de inversores",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vistas para estaciones meteorológicas
@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class WeatherStationIndicatorsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener indicadores de estaciones meteorológicas",
        description="Obtiene los indicadores meteorológicos calculados para estaciones meteorológicas",
        parameters=[
            OpenApiParameter(name='time_range', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='Rango de tiempo: daily o monthly', required=False),
            OpenApiParameter(name='institution_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='ID de la institución', required=False),
            OpenApiParameter(name='device_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='ID específico de la estación meteorológica', required=False),
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, 
                           description='Fecha de inicio (YYYY-MM-DD)', required=False),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, 
                           description='Fecha de fin (YYYY-MM-DD)', required=False),
        ],
        responses={
            200: WeatherStationIndicatorsSerializer(many=True),
            400: {"description": "Parámetros inválidos"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Estaciones Meteorológicas"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/weather-station-indicators/
        
        Obtiene los indicadores meteorológicos calculados para estaciones meteorológicas.
        """
        try:
            # Obtener parámetros de consulta
            time_range = request.query_params.get('time_range', 'daily')
            institution_id = request.query_params.get('institution_id')
            device_id = request.query_params.get('device_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            # Validar parámetros
            if time_range not in ['daily', 'monthly']:
                return Response(
                    {"detail": "time_range debe ser 'daily' o 'monthly'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Construir filtros
            filters = Q(time_range=time_range)
            
            if institution_id:
                try:
                    institution_id = int(institution_id)
                    filters &= Q(institution_id=institution_id)
                except ValueError:
                    return Response(
                        {"detail": "institution_id debe ser un número entero válido"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if device_id:
                filters &= Q(device_id=device_id)
            
            if start_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    filters &= Q(date__gte=start_date)
                except ValueError:
                    return Response(
                        {"detail": "start_date debe estar en formato YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    filters &= Q(date__lte=end_date)
                except ValueError:
                    return Response(
                        {"detail": "end_date debe estar en formato YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Obtener indicadores con select_related para optimizar consultas
            indicators = WeatherStationIndicators.objects.filter(filters).select_related(
                'device', 'institution'
            ).order_by('-date')
            
            # Serializar y devolver resultados
            serializer = WeatherStationIndicatorsSerializer(indicators, many=True)
            
            return Response({
                'count': indicators.count(),
                'results': serializer.data,
                'time_range': time_range,
                'filters_applied': {
                    'institution_id': institution_id,
                    'device_id': device_id,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            })

        except Exception as e:
            logger.error(f"Error obteniendo indicadores meteorológicos: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class WeatherStationChartDataView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener datos de gráficos de estaciones meteorológicas",
        description="Obtiene los datos de gráficos meteorológicos para visualización",
        parameters=[
            OpenApiParameter(name='time_range', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='Rango de tiempo: daily o monthly', required=False),
            OpenApiParameter(name='institution_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='ID de la institución', required=False),
            OpenApiParameter(name='device_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='ID específico de la estación meteorológica', required=False),
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, 
                           description='Fecha de inicio (YYYY-MM-DD)', required=False),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, 
                           description='Fecha de fin (YYYY-MM-DD)', required=False),
        ],
        responses={
            200: WeatherStationChartDataSerializer(many=True),
            400: {"description": "Parámetros inválidos"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Estaciones Meteorológicas"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/weather-station-chart-data/
        
        Obtiene los datos de gráficos meteorológicos para visualización.
        """
        try:
            # Obtener parámetros de consulta
            time_range = request.query_params.get('time_range', 'daily')
            institution_id = request.query_params.get('institution_id')
            device_id = request.query_params.get('device_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            # Validar parámetros
            if time_range not in ['daily', 'monthly']:
                return Response(
                    {"detail": "time_range debe ser 'daily' o 'monthly'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Construir filtros
            filters = Q()
            
            if institution_id:
                try:
                    institution_id = int(institution_id)
                    filters &= Q(institution_id=institution_id)
                except ValueError:
                    return Response(
                        {"detail": "institution_id debe ser un número entero válido"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if device_id:
                filters &= Q(device_id=device_id)
            
            if start_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    filters &= Q(date__gte=start_date)
                except ValueError:
                    return Response(
                        {"detail": "start_date debe estar en formato YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if end_date:
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    filters &= Q(date__lte=end_date)
                except ValueError:
                    return Response(
                        {"detail": "end_date debe estar en formato YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Obtener datos de gráficos con select_related para optimizar consultas
            chart_data = WeatherStationChartData.objects.filter(filters).select_related(
                'device', 'institution'
            ).order_by('-date')
            
            # Serializar y devolver resultados
            serializer = WeatherStationChartDataSerializer(chart_data, many=True)
            
            return Response({
                'count': chart_data.count(),
                'results': serializer.data,
                'time_range': time_range,
                'filters_applied': {
                    'institution_id': institution_id,
                    'device_id': device_id,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            })

        except Exception as e:
            logger.error(f"Error obteniendo datos de gráficos meteorológicos: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CalculateWeatherStationDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get_scada_token(self):
        try:
            return scada_client.get_token()
        except EnvironmentError as e:
            logger.error(f"SCADA configuration error: {e}")
            return Response({"detail": "SCADA server configuration error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting SCADA token: {e}")
            return Response({"detail": "No se pudo autenticar con la API SCADA. Revise las credenciales."}, status=status.HTTP_502_BAD_GATEWAY)

    @extend_schema(
        summary="Calcular indicadores meteorológicos",
        description="Calcula los indicadores meteorológicos para estaciones meteorológicas",
        request=WeatherStationCalculationRequestSerializer,
        responses={
            200: WeatherStationCalculationResponseSerializer,
            400: {"description": "Parámetros inválidos"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Estaciones Meteorológicas"]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/weather-stations/calculate/
        
        Calcula los indicadores meteorológicos para estaciones meteorológicas.
        """
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token

        try:
            # Validar datos de entrada
            serializer = WeatherStationCalculationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            data = serializer.validated_data
            
            # Ejecutar tarea asíncrona
            from .tasks import calculate_weather_station_indicators
            
            task = calculate_weather_station_indicators.delay(
                time_range=data['time_range'],
                start_date=data['start_date'].isoformat(),
                end_date=data['end_date'].isoformat(),
                institution_id=data['institution_id'],
                device_id=data.get('device_id', '')
            )
            
            # Calcular tiempo estimado de finalización
            estimated_time = "5-10 minutos" if data['time_range'] == 'daily' else "15-20 minutos"
            
            return Response({
                'success': True,
                'message': 'Cálculo de indicadores meteorológicos iniciado exitosamente',
                'task_id': task.id,
                'time_range': data['time_range'],
                'start_date': data['start_date'],
                'end_date': data['end_date'],
                'institution_id': data['institution_id'],
                'device_id': data.get('device_id'),
                'processed_records': 0,  # Se actualizará cuando la tarea termine
                'estimated_completion_time': estimated_time
            })

        except Exception as e:
            logger.error(f"Error iniciando cálculo de indicadores meteorológicos: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WeatherStationsListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Listar estaciones meteorológicas",
        description="Obtiene la lista de estaciones meteorológicas disponibles",
        parameters=[
            OpenApiParameter(name='institution_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='ID de la institución para filtrar', required=False),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "institution": {"type": "object"},
                                "is_active": {"type": "boolean"}
                            }
                        }
                    }
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Estaciones Meteorológicas"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/weather-stations/list/
        
        Obtiene la lista de estaciones meteorológicas disponibles.
        """
        try:
            # Obtener parámetros de consulta
            institution_id = request.query_params.get('institution_id')

            # Construir filtros
            filters = Q(category__name='weatherStation', is_active=True)
            
            if institution_id:
                try:
                    institution_id = int(institution_id)
                    filters &= Q(institution_id=institution_id)
                except ValueError:
                    return Response(
                        {"detail": "institution_id debe ser un número entero válido"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Obtener estaciones meteorológicas con select_related para optimizar consultas
            weather_stations = Device.objects.filter(filters).select_related(
                'institution', 'category'
            ).order_by('institution__name', 'name')
            
            # Preparar respuesta
            results = []
            for station in weather_stations:
                results.append({
                    'id': station.id,
                    'name': station.name,
                    'institution': {
                        'id': station.institution.id,
                        'name': station.institution.name
                    },
                    'is_active': station.is_active,
                    'scada_id': station.scada_id,
                    'status': station.status
                })
            
            return Response({
                'count': len(results),
                'results': results
            })

        except Exception as e:
            logger.error(f"Error obteniendo lista de estaciones meteorológicas: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# =========================
# VISTAS PARA GENERACIÓN DE REPORTES
# =========================

class GenerateReportView(APIView):
    """
    Vista para generar reportes en diferentes formatos
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Generar reporte",
        description="Genera un reporte en el formato especificado basado en los parámetros proporcionados",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "institution_id": {"type": "integer", "description": "ID de la institución"},
                    "category": {"type": "string", "description": "Categoría de dispositivo (electricMeter, inverter, weatherStation)"},
                    "devices": {"type": "array", "items": {"type": "string"}, "description": "IDs de dispositivos seleccionados"},
                    "report_type": {"type": "string", "description": "Tipo de reporte a generar"},
                    "time_range": {"type": "string", "description": "Rango de tiempo (daily, monthly)"},
                    "start_date": {"type": "string", "format": "date", "description": "Fecha de inicio"},
                    "end_date": {"type": "string", "format": "date", "description": "Fecha de fin"},
                    "format": {"type": "string", "description": "Formato de exportación (CSV, PDF, Excel)"}
                },
                "required": ["institution_id", "category", "devices", "report_type", "time_range", "start_date", "end_date", "format"]
            }
        },
        responses={
            200: {"description": "Reporte generado exitosamente"},
            400: {"description": "Parámetros inválidos"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Reportes"]
    )
    def post(self, request, *args, **kwargs):
        """
        POST /api/reports/generate/
        
        Genera un reporte en el formato especificado.
        """
        try:
            # Validar datos de entrada
            data = request.data
            required_fields = ['institution_id', 'category', 'devices', 'report_type', 'time_range', 'start_date', 'end_date', 'format']
            
            for field in required_fields:
                if field not in data:
                    return Response(
                        {"detail": f"Campo requerido: {field}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Validar formato de fecha
            try:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"detail": "Formato de fecha inválido. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validar que la fecha de inicio no sea posterior a la de fin
            if start_date > end_date:
                return Response(
                    {"detail": "La fecha de inicio no puede ser posterior a la fecha de fin"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validar formato de exportación
            valid_formats = ['CSV', 'PDF', 'Excel']
            if data['format'] not in valid_formats:
                return Response(
                    {"detail": f"Formato no válido. Formatos disponibles: {', '.join(valid_formats)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Ejecutar tarea asíncrona para generar reporte
            from .tasks import generate_report
            
            task = generate_report.delay(
                institution_id=data['institution_id'],
                category=data['category'],
                devices=data['devices'],
                report_type=data['report_type'],
                time_range=data['time_range'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                format=data['format'],
                user_id=request.user.id
            )
            
            # Estimación real: promedio de duración de los últimos 5 reportes
            # completados de la misma categoría; fallback al literal si no hay.
            estimated = '2-5 minutos'
            from .models import GeneratedReport
            recent = list(GeneratedReport.objects.filter(
                category=data['category'], status='SUCCESS', completed_at__isnull=False,
            ).order_by('-completed_at').values_list('created_at', 'completed_at')[:5])
            if recent:
                avg_s = sum((b - a).total_seconds() for a, b in recent) / len(recent)
                estimated = f'~{max(int(round(avg_s / 60)), 1)} minutos' if avg_s >= 45 else '~1 minuto'

            return Response({
                'success': True,
                'message': 'Generación de reporte iniciada exitosamente',
                'task_id': task.id,
                'estimated_completion_time': estimated
            })

        except Exception as e:
            logger.error(f"Error iniciando generación de reporte: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReportStatusView(APIView):
    """
    Vista para consultar el estado de generación de reportes
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Consultar estado de reporte",
        description="Consulta el estado de generación de un reporte específico",
        parameters=[
            OpenApiParameter(name='task_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='ID de la tarea de generación', required=True),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "progress": {"type": "integer"},
                    "download_url": {"type": "string", "nullable": True},
                    "error": {"type": "string", "nullable": True}
                }
            },
            404: {"description": "Tarea no encontrada"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Reportes"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/reports/status/
        
        Consulta el estado de generación de un reporte.
        """
        try:
            task_id = request.query_params.get('task_id')
            if not task_id:
                return Response(
                    {"detail": "task_id es requerido"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Primero intentar consultar estado desde la base de datos.
            # Se filtra por user_id para no filtrar estado/URL de reportes ajenos (IDOR).
            from .tasks import get_report_status
            status_info = get_report_status(task_id, user_id=request.user.id)
            
            if status_info:
                return Response(status_info)
            
                        # Si no existe en la base de datos, consultar estado de Celery
            try:
                from celery.result import AsyncResult
                from core.celery import app
                
                task_result = AsyncResult(task_id, app=app)
                
                # Log para debugging
                logger.info(f"Estado de Celery para task_id {task_id}: {task_result.state}")
                
                if task_result.state == 'PENDING':
                    return Response({
                        'task_id': task_id,
                        'status': 'pending',
                        'progress': 0,
                        'download_url': None,
                        'error': None
                    })
                elif task_result.state == 'STARTED':
                    return Response({
                        'task_id': task_id,
                        'status': 'processing',
                        'progress': 10,
                        'download_url': None,
                        'error': None
                    })
                elif task_result.state == 'PROGRESS':
                    meta = task_result.info or {}
                    progress = meta.get('current', 0)
                    logger.info(f"Progreso de tarea {task_id}: {progress}%")
                    return Response({
                        'task_id': task_id,
                        'status': 'processing',
                        'progress': progress,
                        'download_url': None,
                        'error': None
                    })
                elif task_result.state == 'SUCCESS':
                    logger.info(f"Tarea {task_id} completada exitosamente")
                    return Response({
                        'task_id': task_id,
                        'status': 'completed',
                        'progress': 100,
                        'download_url': f"/api/reports/download/?task_id={task_id}",
                        'error': None
                    })
                elif task_result.state == 'FAILURE':
                    error_msg = str(task_result.info) if task_result.info else "Error desconocido"
                    logger.error(f"Tarea {task_id} falló: {error_msg}")
                    return Response({
                        'task_id': task_id,
                        'status': 'failed',
                        'progress': 0,
                        'download_url': None,
                        'error': error_msg
                    })
                else:
                    logger.warning(f"Estado desconocido de Celery para tarea {task_id}: {task_result.state}")
                    return Response({
                        'task_id': task_id,
                        'status': 'pending',
                        'progress': 0,
                        'download_url': None,
                        'error': None
                    })
                    
            except Exception as celery_error:
                logger.error(f"Error consultando estado de Celery para tarea {task_id}: {str(celery_error)}")
                # Si no se puede consultar Celery, devolver estado pendiente
                return Response({
                    'task_id': task_id,
                    'status': 'pending',
                    'progress': 0,
                    'download_url': None,
                    'error': None
                })

        except Exception as e:
            logger.error(f"Error consultando estado de reporte: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DownloadReportView(APIView):
    """
    Vista para descargar reportes generados
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Descargar reporte",
        description="Descarga un reporte generado previamente",
        parameters=[
            OpenApiParameter(name='task_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='ID de la tarea de generación', required=True),
        ],
        responses={
            200: {"description": "Archivo del reporte"},
            404: {"description": "Reporte no encontrado"},
            500: {"description": "Error interno del servidor"},
        },
        tags=["Reportes"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/reports/download/
        
        Descarga un reporte generado.
        """
        try:
            task_id = request.query_params.get('task_id')
            if not task_id:
                return Response(
                    {"detail": "task_id es requerido"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Obtener información del reporte.
            # Se filtra por user_id para impedir descargar reportes de otro usuario (IDOR).
            from .tasks import get_report_file
            report_file = get_report_file(task_id, user_id=request.user.id)
            
            if not report_file:
                return Response(
                    {"detail": "Reporte no encontrado o no completado"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Retornar archivo para descarga
            from django.http import FileResponse
            import os
            
            file_path = report_file['file_path']
            if not os.path.exists(file_path):
                return Response(
                    {"detail": "Archivo no encontrado en el servidor"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Determinar tipo MIME
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = 'application/octet-stream'

            # Crear respuesta de archivo
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=mime_type
            )
            
            # Configurar headers para descarga
            filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response

        except Exception as e:
            logger.error(f"Error descargando reporte: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteReportView(APIView):
    """
    Vista para eliminar un reporte generado. Endpoint que el frontend
    (ExportReports.js) ya consumía (DELETE /api/reports/delete/) pero que no existía
    en el backend, provocando 404.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Eliminar reporte",
        description="Elimina un reporte generado por el usuario autenticado (incluye su archivo).",
        parameters=[
            OpenApiParameter(name='task_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                             description='ID de la tarea de generación del reporte', required=True),
        ],
        responses={
            200: {"description": "Reporte eliminado"},
            400: {"description": "task_id requerido"},
            404: {"description": "Reporte no encontrado"},
        },
        tags=["Reportes"]
    )
    def delete(self, request, *args, **kwargs):
        """DELETE /api/reports/delete/?task_id=..."""
        task_id = request.query_params.get('task_id') or request.data.get('task_id')
        if not task_id:
            return Response({"detail": "task_id es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        from .models import GeneratedReport
        # Solo se puede borrar un reporte PROPIO (filtrado por user_id evita IDOR).
        report = GeneratedReport.objects.filter(task_id=task_id, user_id=request.user.id).first()
        if not report:
            return Response({"detail": "Reporte no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        # Borrar el archivo físico si existe.
        import os
        if report.file_path and os.path.isfile(report.file_path):
            try:
                os.remove(report.file_path)
            except OSError:
                logger.warning("No se pudo eliminar el archivo del reporte %s", task_id)

        report.delete()
        return Response({"detail": "Reporte eliminado exitosamente"}, status=status.HTTP_200_OK)


class ReportHistoryView(APIView):
    """
    Vista para obtener el historial de reportes generados
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Historial de reportes",
        description="Obtiene el historial de reportes generados por el usuario",
        parameters=[
            OpenApiParameter(name='institution_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='ID de la institución para filtrar', required=False),
            OpenApiParameter(name='category', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, 
                           description='Categoría de dispositivo para filtrar', required=False),
            OpenApiParameter(name='page', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='Número de página (por defecto: 1)', required=False),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY, 
                           description='Tamaño de página (por defecto: 5, máximo: 100)', required=False),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Total de reportes disponibles"},
                    "total_pages": {"type": "integer", "description": "Total de páginas disponibles"},
                    "current_page": {"type": "integer", "description": "Página actual"},
                    "page_size": {"type": "integer", "description": "Tamaño de página actual"},
                    "next": {"type": "integer", "nullable": True, "description": "Número de la siguiente página"},
                    "previous": {"type": "integer", "nullable": True, "description": "Número de la página anterior"},
                    "has_next": {"type": "boolean", "description": "Indica si hay siguiente página"},
                    "has_previous": {"type": "boolean", "description": "Indica si hay página anterior"},
                    "start_index": {"type": "integer", "description": "Índice del primer elemento en la página actual"},
                    "end_index": {"type": "integer", "description": "Índice del último elemento en la página actual"},
                    "results": {
                        "type": "array",
                        "description": "Lista de reportes en la página actual",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "ID único del reporte"},
                                "report_type": {"type": "string", "description": "Tipo de reporte generado"},
                                "category": {"type": "string", "description": "Categoría de dispositivo"},
                                "institution_name": {"type": "string", "description": "Nombre de la institución"},
                                "devices_count": {"type": "integer", "description": "Número de dispositivos incluidos"},
                                "time_range": {"type": "string", "description": "Rango de tiempo del reporte"},
                                "start_date": {"type": "string", "description": "Fecha de inicio"},
                                "end_date": {"type": "string", "description": "Fecha de fin"},
                                "format": {"type": "string", "description": "Formato del archivo generado"},
                                "status": {"type": "string", "description": "Estado del reporte"},
                                "file_size": {"type": "string", "description": "Tamaño del archivo"},
                                "record_count": {"type": "integer", "description": "Número de registros en el reporte"},
                                "created_at": {"type": "string", "description": "Fecha de creación"},
                                "download_url": {"type": "string", "nullable": True, "description": "URL para descargar el reporte"}
                            }
                        }
                    }
                }
            },
            500: {"description": "Error interno del servidor"},
        },
        tags=["Reportes"]
    )
    def get(self, request, *args, **kwargs):
        """
        GET /api/reports/history/
        
        Obtiene el historial de reportes generados.
        """
        try:
            # Obtener parámetros de consulta
            institution_id = request.query_params.get('institution_id')
            category = request.query_params.get('category')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 5))  # Cambiado a 5 registros por página

            # Construir filtros
            filters = Q(user_id=request.user.id)
            
            if institution_id:
                filters &= Q(institution_id=institution_id)
            
            if category:
                filters &= Q(category=category)

            # Obtener reportes del usuario
            from .models import GeneratedReport
            
            reports = GeneratedReport.objects.filter(filters).order_by('-created_at')
            
            # Paginación mejorada
            from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
            
            # Validar parámetros de paginación
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 5
            elif page_size > 100:  # Límite máximo para evitar sobrecarga
                page_size = 100
            
            paginator = Paginator(reports, page_size)
            
            try:
                page_obj = paginator.get_page(page)
            except (EmptyPage, PageNotAnInteger):
                # Si la página no es válida, ir a la primera página
                page_obj = paginator.get_page(1)
                page = 1
            
            # Serializar resultados
            results = []
            for report in page_obj:
                results.append({
                    'id': report.task_id,
                    'report_type': report.report_type,
                    'category': report.category,
                    'institution_name': report.institution_name,
                    'institution_id': report.institution_id,
                    'devices': report.devices or [],
                    'devices_count': len(report.devices) if report.devices else 0,
                    'time_range': report.time_range,
                    'start_date': report.start_date.isoformat(),
                    'end_date': report.end_date.isoformat(),
                    'format': report.format,
                    'status': report.status,
                    'file_size': report.file_size,
                    'record_count': report.record_count,
                    'created_at': report.created_at.isoformat(),
                    'download_url': f"/api/reports/download/?task_id={report.task_id}" if report.status == 'completed' else None
                })
            
            # Información de paginación mejorada
            pagination_info = {
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page,
                'page_size': page_size,
                'next': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index(),
                'results': results
            }
            
            return Response(pagination_info)

        except Exception as e:
            logger.error(f"Error obteniendo historial de reportes: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )