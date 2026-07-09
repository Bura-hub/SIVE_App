from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta, time
from indicators.models import ElectricMeterIndicators
from indicators.tasks import calculate_electric_meter_indicators
from scada_proxy.models import Device, Institution, DeviceCategory, Measurement

class ElectricMeterIndicatorsTestCase(TestCase):
    def setUp(self):
        """Configuración inicial para las pruebas"""
        # Crear categoría de medidor eléctrico
        self.category = DeviceCategory.objects.create(
            scada_id='CAT_ELECTRICMETER',
            name='electricmeter',
            description='Medidor Eléctrico'
        )

        # Crear institución
        self.institution = Institution.objects.create(
            scada_id='INST_TEST',
            name='Test Institution'
        )
        
        # Crear dispositivo (medidor eléctrico)
        self.device = Device.objects.create(
            name='Test Electric Meter',
            scada_id='TEST_METER_001',
            category=self.category,
            institution=self.institution
        )
        
        # Fecha de prueba
        self.test_date = timezone.now().date()

    def test_electric_meter_indicators_creation(self):
        """Prueba la creación de indicadores eléctricos"""
        indicators = ElectricMeterIndicators.objects.create(
            device=self.device,
            institution=self.institution,
            date=self.test_date,
            time_range='daily',
            imported_energy_kwh=100.5,
            exported_energy_kwh=25.3,
            net_energy_consumption_kwh=75.2,
            peak_demand_kw=150.0,
            avg_demand_kw=75.0,
            load_factor_pct=50.0,
            avg_power_factor=0.95,
            max_voltage_unbalance_pct=2.1,
            max_current_unbalance_pct=1.8,
            max_voltage_thd_pct=3.2,
            max_current_thd_pct=2.9,
            max_current_tdd_pct=2.5
        )
        
        self.assertEqual(indicators.device, self.device)
        self.assertEqual(indicators.institution, self.institution)
        self.assertEqual(indicators.imported_energy_kwh, 100.5)
        self.assertEqual(indicators.peak_demand_kw, 150.0)
        self.assertEqual(indicators.load_factor_pct, 50.0)

    def test_electric_meter_indicators_str_representation(self):
        """Prueba la representación en string del modelo"""
        indicators = ElectricMeterIndicators.objects.create(
            device=self.device,
            institution=self.institution,
            date=self.test_date,
            time_range='daily',
            imported_energy_kwh=100.0,
            exported_energy_kwh=25.0,
            net_energy_consumption_kwh=75.0,
            peak_demand_kw=150.0,
            avg_demand_kw=75.0,
            load_factor_pct=50.0,
            avg_power_factor=0.95
        )
        
        expected_str = f"{self.device.name} - {self.test_date} ({indicators.get_time_range_display()})"
        self.assertEqual(str(indicators), expected_str)

    def test_calculate_electric_meter_indicators_task(self):
        """Prueba la tarea de cálculo de indicadores eléctricos con mediciones reales."""
        # La tarea lee measurement.data (JSONField) y opera sobre el queryset real
        # (order_by/exists/count), así que creamos mediciones reales dentro del día.
        # Mediodía aware: cae dentro de [test_date, test_date+1) para cualquier offset de TZ.
        base = timezone.make_aware(datetime.combine(self.test_date, time(12, 0)))
        # Insertadas por el helper real de ingesta (dual-write v1+v2): la tarea
        # migrada lee la tabla tipada MeterMeasurement.
        from scada_proxy.tasks import upsert_measurements_page
        upsert_measurements_page(self.device, [
            (base, {
                'importedActivePowerLow': 100.0, 'importedActivePowerHigh': 0.5,
                'exportedActivePowerLow': 25.0, 'exportedActivePowerHigh': 0.1,
                'totalActivePower': 150.0, 'totalPowerFactor': 0.95,
                'voltagePhaseA': 220.0, 'voltagePhaseB': 221.0, 'voltagePhaseC': 219.0,
                'currentPhaseA': 10.0, 'currentPhaseB': 10.5, 'currentPhaseC': 9.5,
                'voltageTHDPhaseA': 3.2, 'voltageTHDPhaseB': 3.0, 'voltageTHDPhaseC': 3.1,
                'currentTHDPhaseA': 2.9, 'currentTHDPhaseB': 2.7, 'currentTHDPhaseC': 2.8,
                'currentTDDPhaseA': 2.5, 'currentTDDPhaseB': 2.3, 'currentTDDPhaseC': 2.4,
            }),
            (base + timedelta(minutes=2), {
                'importedActivePowerLow': 200.0, 'importedActivePowerHigh': 1.0,
                'exportedActivePowerLow': 50.0, 'exportedActivePowerHigh': 0.2,
                'totalActivePower': 300.0, 'totalPowerFactor': 0.98,
                'voltagePhaseA': 222.0, 'voltagePhaseB': 220.0, 'voltagePhaseC': 218.0,
                'currentPhaseA': 12.0, 'currentPhaseB': 11.5, 'currentPhaseC': 12.5,
                'voltageTHDPhaseA': 2.8, 'voltageTHDPhaseB': 2.6, 'voltageTHDPhaseC': 2.7,
                'currentTHDPhaseA': 2.5, 'currentTHDPhaseB': 2.4, 'currentTHDPhaseC': 2.3,
                'currentTDDPhaseA': 2.1, 'currentTDDPhaseB': 2.0, 'currentTDDPhaseC': 1.9,
            }),
        ])

        # Ejecutar la tarea
        result = calculate_electric_meter_indicators(
            self.device.id,
            self.test_date.strftime('%Y-%m-%d'),
            'daily'
        )
        
        # Verificar que se creó el indicador
        indicators = ElectricMeterIndicators.objects.filter(
            device=self.device,
            date=self.test_date,
            time_range='daily'
        )
        
        self.assertTrue(indicators.exists(), result)
        indicator = indicators.first()
        
        # Verificar cálculos básicos
        self.assertIsNotNone(indicator.imported_energy_kwh)
        self.assertIsNotNone(indicator.exported_energy_kwh)
        self.assertIsNotNone(indicator.net_energy_consumption_kwh)
        self.assertIsNotNone(indicator.peak_demand_kw)
        self.assertIsNotNone(indicator.avg_demand_kw)
        self.assertIsNotNone(indicator.load_factor_pct)

    def test_electric_meter_indicators_validation(self):
        """Prueba la validación de campos del modelo"""
        # Crear indicadores con valores válidos
        indicators = ElectricMeterIndicators(
            device=self.device,
            institution=self.institution,
            date=self.test_date,
            time_range='daily',
            imported_energy_kwh=100.0,
            exported_energy_kwh=25.0,
            net_energy_consumption_kwh=75.0,
            peak_demand_kw=150.0,
            avg_demand_kw=75.0,
            load_factor_pct=50.0,
            avg_power_factor=0.95
        )
        
        # full_clean() no lanza y devuelve None cuando el modelo es válido
        self.assertIsNone(indicators.full_clean())

    def test_electric_meter_indicators_time_range_choices(self):
        """Prueba las opciones de rango de tiempo"""
        indicators = ElectricMeterIndicators.objects.create(
            device=self.device,
            institution=self.institution,
            date=self.test_date,
            time_range='monthly',
            imported_energy_kwh=100.0,
            exported_energy_kwh=25.0,
            net_energy_consumption_kwh=75.0,
            peak_demand_kw=150.0,
            avg_demand_kw=75.0,
            load_factor_pct=50.0,
            avg_power_factor=0.95
        )
        
        # Verificar que se puede obtener el display del rango de tiempo
        self.assertEqual(indicators.get_time_range_display(), 'Mensual')

if __name__ == '__main__':
    import pytest  # import perezoso: solo requerido para ejecución standalone
    pytest.main([__file__])
