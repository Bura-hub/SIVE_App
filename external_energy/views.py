from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.permissions import IsSuperUser
from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# TTL de caché para los endpoints que sirven series de XM. Los datos de XM son DIARIOS
# (no cambian intra-hora), así que 1 hora de caché es seguro y evita golpear la API de XM
# en cada request. Nota: la respuesta cacheada es un agregado del mercado colombiano
# compartido entre todos los usuarios (no contiene datos sensibles ni por-usuario), por lo
# que compartir la entrada de caché entre usuarios autenticados es aceptable.
XM_CACHE_TTL = 60 * 60

from .models import (
    EnergyPrice,
    EnergySavings,
    EnergyPriceForecast,
    EnergyMarketData,
    EnergyAlert
)
from .serializers import (
    ExternalEnergySummarySerializer,
    EnergySavingsSummarySerializer
)
from .services import (
    XMEnergyService
)

logger = logging.getLogger(__name__)


def _is_valid_number(value):
    """Indica si `value` es un número utilizable para estadísticas.

    Descarta None y NaN, pero CONSERVA los ceros: una demanda/generación/importación/
    exportación de 0 es un dato real y no debe excluirse de los agregados.
    """
    if value is None:
        return False
    if isinstance(value, float) and value != value:  # NaN
        return False
    return True


