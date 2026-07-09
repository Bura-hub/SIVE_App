# Data migration: elimina los registros SIMULADOS de EnergySavings, EnergyMarketData y
# EnergyPriceForecast.
#
# Contexto: esas tres tablas solo contenían filas sintéticas creadas por el comando
# `populate_external_energy_data` (91 filas con fechas 2025-11-26 → 2026-02-24); ninguna
# tarea real las alimentaba, por lo que los endpoints de ahorros/mercado devolvían 0.00.
# Se borran TODAS las filas (autorizado: todo el contenido es sintético). Los datos
# reales los pueblan a partir de ahora:
#   - EnergySavings:   external_energy.tasks.calculate_energy_savings (diaria, 03:30)
#   - EnergyMarketData: XMEnergyService._sync_market_data dentro del sync diario (03:00)
# EnergyPriceForecast queda vacía (no hay fuente real de pronósticos todavía).
#
# La operación inversa es un no-op: los datos sintéticos no se restauran.

from django.db import migrations


def delete_simulated_rows(apps, schema_editor):
    for model_name in ('EnergySavings', 'EnergyMarketData', 'EnergyPriceForecast'):
        model = apps.get_model('external_energy', model_name)
        deleted, _ = model.objects.all().delete()
        print(f"  external_energy.{model_name}: {deleted} registros simulados eliminados")


class Migration(migrations.Migration):

    dependencies = [
        ('external_energy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(delete_simulated_rows, migrations.RunPython.noop),
    ]
