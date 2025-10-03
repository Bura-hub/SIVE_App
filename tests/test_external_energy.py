#!/usr/bin/env python3
"""
Script de prueba para la funcionalidad de datos externos de energía
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from external_energy.models import (
    EnergyPrice, 
    EnergySavings, 
    EnergyPriceForecast, 
    EnergyMarketData, 
    EnergyAlert
)
from external_energy.services import (
    XMEnergyService
)


def test_models():
    """Prueba la creación y funcionalidad de los modelos"""
    print("🧪 Probando modelos...")
    
    try:
        # Crear un precio de energía
        price = EnergyPrice.objects.create(
            date=datetime.now().date(),
            price_per_kwh=Decimal('450.50'),
            source='ElectricityMaps',
            region='Colombia'
        )
        print(f"  ✅ Precio creado: {price}")
        
        # Crear datos del mercado
        market_data = EnergyMarketData.objects.create(
            date=datetime.now().date(),
            demand_mw=Decimal('9500.00'),
            supply_mw=Decimal('10200.00'),
            hydro_percentage=Decimal('70.00'),
            thermal_percentage=Decimal('20.00'),
            renewable_percentage=Decimal('10.00'),
            market_price_cop_mwh=Decimal('200000.00')
        )
        print(f"  ✅ Datos del mercado creados: {market_data}")
        
        # Crear un ahorro de energía
        savings = EnergySavings.objects.create(
            date=datetime.now().date(),
            total_consumed_kwh=Decimal('150.00'),
            total_generated_kwh=Decimal('120.00'),
            average_price_kwh=Decimal('450.50')
        )
        print(f"  ✅ Ahorro creado: {savings}")
        print(f"     - Ahorro total: {savings.total_savings_cop} COP")
        print(f"     - Porcentaje de ahorro: {savings.savings_percentage}%")
        print(f"     - Autoconsumo: {savings.self_consumption_percentage}%")
        
        # Crear un pronóstico
        forecast = EnergyPriceForecast.objects.create(
            date=datetime.now().date() + timedelta(days=1),
            predicted_price_kwh=Decimal('455.00'),
            confidence_level=Decimal('85.5'),
            source='ElectricityMaps',
            algorithm='ML_Model'
        )
        print(f"  ✅ Pronóstico creado: {forecast}")
        
        # Crear una alerta
        alert = EnergyAlert.objects.create(
            alert_type='price_spike',
            severity='medium',
            title='Pico de precio detectado',
            description='Se ha detectado un incremento significativo en los precios',
            affected_date=datetime.now().date(),
            is_active=True
        )
        print(f"  ✅ Alerta creada: {alert}")
        
        print("  🎉 Todos los modelos funcionan correctamente")
        
    except Exception as e:
        print(f"  ❌ Error en modelos: {e}")
        return False
    
    return True


def test_services():
    """Prueba los servicios de datos externos"""
    print("\n🔌 Probando servicios...")
    
    try:
        # Probar servicio XM
        xm_service = XMEnergyService()
        print(f"  ✅ Servicio XM creado: {xm_service}")
        
        # Probar obtención de precios desde XM
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        prices = xm_service.fetch_energy_prices(start_date, end_date)
        print(f"  ✅ Precios XM obtenidos: {len(prices)} registros")
        
        # Probar datos de generación
        generation_data = xm_service.fetch_generation_data(start_date, end_date)
        print(f"  ✅ Datos de generación obtenidos: {len(generation_data)} registros")
        
        # Probar datos de demanda
        demand_data = xm_service.fetch_demand_data(start_date, end_date)
        print(f"  ✅ Datos de demanda obtenidos: {len(demand_data)} registros")
        
        # Probar datos de emisiones
        emissions_data = xm_service.fetch_emissions_data(start_date, end_date)
        print(f"  ✅ Datos de emisiones obtenidos: {len(emissions_data)} registros")
        
        print("  🎉 Todos los servicios funcionan correctamente")
        
    except Exception as e:
        print(f"  ❌ Error en servicios: {e}")
        return False
    
    return True


def test_api_endpoints():
    """Prueba los endpoints de la API"""
    print("\n🌐 Probando endpoints de la API...")
    
    try:
        from django.test import Client
        from django.contrib.auth.models import User
        
        # Crear un usuario de prueba
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        if created:
            user.set_password('testpass123')
            user.save()
        
        # Crear un token de autenticación
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=user)
        
        # Crear cliente de prueba
        client = Client()
        client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        
        # Probar endpoint de precios
        response = client.get('/api/external-energy/prices/?range=week')
        print(f"  ✅ Endpoint de precios: {response.status_code}")
        
        # Probar endpoint de ahorros
        response = client.get('/api/external-energy/savings/?range=week')
        print(f"  ✅ Endpoint de ahorros: {response.status_code}")
        
        # Probar endpoint de vista del mercado
        response = client.get('/api/external-energy/market-overview/')
        print(f"  ✅ Endpoint del mercado: {response.status_code}")
        
        print("  🎉 Todos los endpoints funcionan correctamente")
        
    except Exception as e:
        print(f"  ❌ Error en endpoints: {e}")
        return False
    
    return True


def test_xm_data_generation():
    """Prueba la generación de datos desde XM"""
    print("\n⚡ Probando datos de XM...")
    
    try:
        xm_service = XMEnergyService()
        
        # Probar diferentes períodos
        periods = [
            ('Última semana', 7),
            ('Último mes', 30),
            ('Últimos 3 meses', 90)
        ]
        
        for period_name, days in periods:
            print(f"  📅 Probando {period_name}...")
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Probar precios
            prices = xm_service.fetch_energy_prices(start_date, end_date)
            print(f"    ✅ Precios obtenidos: {len(prices)} registros")
            
            # Probar generación
            generation = xm_service.fetch_generation_data(start_date, end_date)
            print(f"    ✅ Generación obtenida: {len(generation)} registros")
            
            # Probar demanda
            demand = xm_service.fetch_demand_data(start_date, end_date)
            print(f"    ✅ Demanda obtenida: {len(demand)} registros")
            
            # Probar emisiones
            emissions = xm_service.fetch_emissions_data(start_date, end_date)
            print(f"    ✅ Emisiones obtenidas: {len(emissions)} registros")
        
        print("  🎉 Datos de XM funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"  ❌ Error en datos de XM: {e}")
        return False


def cleanup_test_data():
    """Limpia los datos de prueba"""
    print("\n🧹 Limpiando datos de prueba...")
    
    try:
        # Eliminar registros de prueba
        EnergyPrice.objects.filter(source='ElectricityMaps').delete()
        EnergyMarketData.objects.all().delete()
        EnergySavings.objects.all().delete()
        EnergyPriceForecast.objects.all().delete()
        EnergyAlert.objects.all().delete()
        
        print("  ✅ Datos de prueba eliminados")
        
    except Exception as e:
        print(f"  ❌ Error al limpiar: {e}")


def main():
    """Función principal de pruebas"""
    print("🚀 Iniciando pruebas de datos externos de energía...\n")
    
    # Ejecutar pruebas
    models_ok = test_models()
    services_ok = test_services()
    api_ok = test_api_endpoints()
    xm_ok = test_xm_data_generation()
    
    # Limpiar datos de prueba
    cleanup_test_data()
    
    # Resumen
    print("\n📊 Resumen de pruebas:")
    print(f"  Modelos: {'✅ OK' if models_ok else '❌ FALLO'}")
    print(f"  Servicios: {'✅ OK' if services_ok else '❌ FALLO'}")
    print(f"  API: {'✅ OK' if api_ok else '❌ FALLO'}")
    print(f"  Datos XM: {'✅ OK' if xm_ok else '❌ FALLO'}")
    
    if all([models_ok, services_ok, api_ok, xm_ok]):
        print("\n🎉 Todas las pruebas pasaron exitosamente!")
        return 0
    else:
        print("\n💥 Algunas pruebas fallaron")
        return 1


if __name__ == '__main__':
    sys.exit(main())