@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Precios de energía del mercado (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def energy_prices(request):
    """
    Obtiene datos de precios de energía para el rango especificado
    """
    try:
        range_param = request.GET.get('range', 'month')
        
        # Calcular fechas según el rango
        end_date = timezone.now().date()
        if range_param == 'week':
            start_date = end_date - timedelta(days=7)
        elif range_param == 'month':
            start_date = end_date - timedelta(days=30)
        elif range_param == 'quarter':
            start_date = end_date - timedelta(days=90)
        elif range_param == 'year':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Obtener precios del período
        prices = EnergyPrice.objects.filter(
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if not prices.exists():
            # Si no hay datos, intentar obtener de fuentes externas (no fallar si XM no está disponible)
            try:
                xm_service = XMEnergyService()
                prices_data = xm_service.fetch_energy_prices(start_date, end_date)
                
                # Los precios vienen agregados a nivel diario desde el servicio (una entrada
                # por fecha), por lo que no hay 24 filas con la misma fecha. Se usa
                # update_or_create para no depender del IntegrityError del `unique` de la fecha.
                for price_data in prices_data:
                    try:
                        if isinstance(price_data['date'], str):
                            price_date = datetime.strptime(price_data['date'], '%Y-%m-%d').date()
                        else:
                            price_date = price_data['date']

                        EnergyPrice.objects.update_or_create(
                            date=price_date,
                            defaults={
                                'price_per_kwh': price_data['price'],
                                'source': 'XM',
                                'region': 'Colombia',
                            },
                        )
                    except Exception as e:
                        logger.warning(f"Error creando registro de precio: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"No se pudieron obtener precios de XM (se devuelven datos vacíos): {str(e)}")
            
            prices = EnergyPrice.objects.filter(
                date__range=[start_date, end_date]
            ).order_by('date')
        
        # Calcular estadísticas
        price_values = [float(p.price_per_kwh) for p in prices]
        
        if price_values:
            average_price = sum(price_values) / len(price_values)
            max_price = max(price_values)
            min_price = min(price_values)
            
            # Calcular variación
            if len(price_values) > 1:
                first_price = price_values[0]
                last_price = price_values[-1]
                if first_price > 0:
                    price_variation = ((last_price - first_price) / first_price) * 100
                else:
                    price_variation = 0
            else:
                price_variation = 0
            
            # Determinar tendencia
            if price_variation > 2:
                price_trend = 'increasing'
            elif price_variation < -2:
                price_trend = 'decreasing'
            else:
                price_trend = 'stable'
        else:
            average_price = 0
            max_price = 0
            min_price = 0
            price_variation = 0
            price_trend = 'stable'
        
        # Obtener pronósticos (simulados)
        price_forecast = []
        
        # Obtener alertas activas
        active_alerts = EnergyAlert.objects.filter(
            is_active=True,
            affected_date__range=[start_date, end_date]
        )
        alerts = [alert.title for alert in active_alerts]
        
        # Obtener datos del mercado
        market_data = EnergyMarketData.objects.filter(
            date__range=[start_date, end_date]
        ).order_by('-date').first()
        
        # Determinar la fuente REAL de los datos servidos. No se marcan datos válidos como
        # 'Error': se distingue el origen real de XM del origen simulado (p.ej. el comando
        # populate crea registros con source='ElectricityMaps').
        if prices.exists():
            sources = set(p.source for p in prices)
            if sources == {'XM'}:
                data_source = 'XM'
            elif 'XM' not in sources:
                data_source = 'simulated'  # datos simulados (no reales de XM)
            else:
                data_source = 'mixed'      # mezcla de reales y simulados
        else:
            data_source = 'none'
        
        response_data = {
            'average_price': average_price,
            'max_price': max_price,
            'min_price': min_price,
            'price_variation': price_variation,
            'price_trend': price_trend,
            'price_history': [
                {
                    'date': p.date.strftime('%Y-%m-%d'),
                    'price': float(p.price_per_kwh)
                }
                for p in prices
            ],
            'price_forecast': price_forecast,
            'alerts': alerts,
            'market_demand': float(market_data.demand_mw) if market_data else 0,
            'market_supply': float(market_data.supply_mw) if market_data else 0,
            'renewable_percentage': float(market_data.renewable_percentage) if market_data else 0,
            'source': data_source
        }
        
        serializer = ExternalEnergySummarySerializer(response_data)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error en energy_prices: {str(e)}")
        return Response(
            {'error': 'Error al obtener precios de energía'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(tags=["Mercado Energético (XM)"], summary="Ahorros estimados por energía")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def energy_savings(request):
    """
    Obtiene datos de ahorro de energía para el rango especificado
    """
    try:
        range_param = request.GET.get('range', 'month')
        
        # Calcular fechas según el rango
        end_date = timezone.now().date()
        if range_param == 'week':
            start_date = end_date - timedelta(days=7)
        elif range_param == 'month':
            start_date = end_date - timedelta(days=30)
        elif range_param == 'quarter':
            start_date = end_date - timedelta(days=90)
        elif range_param == 'year':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Obtener ahorros del período
        savings = EnergySavings.objects.filter(
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Los datos de ahorro deben existir en la base de datos
        # Si no hay datos, retornar valores por defecto
        
        # Calcular totales
        total_consumed = sum(float(s.total_consumed_kwh) for s in savings)
        total_generated = sum(float(s.total_generated_kwh) for s in savings)
        total_savings = sum(float(s.total_savings_cop) for s in savings)
        
        # Calcular costo evitado
        average_price = EnergyPrice.objects.filter(
            date__range=[start_date, end_date]
        ).aggregate(avg_price=models.Avg('price_per_kwh'))['avg_price'] or 0
        average_price_float = float(average_price)
        
        avoided_cost = total_generated * average_price_float
        
        # Calcular porcentajes (evitar división por cero)
        savings_percentage = 0
        if total_consumed > 0 and average_price_float > 0:
            savings_percentage = (total_savings / (total_consumed * average_price_float)) * 100
        
        self_consumption = 0
        if total_consumed > 0:
            self_consumption = min((total_generated / total_consumed) * 100, 100)
        
        # Calcular excedentes
        excess_energy = max(0, total_generated - total_consumed)
        
        # Calcular factor de capacidad (simplificado).
        # La capacidad instalada es parametrizable (settings.SOLAR_INSTALLED_CAPACITY_KW,
        # variable de entorno SOLAR_INSTALLED_CAPACITY_KW; por defecto 100 kW).
        capacity_factor = 0
        installed_capacity = float(getattr(settings, 'SOLAR_INSTALLED_CAPACITY_KW', 100))
        hours_in_period = (end_date - start_date).days * 24
        # Guardar contra división por cero (p.ej. start_date == end_date -> hours_in_period == 0).
        if total_generated > 0 and installed_capacity > 0 and hours_in_period > 0:
            capacity_factor = (total_generated / (installed_capacity * hours_in_period)) * 100

        # Calcular ROI (simplificado).
        # El costo de instalación es parametrizable (settings.SOLAR_INSTALLATION_COST_COP,
        # variable de entorno SOLAR_INSTALLATION_COST_COP; por defecto 50.000.000 COP).
        installation_cost = float(getattr(settings, 'SOLAR_INSTALLATION_COST_COP', 50000000))
        roi = 0
        if installation_cost > 0:
            roi = (total_savings / installation_cost) * 100
        
        # Datos mensuales
        monthly_savings = []
        current_month = start_date.replace(day=1)
        
        while current_month <= end_date:
            month_end = (current_month.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            month_savings = savings.filter(date__range=[current_month, month_end])
            
            month_total = sum(float(s.total_savings_cop) for s in month_savings)
            
            monthly_savings.append({
                'month': current_month.strftime('%Y-%m'),
                'savings': month_total
            })
            
            current_month = (current_month.replace(day=1) + timedelta(days=32)).replace(day=1)
        
        response_data = {
            'total_consumed': total_consumed,
            'total_generated': total_generated,
            'total_savings': total_savings,
            'avoided_cost': avoided_cost,
            'savings_percentage': savings_percentage,
            'self_consumption': self_consumption,
            'excess_energy': excess_energy,
            'capacity_factor': capacity_factor,
            'roi': roi,
            'monthly_savings': monthly_savings
        }
        
        serializer = EnergySavingsSummarySerializer(response_data)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error en energy_savings: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de ahorro'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(tags=["Operación"], summary="Sincronizar datos externos del mercado (XM)")
@api_view(['POST'])
@permission_classes([IsSuperUser])
def sync_external_data(request):
    """
    Sincroniza datos externos de energía desde fuentes como XM.

    La sincronización llama a la API de XM (red potencialmente lenta) y persiste datos, por
    lo que se ejecuta como tarea Celery asíncrona en lugar de bloquear el ciclo
    request/response de Django.
    """
    try:
        # Import diferido: la tarea depende de Celery y de los servicios de XM.
        from .tasks import sync_external_energy_data

        async_result = sync_external_energy_data.delay()

        return Response(
            {
                'message': 'Sincronización de datos externos encolada',
                'task_id': async_result.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    except Exception as e:
        logger.error(f"Error al encolar la sincronización externa: {str(e)}")
        return Response(
            {'error': 'Error al encolar la sincronización de datos externos'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Resumen del mercado energético")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def market_overview(request):
    """
    Obtiene una vista general del mercado de energía
    """
    try:
        today = timezone.now().date()
        
        # Obtener datos más recientes del mercado
        market_data = EnergyMarketData.objects.filter(
            date__lte=today
        ).order_by('-date').first()
        
        # Obtener precios recientes
        recent_prices = EnergyPrice.objects.filter(
            date__lte=today
        ).order_by('-date')[:7]
        
        # Obtener alertas activas
        active_alerts = EnergyAlert.objects.filter(
            is_active=True
        ).order_by('-created_at')[:5]
        
        response_data = {
            'market_data': {
                'demand_mw': float(market_data.demand_mw) if market_data else 0,
                'supply_mw': float(market_data.supply_mw) if market_data else 0,
                'renewable_percentage': float(market_data.renewable_percentage) if market_data else 0,
                'market_price_cop_mwh': float(market_data.market_price_cop_mwh) if market_data else 0
            } if market_data else {},
            'recent_prices': [
                {
                    'date': p.date.strftime('%Y-%m-%d'),
                    'price': float(p.price_per_kwh)
                }
                for p in recent_prices
            ],
            'active_alerts': [
                {
                    'type': alert.alert_type,
                    'severity': alert.severity,
                    'title': alert.title,
                    'description': alert.description
                }
                for alert in active_alerts
            ]
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en market_overview: {str(e)}")
        return Response(
            {'error': 'Error al obtener vista del mercado'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _range_to_dates(range_param):
    """Mapea el parámetro 'range' a (start_date, end_date). Rango desconocido → 30 días."""
    end_date = timezone.now().date()
    days = {'week': 7, 'month': 30, 'quarter': 90, 'year': 365}.get(range_param, 30)
    return end_date - timedelta(days=days), end_date


def _xm_metric_response(request, fetch_method, prefix, default_range, error_label):
    """Vista genérica para las series de XM (generación/demanda/emisiones/exportaciones/
    importaciones): mismo cálculo de rango, estadísticas y envelope, parametrizado por
    métrica. Evita 5 copias que ya divergían (default 'week' vs 'month')."""
    try:
        range_param = request.GET.get('range', default_range)
        start_date, end_date = _range_to_dates(range_param)

        data = None
        try:
            data = getattr(XMEnergyService(), fetch_method)(start_date, end_date)
        except Exception as e:
            logger.warning(f"No se pudieron obtener datos de {error_label} de XM: {str(e)}")

        # Conserva los ceros legítimos; solo descarta None/NaN.
        values = [item['value'] for item in data if _is_valid_number(item['value'])] if data else []
        if values:
            avg_v, max_v, min_v, total_v = sum(values) / len(values), max(values), min(values), sum(values)
        else:
            avg_v = max_v = min_v = total_v = 0

        return Response({
            f'average_{prefix}': avg_v,
            f'max_{prefix}': max_v,
            f'min_{prefix}': min_v,
            f'total_{prefix}': total_v,
            f'{prefix}_history': data or [],
            'source': 'XM' if data else 'unavailable',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param,
            },
        })
    except Exception as e:
        logger.error(f"Error en {prefix}_data: {str(e)}")
        return Response(
            {'error': f'Error al obtener datos de {error_label}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Datos de generación del sistema (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def generation_data(request):
    """Obtiene datos de generación de energía desde XM"""
    return _xm_metric_response(request, 'fetch_generation_data', 'generation', 'month', 'generación')


@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Datos de demanda del sistema (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def demand_data(request):
    """Obtiene datos de demanda de energía desde XM"""
    return _xm_metric_response(request, 'fetch_demand_data', 'demand', 'month', 'demanda')


@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Datos de emisiones (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def emissions_data(request):
    """Obtiene datos de emisiones de CO2 desde XM"""
    return _xm_metric_response(request, 'fetch_emissions_data', 'emissions', 'month', 'emisiones')

@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Datos de exportaciones de energía (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def exports_data(request):
    """Obtiene datos de exportaciones de energía desde XM"""
    return _xm_metric_response(request, 'fetch_exports_data', 'exports', 'week', 'exportaciones')

@cache_page(XM_CACHE_TTL)
@vary_on_headers('Authorization')
@extend_schema(tags=["Mercado Energético (XM)"], summary="Datos de importaciones de energía (XM)")
@api_view(['GET'])
@permission_classes([IsSuperUser])
def imports_data(request):
    """Obtiene datos de importaciones de energía desde XM"""
    return _xm_metric_response(request, 'fetch_imports_data', 'imports', 'week', 'importaciones')
