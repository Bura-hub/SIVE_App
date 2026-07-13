from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from datetime import datetime, timedelta, time
from indicators.models import ElectricMeterIndicators
from indicators.services.meter_calc import (
    METER_FIELDS,
    MIN_CURRENT_A_FOR_UNBALANCE,
    compute_meter_indicators,
)
from indicators.tasks import calculate_electric_meter_indicators
from scada_proxy.models import Device, Institution, DeviceCategory

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

    def test_glitch_de_rollover_no_corrompe_energia_importada(self):
        """Integración end-to-end del anti roll-over: un salto imposible en el registro
        acumulado (glitch) NO debe inflar imported_energy_kwh. El registro es
        importedActivePowerHigh*1000 + importedActivePowerLow; el saneamiento descarta el
        delta > cap. Antes, una sola lectura corrupta producía ~5e8 kWh/día."""
        from scada_proxy.tasks import upsert_measurements_page
        base = timezone.make_aware(datetime.combine(self.test_date, time(12, 0)))

        def reading(high, low):
            return {
                'importedActivePowerHigh': high, 'importedActivePowerLow': low,
                'exportedActivePowerHigh': 0.0, 'exportedActivePowerLow': 0.0,
                'totalActivePower': 1.0, 'totalPowerFactor': 0.95,
            }

        # Registro: 1000.0 -> 1000.5 -> 1001.0 (deltas válidos de 0.5), luego un GLITCH a
        # 5e8 y vuelta a 1001.5 (delta negativo). Solo deben contar ~1.0 kWh; el salto de
        # ~5e8 (>cap) y su retorno negativo se descartan.
        upsert_measurements_page(self.device, [
            (base, reading(1, 0.0)),
            (base + timedelta(minutes=2), reading(1, 0.5)),
            (base + timedelta(minutes=4), reading(1, 1.0)),
            (base + timedelta(minutes=6), reading(500000, 0.0)),  # registro = 5e8
            (base + timedelta(minutes=8), reading(1, 1.5)),
        ])

        calculate_electric_meter_indicators(
            self.device.id, self.test_date.strftime('%Y-%m-%d'), 'daily'
        )
        ind = ElectricMeterIndicators.objects.get(
            device=self.device, date=self.test_date, time_range='daily'
        )
        # Sin saneamiento serían ~5e8 kWh; con saneamiento, ~1.0 kWh (los dos deltas válidos).
        self.assertLess(ind.imported_energy_kwh, 100.0)
        self.assertGreater(ind.imported_energy_kwh, 0.0)

    def test_iteracion_diaria_crea_un_indicador_por_dia(self):
        """El envoltorio genérico (services/device_calc.run_over_days) crea un indicador
        diario por cada día del rango."""
        from scada_proxy.tasks import upsert_measurements_page
        from indicators.tasks import _calculate_daily_electrical_data
        day1 = self.test_date
        day2 = self.test_date + timedelta(days=1)
        for d in (day1, day2):
            base = timezone.make_aware(datetime.combine(d, time(12, 0)))
            upsert_measurements_page(self.device, [
                (base, {'totalActivePower': 100.0, 'importedActivePowerHigh': 1, 'importedActivePowerLow': 0.0}),
                (base + timedelta(minutes=2), {'totalActivePower': 100.0, 'importedActivePowerHigh': 1, 'importedActivePowerLow': 5.0}),
            ])
        created, updated = _calculate_daily_electrical_data(self.device, day1, day2)
        self.assertEqual(created, 2)
        self.assertEqual(
            ElectricMeterIndicators.objects.filter(device=self.device, time_range='daily').count(), 2)

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

def _meter_row(**overrides):
    """Fila mínima válida para `compute_meter_indicators` (todas las columnas de
    METER_FIELDS presentes, en None salvo lo que se sobreescriba)."""
    row = {field: None for field in METER_FIELDS}
    row.update(overrides)
    return row


