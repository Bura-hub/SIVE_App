#!/usr/bin/env python3
"""
Script de prueba para verificar la integración con la API de XM
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Configurar Django
sys.path.append('/home/insuasti/iteracion2/SIVET_App/SIVET_App')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from external_energy.services import XMRealAPIService, XMEnergyService

def test_xm_service():
    """Prueba el servicio de XM"""
    print("🔍 Probando integración con API de XM...")
    
    # Crear instancia del servicio
    xm_service = XMRealAPIService()
    
    # Verificar disponibilidad de la API
    print(f"📡 API de XM disponible: {xm_service.api_available}")
    
    if not xm_service.api_available:
        print("⚠️  pydataxm no está disponible. Usando datos simulados.")
    
    # Fechas de prueba
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)
    
    print(f"📅 Período de prueba: {start_date} a {end_date}")
    
    try:
        # Probar obtención de precios
        print("\n💰 Probando obtención de precios...")
        prices = xm_service.fetch_energy_prices(start_date, end_date)
        print(f"✅ Precios obtenidos: {len(prices)} registros")
        if prices:
            print(f"   Precio promedio: {sum(p['price'] for p in prices) / len(prices):.2f} COP/kWh")
        
        # Probar obtención de generación
        print("\n⚡ Probando obtención de generación...")
        generation = xm_service.fetch_generation_data(start_date, end_date)
        print(f"✅ Datos de generación obtenidos: {len(generation)} registros")
        if generation:
            print(f"   Generación promedio: {sum(g['value'] for g in generation) / len(generation):.2f} MW")
        
        # Probar obtención de demanda
        print("\n📊 Probando obtención de demanda...")
        demand = xm_service.fetch_demand_data(start_date, end_date)
        print(f"✅ Datos de demanda obtenidos: {len(demand)} registros")
        if demand:
            print(f"   Demanda promedio: {sum(d['value'] for d in demand) / len(demand):.2f} MW")
        
        # Probar obtención de emisiones
        print("\n🌱 Probando obtención de emisiones...")
        emissions = xm_service.fetch_emissions_data(start_date, end_date)
        print(f"✅ Datos de emisiones obtenidos: {len(emissions)} registros")
        if emissions:
            print(f"   Factor de emisión promedio: {sum(e['value'] for e in emissions) / len(emissions):.2f} gCO₂e/kWh")
        
        print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {str(e)}")
        return False

def test_xm_energy_service():
    """Prueba el servicio principal de energía"""
    print("\n🔧 Probando XMEnergyService...")
    
    try:
        service = XMEnergyService()
        
        # Probar sincronización
        print("🔄 Probando sincronización de datos...")
        sync_result = service.sync_all_data()
        print(f"✅ Resultado de sincronización: {sync_result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en XMEnergyService: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de integración XM...")
    
    # Ejecutar pruebas
    test1_passed = test_xm_service()
    test2_passed = test_xm_energy_service()
    
    # Resumen
    print("\n" + "="*50)
    print("📋 RESUMEN DE PRUEBAS")
    print("="*50)
    print(f"XMRealAPIService: {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"XMEnergyService: {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")
    
    if test1_passed and test2_passed:
        print("\n🎊 ¡Todas las pruebas pasaron! La integración está lista.")
        sys.exit(0)
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisar la configuración.")
        sys.exit(1)
