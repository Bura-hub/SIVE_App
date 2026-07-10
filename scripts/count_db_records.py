#!/usr/bin/env python
"""
Script para contar registros en las tablas principales y ver si se está llenando la BD.
Ejecutar dentro del contenedor backend:
  docker compose -f docker-compose.prod.yml exec backend python scripts/count_db_records.py
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.db import connection
from scada_proxy.models import Device, DeviceCategory, Institution, MeterMeasurement, InverterMeasurement, WeatherStationMeasurement
from indicators.models import (
    MonthlyConsumptionKPI,
    DailyChartData,
    ElectricMeterIndicators,
    ElectricMeterChartData,
    InverterIndicators,
    InverterChartData,
    WeatherStationIndicators,
    WeatherStationChartData,
)

def main():
    print("=" * 60)
    print("CONTEO DE REGISTROS EN LA BASE DE DATOS")
    print("=" * 60)

    # SCADA / proxy
    print("\n--- SCADA (scada_proxy) ---")
    print(f"  Institution:           {Institution.objects.count()}")
    print(f"  DeviceCategory:       {DeviceCategory.objects.count()}")
    print(f"  Device:               {Device.objects.count()}")
    print(f"  MeterMeasurement:     {MeterMeasurement.objects.count()}")
    print(f"  InverterMeasurement:  {InverterMeasurement.objects.count()}")
    print(f"  WeatherStationMeas.:  {WeatherStationMeasurement.objects.count()}")

    # Indicadores dashboard
    print("\n--- Dashboard (indicators) ---")
    print(f"  MonthlyConsumptionKPI: {MonthlyConsumptionKPI.objects.count()}")
    print(f"  DailyChartData:         {DailyChartData.objects.count()}")

    # Por componente
    print("\n--- Medidores eléctricos ---")
    print(f"  ElectricMeterIndicators: {ElectricMeterIndicators.objects.count()}")
    print(f"  ElectricMeterChartData:   {ElectricMeterChartData.objects.count()}")

    print("\n--- Inversores ---")
    print(f"  InverterIndicators:   {InverterIndicators.objects.count()}")
    print(f"  InverterChartData:    {InverterChartData.objects.count()}")

    print("\n--- Estaciones meteorológicas ---")
    print(f"  WeatherStationIndicators: {WeatherStationIndicators.objects.count()}")
    print(f"  WeatherStationChartData:   {WeatherStationChartData.objects.count()}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
