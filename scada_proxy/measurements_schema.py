"""
Catálogo canónico de métricas por categoría de dispositivo (esquema v2).

Fuente única de verdad para los modelos MeterMeasurement, InverterMeasurement
y WeatherStationMeasurement: los campos de esos modelos se generan desde estas
listas (ver models.py), y la ingesta filtra las claves del connector contra
ellas. Los nombres son las claves EXACTAS (camelCase) que entrega el SCADA
connector — sin capa de mapeo.

Verificado contra producción (jul-2026): el catálogo es idéntico en todo el
histórico (muestras de 2025-03, 2025-10 y 2026-06) y todos los valores son
JSON number. Si el connector añade una métrica nueva, agregarla aquí y crear
la migración correspondiente (la ingesta ignora claves desconocidas y lo
registra en el log).
"""

# Claves de la categoría "electricMeter" (54)
METER_METRICS = [
    'activePowerPhaseA', 'activePowerPhaseB', 'activePowerPhaseC',
    'apparentPowerHigh', 'apparentPowerLow',
    'apparentPowerPhaseA', 'apparentPowerPhaseB', 'apparentPowerPhaseC',
    'cumulativeActivePower', 'cumulativeApparentPower',
    'currentActivePowerDemand', 'currentApparentPowerDemand',
    'currentPhaseA', 'currentPhaseB', 'currentPhaseC',
    'currentTDDPhaseA', 'currentTDDPhaseB', 'currentTDDPhaseC',
    'currentTHDPhaseA', 'currentTHDPhaseB', 'currentTHDPhaseC',
    'exportedActivePowerHigh', 'exportedActivePowerLow',
    'frequency',
    'importedActivePowerHigh', 'importedActivePowerLow',
    'maxActivePowerDemand', 'maxApparentPowerDemand',
    'maxCurrentPhaseA', 'maxCurrentPhaseB', 'maxCurrentPhaseC',
    'negativeReactivePowerHigh', 'negativeReactivePowerLow',
    'neutralCurrent', 'outputStatus',
    'positiveReactivePowerHigh', 'positiveReactivePowerLow',
    'powerFactorMaxImportedApparentPower',
    'powerFactorPhaseA', 'powerFactorPhaseB', 'powerFactorPhaseC',
    'reactivePowerPhaseA', 'reactivePowerPhaseB', 'reactivePowerPhaseC',
    'totalActivePower', 'totalApparentPower', 'totalPowerFactor',
    'totalReactivePower',
    'voltagePhaseA', 'voltagePhaseB', 'voltagePhaseC',
    'voltageTHDPhaseA', 'voltageTHDPhaseB', 'voltageTHDPhaseC',
]

# Claves de la categoría "inverter" (18)
INVERTER_METRICS = [
    'acCurrentPhaseA', 'acCurrentPhaseB', 'acCurrentPhaseC',
    'acFrequency', 'acPower', 'acTotalCurrent',
    'acVoltagePhaseA', 'acVoltagePhaseB', 'acVoltagePhaseC',
    'apparentPower',
    'dcCurrent', 'dcPower', 'dcVoltage',
    'phaseVoltagePhaseAB', 'phaseVoltagePhaseBC', 'phaseVoltagePhaseCA',
    'powerFactor', 'reactivePower',
]

# Claves de la categoría "weatherStation" (7)
WEATHER_METRICS = [
    'batteryVoltage', 'humidity', 'irradiance', 'precipitation',
    'temperature', 'windDirection', 'windSpeed',
]

# Nombre de categoría (DeviceCategory.name) → lista de métricas
CATEGORY_METRICS = {
    'electricMeter': METER_METRICS,
    'inverter': INVERTER_METRICS,
    'weatherStation': WEATHER_METRICS,
}

_CATEGORY_METRICS_LOWER = {k.lower(): v for k, v in CATEGORY_METRICS.items()}


def metrics_for_category(category_name):
    """Lista de métricas de una categoría, o None si es desconocida.

    Case-insensitive, igual que los filtros `category__name__iexact` que usa
    todo el proyecto.
    """
    return _CATEGORY_METRICS_LOWER.get((category_name or '').lower())