class MeterCurrentUnbalanceGateTests(SimpleTestCase):
    """Tests del gate de carga mínima + tope defensivo del desbalance/THD/TDD de
    corriente (corrección de la fórmula NEMA que se disparaba sin sentido físico a
    carga ~0, ver MIN_CURRENT_A_FOR_UNBALANCE en indicators/services/meter_calc.py)."""

    def test_desbalance_con_carga_real_se_calcula_normalmente(self):
        # avg = 10 A (>= umbral), max_deviation = 2 A -> 20% de desbalance real.
        rows = [_meter_row(currentPhaseA=8.0, currentPhaseB=10.0, currentPhaseC=12.0)]
        result = compute_meter_indicators(rows)
        self.assertAlmostEqual(result['max_current_unbalance_pct'], 20.0)

    def test_carga_casi_nula_con_fase_en_cero_queda_excluida(self):
        # avg = 0.2 A (< MIN_CURRENT_A_FOR_UNBALANCE): sin el gate, esta muestra
        # daría max_deviation(0.4)/avg(0.2)*100 = 200%, el artefacto reportado.
        self.assertLess(0.2, MIN_CURRENT_A_FOR_UNBALANCE)
        rows = [_meter_row(currentPhaseA=0.0, currentPhaseB=0.0, currentPhaseC=0.6)]
        result = compute_meter_indicators(rows)
        # Única muestra del día excluida por el gate -> sin datos válidos -> 0.
        self.assertEqual(result['max_current_unbalance_pct'], 0)

    def test_desbalance_extremo_con_carga_real_se_acota_a_100(self):
        # avg = 10.1667 A (>= umbral, carga real), pero max_deviation/avg ~ 195%:
        # el tope defensivo debe acotarlo a 100%, análogo al clamp de load_factor_pct.
        rows = [_meter_row(currentPhaseA=0.0, currentPhaseB=0.5, currentPhaseC=30.0)]
        result = compute_meter_indicators(rows)
        self.assertGreaterEqual((0.0 + 0.5 + 30.0) / 3, MIN_CURRENT_A_FOR_UNBALANCE)
        self.assertEqual(result['max_current_unbalance_pct'], 100.0)

    def test_thd_de_corriente_con_carga_nula_se_excluye(self):
        rows = [_meter_row(
            currentPhaseA=0.0, currentPhaseB=0.0, currentPhaseC=0.0,
            currentTHDPhaseA=250.0, currentTHDPhaseB=250.0, currentTHDPhaseC=250.0,
            currentTDDPhaseA=250.0, currentTDDPhaseB=250.0, currentTDDPhaseC=250.0,
        )]
        result = compute_meter_indicators(rows)
        self.assertEqual(result['max_current_thd_pct'], 0)
        self.assertEqual(result['max_current_tdd_pct'], 0)

    def test_thd_de_corriente_con_carga_real_se_incluye(self):
        rows = [_meter_row(
            currentPhaseA=10.0, currentPhaseB=10.0, currentPhaseC=10.0,
            currentTHDPhaseA=3.0, currentTHDPhaseB=2.5, currentTHDPhaseC=2.8,
            currentTDDPhaseA=2.1, currentTDDPhaseB=2.0, currentTDDPhaseC=1.9,
        )]
        result = compute_meter_indicators(rows)
        self.assertEqual(result['max_current_thd_pct'], 3.0)
        self.assertEqual(result['max_current_tdd_pct'], 2.1)

    def test_desbalance_de_voltaje_no_se_altera_por_el_gate(self):
        # El gate/cap es exclusivo de corriente; el voltaje conserva su fórmula original.
        rows = [_meter_row(
            currentPhaseA=0.0, currentPhaseB=0.0, currentPhaseC=0.0,
            voltagePhaseA=210.0, voltagePhaseB=220.0, voltagePhaseC=230.0,
        )]
        result = compute_meter_indicators(rows)
        self.assertAlmostEqual(result['max_voltage_unbalance_pct'], (10 / 220) * 100)
        self.assertEqual(result['max_current_unbalance_pct'], 0)


if __name__ == '__main__':
    import pytest  # import perezoso: solo requerido para ejecución standalone
    pytest.main([__file__])
