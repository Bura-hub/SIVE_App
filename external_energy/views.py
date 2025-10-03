from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
from decimal import Decimal
import logging

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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
            # Si no hay datos, intentar obtener de fuentes externas
            xm_service = XMEnergyService()
            prices_data = xm_service.fetch_energy_prices(start_date, end_date)
            
            # Crear registros en la base de datos
            for price_data in prices_data:
                try:
                    # Convertir string de fecha a objeto date si es necesario
                    if isinstance(price_data['date'], str):
                        price_date = datetime.strptime(price_data['date'], '%Y-%m-%d').date()
                    else:
                        price_date = price_data['date']
                    
                    EnergyPrice.objects.create(
                        date=price_date,
                        price_per_kwh=price_data['price'],
                        source='XM',
                        region='Colombia'
                    )
                except Exception as e:
                    logger.warning(f"Error creando registro de precio: {str(e)}")
                    continue
            
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
        
        # Determinar fuente de datos
        data_source = 'XM' if prices.exists() and prices.first().source == 'XM' else 'Error'
        
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
        
        avoided_cost = total_generated * float(average_price)
        
        # Calcular porcentajes
        savings_percentage = 0
        if total_consumed > 0:
            savings_percentage = (total_savings / (total_consumed * float(average_price))) * 100
        
        self_consumption = 0
        if total_consumed > 0:
            self_consumption = min((total_generated / total_consumed) * 100, 100)
        
        # Calcular excedentes
        excess_energy = max(0, total_generated - total_consumed)
        
        # Calcular factor de capacidad (simplificado)
        capacity_factor = 0
        if total_generated > 0:
            # Asumiendo una capacidad instalada de 100kW como ejemplo
            installed_capacity = 100
            hours_in_period = (end_date - start_date).days * 24
            capacity_factor = (total_generated / (installed_capacity * hours_in_period)) * 100
        
        # Calcular ROI (simplificado)
        # Asumiendo un costo de instalación de 50,000,000 COP
        installation_cost = 50000000
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_external_data(request):
    """
    Sincroniza datos externos de energía desde fuentes como XM
    """
    try:
        # Obtener datos de XM
        xm_service = XMEnergyService()
        sync_result = xm_service.sync_all_data()
        
        return Response({
            'message': 'Datos sincronizados exitosamente',
            'details': sync_result
        })
        
    except Exception as e:
        logger.error(f"Error en sync_external_data: {str(e)}")
        return Response(
            {'error': 'Error al sincronizar datos externos'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generation_data(request):
    """
    Obtiene datos de generación de energía desde XM
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
        
        # Obtener datos de generación desde XM
        xm_service = XMEnergyService()
        generation_data = xm_service.fetch_generation_data(start_date, end_date)
        
        # Calcular estadísticas
        if generation_data:
            values = [item['value'] for item in generation_data if item['value'] > 0]
            if values:
                avg_generation = sum(values) / len(values)
                max_generation = max(values)
                min_generation = min(values)
                total_generation = sum(values)
            else:
                avg_generation = max_generation = min_generation = total_generation = 0
        else:
            avg_generation = max_generation = min_generation = total_generation = 0
        
        response_data = {
            'average_generation': avg_generation,
            'max_generation': max_generation,
            'min_generation': min_generation,
            'total_generation': total_generation,
            'generation_history': generation_data,
            'source': 'XM' if generation_data else 'Error',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en generation_data: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de generación'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def demand_data(request):
    """
    Obtiene datos de demanda de energía desde XM
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
        
        # Obtener datos de demanda desde XM
        xm_service = XMEnergyService()
        demand_data = xm_service.fetch_demand_data(start_date, end_date)
        
        # Calcular estadísticas
        if demand_data:
            values = [item['value'] for item in demand_data if item['value'] > 0]
            if values:
                avg_demand = sum(values) / len(values)
                max_demand = max(values)
                min_demand = min(values)
                total_demand = sum(values)
            else:
                avg_demand = max_demand = min_demand = total_demand = 0
        else:
            avg_demand = max_demand = min_demand = total_demand = 0
        
        response_data = {
            'average_demand': avg_demand,
            'max_demand': max_demand,
            'min_demand': min_demand,
            'total_demand': total_demand,
            'demand_history': demand_data,
            'source': 'XM' if demand_data else 'Error',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en demand_data: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de demanda'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def emissions_data(request):
    """
    Obtiene datos de emisiones de CO2 desde XM
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
        
        # Obtener datos de emisiones desde XM
        xm_service = XMEnergyService()
        emissions_data = xm_service.fetch_emissions_data(start_date, end_date)
        
        # Calcular estadísticas
        if emissions_data:
            values = [item['value'] for item in emissions_data if item['value'] > 0]
            if values:
                avg_emissions = sum(values) / len(values)
                max_emissions = max(values)
                min_emissions = min(values)
                total_emissions = sum(values)
            else:
                avg_emissions = max_emissions = min_emissions = total_emissions = 0
        else:
            avg_emissions = max_emissions = min_emissions = total_emissions = 0
        
        response_data = {
            'average_emissions': avg_emissions,
            'max_emissions': max_emissions,
            'min_emissions': min_emissions,
            'total_emissions': total_emissions,
            'emissions_history': emissions_data,
            'source': 'XM' if emissions_data else 'Error',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en emissions_data: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de emisiones'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exports_data(request):
    """Obtiene datos de exportaciones de energía desde XM"""
    try:
        range_param = request.GET.get('range', 'week')
        end_date = timezone.now().date()
        
        # Calcular fecha de inicio según el rango
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
        
        # Obtener datos de exportaciones desde XM
        xm_service = XMEnergyService()
        exports_data = xm_service.fetch_exports_data(start_date, end_date)
        
        # Calcular estadísticas
        if exports_data:
            values = [item['value'] for item in exports_data if item['value'] > 0]
            if values:
                avg_exports = sum(values) / len(values)
                max_exports = max(values)
                min_exports = min(values)
                total_exports = sum(values)
            else:
                avg_exports = max_exports = min_exports = total_exports = 0
        else:
            avg_exports = max_exports = min_exports = total_exports = 0
        
        response_data = {
            'average_exports': avg_exports,
            'max_exports': max_exports,
            'min_exports': min_exports,
            'total_exports': total_exports,
            'exports_history': exports_data,
            'source': 'XM' if exports_data else 'Error',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en exports_data: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de exportaciones'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def imports_data(request):
    """Obtiene datos de importaciones de energía desde XM"""
    try:
        range_param = request.GET.get('range', 'week')
        end_date = timezone.now().date()
        
        # Calcular fecha de inicio según el rango
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
        
        # Obtener datos de importaciones desde XM
        xm_service = XMEnergyService()
        imports_data = xm_service.fetch_imports_data(start_date, end_date)
        
        # Calcular estadísticas
        if imports_data:
            values = [item['value'] for item in imports_data if item['value'] > 0]
            if values:
                avg_imports = sum(values) / len(values)
                max_imports = max(values)
                min_imports = min(values)
                total_imports = sum(values)
            else:
                avg_imports = max_imports = min_imports = total_imports = 0
        else:
            avg_imports = max_imports = min_imports = total_imports = 0
        
        response_data = {
            'average_imports': avg_imports,
            'max_imports': max_imports,
            'min_imports': min_imports,
            'total_imports': total_imports,
            'imports_history': imports_data,
            'source': 'XM' if imports_data else 'Error',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'range': range_param
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error en imports_data: {str(e)}")
        return Response(
            {'error': 'Error al obtener datos de importaciones'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
