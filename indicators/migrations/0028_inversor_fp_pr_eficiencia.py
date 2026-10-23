"""
Corrección de octubre de 2026 en los indicadores de inversor.

- avg_power_factor_pct -> avg_power_factor (escala 0–1, media de |FP|/100 mientras genera).
- dc_ac_efficiency_pct, performance_ratio_pct, reference_energy_kwh, avg_irradiance_wm2,
  avg_temperature_c, avg_frequency_hz y frequency_stability_pct admiten NULL («no disponible»).
- performance_ratio_valid_days y performance_ratio_note: días válidos y motivo del PR.

Los valores ya guardados de FP (en % con signo), eficiencia (recortada a 100 %), PR (siempre 0)
e irradiancia y temperatura del inversor (siempre 0) no significan nada en la escala nueva: se
ponen en NULL. Se rellenan al recalcular los indicadores de inversor (recálculo pendiente).
"""
from django.db import migrations, models

NULL_OUT_SQL = [
    """UPDATE indicators_inverterindicators
          SET avg_power_factor = NULL, dc_ac_efficiency_pct = NULL, performance_ratio_pct = NULL,
              reference_energy_kwh = NULL, avg_irradiance_wm2 = NULL, avg_temperature_c = NULL""",
    """UPDATE indicators_hourlyinverterindicators
          SET avg_power_factor = NULL, dc_ac_efficiency_pct = NULL, performance_ratio_pct = NULL,
              reference_energy_kwh = NULL""",
]


class Migration(migrations.Migration):

    dependencies = [
        ('indicators', '0027_hourlyinverterindicators_hourlymeterindicators_and_more'),
    ]

    operations = [
        migrations.RenameField('inverterindicators', 'avg_power_factor_pct', 'avg_power_factor'),
        migrations.RenameField('hourlyinverterindicators', 'avg_power_factor_pct', 'avg_power_factor'),
        migrations.AlterField(
            model_name='inverterindicators', name='avg_power_factor',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Factor de potencia promedio (0–1) mientras el inversor genera.'),
        ),
        migrations.AlterField(
            model_name='hourlyinverterindicators', name='avg_power_factor',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Factor de potencia promedio de la hora (0–1) mientras el inversor genera.'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='dc_ac_efficiency_pct',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Eficiencia de conversión DC-AC en porcentaje. No se calcula: dcPower mide una sola entrada MPPT.'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='performance_ratio_pct',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Performance Ratio en porcentaje (irradiancia horizontal). NULL si no se puede calcular; ver performance_ratio_note.'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='reference_energy_kwh',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Energía de referencia Σ H × kWp de los días válidos, en kWh.'),
        ),
        migrations.AddField(
            model_name='inverterindicators', name='performance_ratio_valid_days',
            field=models.IntegerField(blank=True, default=None, null=True, help_text='Días válidos usados en el PR.'),
        ),
        migrations.AddField(
            model_name='inverterindicators', name='performance_ratio_note',
            field=models.CharField(blank=True, default=None, max_length=255, null=True, help_text='Motivo por el que el PR no está disponible.'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='avg_irradiance_wm2',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Irradiancia promedio en W/m² (el inversor no la mide: NULL).'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='avg_temperature_c',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Temperatura promedio en °C (el inversor no la mide: NULL).'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='avg_frequency_hz',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Frecuencia promedio en Hz mientras el inversor genera.'),
        ),
        migrations.AlterField(
            model_name='inverterindicators', name='frequency_stability_pct',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Estabilidad de frecuencia en porcentaje mientras el inversor genera.'),
        ),
        migrations.AlterField(
            model_name='hourlyinverterindicators', name='dc_ac_efficiency_pct',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Eficiencia de conversión DC-AC de la hora en porcentaje.'),
        ),
        migrations.AlterField(
            model_name='hourlyinverterindicators', name='performance_ratio_pct',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Performance Ratio de la hora en porcentaje.'),
        ),
        migrations.AlterField(
            model_name='hourlyinverterindicators', name='reference_energy_kwh',
            field=models.FloatField(blank=True, default=None, null=True, help_text='Energía de referencia de la hora en kWh.'),
        ),
        migrations.RunSQL(NULL_OUT_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
