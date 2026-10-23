"""
Cálculo PURO de indicadores meteorológicos por día y por mes.

Extraído verbatim de tasks.py: reciben filas dict de `.values()` y devuelven el dict
de indicadores. Puras (no tocan la BD ni Celery). Descartan lecturas fuera de rango
físico plausible antes de promediar.
"""
import math

from indicators.services.date_ranges import COLOMBIA_TZ

# Rangos físicos de las lecturas (mismos en el diario, el horario y la gráfica del día).
IRRADIANCE_MAX_WM2 = 1100.0
DAYLIGHT_START_HOUR = 6
DAYLIGHT_END_HOUR = 18


def _local_hour(ts):
    """Hora de Bogotá de un datetime aware (Django devuelve UTC)."""
    try:
        return ts.astimezone(COLOMBIA_TZ).hour
    except (ValueError, AttributeError):
        return None


def _valid_irradiance(data):
    """Irradiancia (W/m²) de la fila si pasa el filtro físico del diario: 0–1100 W/m² y dentro de
    06–18 h de Bogotá. None si no pasa o no se midió."""
    irr = data['irradiance']
    if irr is None or not (0.0 <= float(irr) <= IRRADIANCE_MAX_WM2):
        return None
    hour = _local_hour(data['date'])
    if hour is not None and not (DAYLIGHT_START_HOUR <= hour < DAYLIGHT_END_HOUR):
        return None
    return float(irr)


def _in_range(value, low, high=None):
    if value is None:
        return None
    v = float(value)
    if v < low or (high is not None and v > high):
        return None
    return v


def circular_mean_deg(directions):
    """Media circular de direcciones en grados (0–360). La media aritmética de 350° y 10° da 180°
    (sur); la circular da 0° (norte). None si no hay direcciones o el viento no tiene dirección
    dominante (resultante nula)."""
    if not directions:
        return None
    s = sum(math.sin(math.radians(d)) for d in directions)
    c = sum(math.cos(math.radians(d)) for d in directions)
    if abs(s) < 1e-12 and abs(c) < 1e-12:
        return None
    return math.degrees(math.atan2(s, c)) % 360.0


def calculate_single_day_weather_indicators(measurements):
    """
    Calcula indicadores meteorológicos para un día específico.

    Recibe filas dict (v2: `.values('date', <columnas meteorológicas>)`);
    una columna NULL equivale a la clave ausente del antiguo jsonb.
    """
    if not measurements:
        return {}

    # Extraer datos de las mediciones
    irradiance_values = []
    temperature_values = []
    humidity_values = []
    wind_speed_values = []
    wind_direction_values = []
    precipitation_values = []

    # Se descartan lecturas fuera de rango físico (sensores saturados/averiados que
    # corrompían los promedios: irradiancia negativa o >1968 W/m², viento >400 km/h).
    for data in measurements:
        # Irradiancia (W/m²): rango físico 0–1100 y solo en horas de luz (06–18 local).
        # Fuera de ese horario un valor alto es un sensor pegado que inflaba la
        # acumulación diaria (llegaba a ~24 kWh/m² vs ~8 físico). Nariño es ~1°N, con
        # día solar estable ~06–18 todo el año, así que la ventana no recorta energía real.
        irr = _valid_irradiance(data)
        if irr is not None:
            irradiance_values.append(irr)

        # Temperatura (°C): rango plausible -20–60
        temp = data['temperature']
        if temp is not None and -20.0 <= float(temp) <= 60.0:
            temperature_values.append(float(temp))

        # Humedad (%): 0–100
        hum = data['humidity']
        if hum is not None and 0.0 <= float(hum) <= 100.0:
            humidity_values.append(float(hum))

        # Velocidad del viento (km/h): 0–150
        ws = data['windSpeed']
        if ws is not None and 0.0 <= float(ws) <= 150.0:
            wind_speed_values.append(float(ws))

        # Dirección del viento (°): 0–360
        wd = data['windDirection']
        if wd is not None and 0.0 <= float(wd) <= 360.0:
            wind_direction_values.append(float(wd))

        # Precipitación (cm/día): no negativa
        prec = data['precipitation']
        if prec is not None and float(prec) >= 0.0:
            precipitation_values.append(float(prec))
    
    # Calcular indicadores. Lo que no se midió queda en None («no disponible»), nunca en 0.
    indicators = {
        'daily_irradiance_kwh_m2': None,
        'daily_hsp_hours': None,
        'theoretical_pv_power_w': None,
        'avg_wind_speed_kmh': None,
        'daily_precipitation_cm': None,
        'avg_temperature_c': None,
        'max_temperature_c': None,
        'min_temperature_c': None,
        'avg_humidity_pct': None,
    }

    # 5.1. Irradiancia Acumulada Diaria (kWh/m²)
    if irradiance_values:
        # Fórmula: Suma de irradiance (W/m²) × (2/60) horas × (1/1000) kW/W
        # Cada lectura de 2 minutos se convierte a energía: W/m² × (2/60) h = Wh/m²
        # Luego se convierte a kWh/m² dividiendo por 1000
        total_irradiance_wh_m2 = sum(irradiance_values) * (2/60)  # Wh/m²
        indicators['daily_irradiance_kwh_m2'] = total_irradiance_wh_m2 / 1000  # kWh/m²
        
        # 5.2. Horas Solares Pico (HSP)
        # 1 HSP = 1 kWh/m²
        indicators['daily_hsp_hours'] = indicators['daily_irradiance_kwh_m2']
        
        # 5.5. Generación Fotovoltaica Potencia (teórica)
        # Potencia instantánea basada en irradiancia actual
        # Asumiendo eficiencia típica del 15-20% y área de 1 m²
        efficiency = 0.17  # 17% de eficiencia típica
        # Usar la irradiancia promedio del día para calcular potencia teórica
        avg_irradiance_wm2 = sum(irradiance_values) / len(irradiance_values)
        indicators['theoretical_pv_power_w'] = avg_irradiance_wm2 * efficiency  # W instantáneos
    
    # 5.3. Viento: Velocidad Media
    if wind_speed_values:
        indicators['avg_wind_speed_kmh'] = sum(wind_speed_values) / len(wind_speed_values)
        
        # Rosa de los vientos (distribución de direcciones)
        if wind_direction_values:
            indicators['wind_direction_distribution'] = calculate_wind_direction_distribution(wind_direction_values)
            indicators['wind_speed_distribution'] = calculate_wind_speed_distribution(wind_speed_values)
    
    # 5.4. Precipitación Acumulada
    if precipitation_values:
        # Si precipitation ya está en cm/día (acumulador diario), tomar el último valor
        # Si es una tasa instantánea, se deben sumar las lecturas de 2 minutos
        # Asumiendo que cm/día significa que es un acumulador de reinicio diario
        indicators['daily_precipitation_cm'] = precipitation_values[len(precipitation_values)-1] if precipitation_values else 0.0
    
    # Datos adicionales
    if temperature_values:
        indicators['avg_temperature_c'] = sum(temperature_values) / len(temperature_values)
        indicators['max_temperature_c'] = max(temperature_values)
        indicators['min_temperature_c'] = min(temperature_values)
    
    if humidity_values:
        indicators['avg_humidity_pct'] = sum(humidity_values) / len(humidity_values)
    
    # Metadatos
    indicators['measurement_count'] = len(measurements)
    indicators['last_measurement_date'] = measurements[len(measurements)-1]['date'] if measurements else None

    return indicators


def calculate_single_month_weather_indicators(measurements):
    """
    Calcula indicadores meteorológicos para un mes específico.
    """
    if not measurements:
        return {}
    
    # Agrupar por día y calcular promedios mensuales (filas dict v2)
    daily_indicators = []
    current_day = None
    day_measurements = []

    for measurement in measurements:
        # Día de Bogotá: `date.date()` daba el día UTC y partía cada día a las 19:00.
        day = measurement['date'].astimezone(COLOMBIA_TZ).date()
        if current_day != day:
            if day_measurements:
                daily_indicators.append(calculate_single_day_weather_indicators(day_measurements))
            current_day = day
            day_measurements = []
        day_measurements.append(measurement)
    
    # Procesar el último día
    if day_measurements:
        daily_indicators.append(calculate_single_day_weather_indicators(day_measurements))
    
    if not daily_indicators:
        return {}
    
    # Calcular promedios mensuales. Lo que ningún día midió queda en None, no en 0.
    monthly_indicators = {
        'daily_irradiance_kwh_m2': None, 'daily_hsp_hours': None, 'avg_wind_speed_kmh': None,
        'avg_temperature_c': None, 'avg_humidity_pct': None, 'daily_precipitation_cm': None,
        'max_temperature_c': None, 'min_temperature_c': None,
    }
    
    # Promedios de valores diarios (magnitudes intensivas: irradiancia media diaria,
    # HSP, viento, temperatura, humedad)
    for field in ['daily_irradiance_kwh_m2', 'daily_hsp_hours', 'avg_wind_speed_kmh', 'avg_temperature_c', 'avg_humidity_pct']:
        values = [ind.get(field, 0) for ind in daily_indicators if ind.get(field) is not None]
        if values:
            monthly_indicators[field] = sum(values) / len(values)

    # Precipitación mensual = ACUMULADA (suma de los diarios), no promedio
    # (indicators.md la define como acumulada). Antes se promediaba, subestimándola.
    precip_values = [ind.get('daily_precipitation_cm', 0) for ind in daily_indicators
                     if ind.get('daily_precipitation_cm') is not None]
    if precip_values:
        monthly_indicators['daily_precipitation_cm'] = sum(precip_values)
    
    # Valores máximos y mínimos
    for field in ['max_temperature_c', 'min_temperature_c']:
        values = [ind.get(field, 0) for ind in daily_indicators if ind.get(field) is not None]
        if values:
            if 'max' in field:
                monthly_indicators[field] = max(values)
            else:
                monthly_indicators[field] = min(values)
    
    # Metadatos
    monthly_indicators['measurement_count'] = sum(ind.get('measurement_count', 0) for ind in daily_indicators)
    monthly_indicators['last_measurement_date'] = measurements[len(measurements)-1]['date'] if measurements else None
    
    return monthly_indicators


def calculate_single_hour_weather_indicators(measurements):
    """
    Calcula indicadores meteorológicos para UNA hora (vista horaria y gráfica del día).

    Recibe filas dict de una sola hora (`.values('date', <columnas meteorológicas>)`) y devuelve
    el dict de campos de `HourlyWeatherIndicators`.

    Corrección de octubre de 2026:
    - aplica los mismos filtros físicos que el diario a todas las variables (antes solo a la
      irradiancia);
    - la dirección del viento es la media circular (antes la aritmética: 350° y 10° daban 180°);
    - lo que no se midió queda en None, no en 0. La irradiancia de una hora nocturna (fuera de
      06–18 h, donde el método la descarta) es 0,0 W/m².
    """
    irradiance_values = []
    temperature_values = []
    humidity_values = []
    wind_speed_values = []
    wind_direction_values = []
    precipitation_values = []
    daylight = False

    for data in measurements:
        hour = _local_hour(data['date'])
        if hour is None or DAYLIGHT_START_HOUR <= hour < DAYLIGHT_END_HOUR:
            daylight = True
        irr = _valid_irradiance(data)
        if irr is not None:
            irradiance_values.append(irr)
        for key, low, high, bucket in (
            ('temperature', -20.0, 60.0, temperature_values),
            ('humidity', 0.0, 100.0, humidity_values),
            ('windSpeed', 0.0, 150.0, wind_speed_values),
            ('windDirection', 0.0, 360.0, wind_direction_values),
            ('precipitation', 0.0, None, precipitation_values),
        ):
            v = _in_range(data[key], low, high)
            if v is not None:
                bucket.append(v)

    indicators = {}

    if irradiance_values:
        indicators['avg_irradiance_wm2'] = sum(irradiance_values) / len(irradiance_values)
        # Irradiación de la hora (kWh/m²): cada muestra de 2 min aporta W/m² × 2/60 h.
        indicators['irradiance_energy_kwh_m2'] = sum(irradiance_values) * (2 / 60) / 1000
    elif measurements and not daylight:
        indicators['avg_irradiance_wm2'] = 0.0      # hora nocturna
        indicators['irradiance_energy_kwh_m2'] = 0.0
    else:
        indicators['avg_irradiance_wm2'] = None
        indicators['irradiance_energy_kwh_m2'] = None

    if temperature_values:
        indicators['avg_temperature_c'] = sum(temperature_values) / len(temperature_values)
        indicators['max_temperature_c'] = max(temperature_values)
        indicators['min_temperature_c'] = min(temperature_values)
    else:
        indicators['avg_temperature_c'] = None
        indicators['max_temperature_c'] = None
        indicators['min_temperature_c'] = None

    indicators['avg_humidity_pct'] = (
        sum(humidity_values) / len(humidity_values) if humidity_values else None)
    indicators['avg_wind_speed_kmh'] = (
        sum(wind_speed_values) / len(wind_speed_values) if wind_speed_values else None)
    indicators['avg_wind_direction_deg'] = circular_mean_deg(wind_direction_values)
    # Precipitación: último valor de la hora (acumulador), mismo criterio que el diario.
    indicators['precipitation_cm'] = precipitation_values[-1] if precipitation_values else None

    indicators['measurement_count'] = len(measurements)

    return indicators


def calculate_single_day_weather_chart_data(measurements):
    """
    Calcula datos de gráficos para un día.

    Recibe filas dict de UN día de Bogotá (`.values('date', <columnas meteorológicas>)`).

    Corrección de octubre de 2026:
    - horas de Bogotá (antes `date.hour` en UTC, 5 h corridas);
    - `hourly_irradiance` es la media horaria con el filtro físico del diario, y
      `daily_irradiance_kwh_m2` es Σ muestras válidas × 2/60 / 1000, igual que el indicador diario
      (antes se sumaban las 24 medias horarias × 2/60: 30 veces menos);
    - los promedios del día salen de las muestras (no de 24 medias con las horas vacías en 0);
    - las horas sin datos quedan en None.
    """
    if not measurements:
        return {}

    hourly_measurements = {i: [] for i in range(24)}
    for data in measurements:
        hourly_measurements[data['date'].astimezone(COLOMBIA_TZ).hour].append(data)

    chart_data = {
        'hourly_irradiance': [],
        'hourly_temperature': [],
        'hourly_humidity': [],
        'hourly_wind_speed': [],
        'hourly_wind_direction': [],
        'hourly_precipitation': []
    }
    for hour in range(24):
        rows = hourly_measurements[hour]
        if not rows:
            for key in chart_data:
                chart_data[key].append(None)
            continue
        ind = calculate_single_hour_weather_indicators(rows)
        chart_data['hourly_irradiance'].append(ind['avg_irradiance_wm2'])
        chart_data['hourly_temperature'].append(ind['avg_temperature_c'])
        chart_data['hourly_humidity'].append(ind['avg_humidity_pct'])
        chart_data['hourly_wind_speed'].append(ind['avg_wind_speed_kmh'])
        chart_data['hourly_wind_direction'].append(ind['avg_wind_direction_deg'])
        chart_data['hourly_precipitation'].append(ind['precipitation_cm'])

    # Valores del día: los mismos del indicador diario (mismas muestras y filtros).
    day = calculate_single_day_weather_indicators(measurements)
    chart_data['daily_irradiance_kwh_m2'] = day['daily_irradiance_kwh_m2']
    chart_data['avg_daily_temperature_c'] = day['avg_temperature_c']
    chart_data['avg_daily_humidity_pct'] = day['avg_humidity_pct']
    chart_data['avg_daily_wind_speed_kmh'] = day['avg_wind_speed_kmh']
    chart_data['daily_precipitation_cm'] = day['daily_precipitation_cm']

    return chart_data


def calculate_wind_direction_distribution(wind_directions):
    """
    Calcula la distribución de direcciones del viento para la rosa de los vientos.
    """
    # Dividir en 8 direcciones principales (N, NE, E, SE, S, SW, W, NW)
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    direction_bins = {direction: 0 for direction in directions}
    
    for direction in wind_directions:
        # Convertir grados a dirección cardinal
        if 337.5 <= direction <= 360 or 0 <= direction < 22.5:
            direction_bins['N'] += 1
        elif 22.5 <= direction < 67.5:
            direction_bins['NE'] += 1
        elif 67.5 <= direction < 112.5:
            direction_bins['E'] += 1
        elif 112.5 <= direction < 157.5:
            direction_bins['SE'] += 1
        elif 157.5 <= direction < 202.5:
            direction_bins['S'] += 1
        elif 202.5 <= direction < 247.5:
            direction_bins['SW'] += 1
        elif 247.5 <= direction < 292.5:
            direction_bins['W'] += 1
        elif 292.5 <= direction < 337.5:
            direction_bins['NW'] += 1
    
    return direction_bins


def calculate_wind_speed_distribution(wind_speeds):
    """
    Calcula la distribución de velocidades del viento.
    """
    # Definir rangos de velocidad
    speed_ranges = {
        '0-5': 0,    # Calma
        '5-10': 0,   # Ligera
        '10-20': 0,  # Moderada
        '20-30': 0,  # Fuerte
        '30+': 0     # Muy fuerte
    }
    
    for speed in wind_speeds:
        if speed < 5:
            speed_ranges['0-5'] += 1
        elif speed < 10:
            speed_ranges['5-10'] += 1
        elif speed < 20:
            speed_ranges['10-20'] += 1
        elif speed < 30:
            speed_ranges['20-30'] += 1
        else:
            speed_ranges['30+'] += 1
    
    return speed_ranges


# ---------------------------------------------------------------------------------------------
# Irradiación diaria para el Performance Ratio (corrección de octubre de 2026)
# ---------------------------------------------------------------------------------------------

PR_IRRADIANCE_MAX_WM2 = 1400.0         # tope físico de una muestra (con realce por nubes)
PR_DAYLIGHT_START_HOUR = 6             # ventana diurna en hora de Bogotá: [06:00, 18:00)
PR_DAYLIGHT_END_HOUR = 18
PR_EXPECTED_DAYLIGHT_SAMPLES = 360     # 12 h × 30 muestras/h (Δt = 2 min)
PR_MIN_COVERAGE = 0.80                 # ≥ 80 % de las muestras diurnas esperadas
PR_MAX_DAILY_KWH_M2 = 8.0              # por encima, el día no es físico (sensor descalibrado)


def daily_irradiation_for_pr(rows):
    """Irradiación diurna por día de Bogotá para el PR, a partir de filas
    `.values('date', 'irradiance')` de la estación.

        H_día = Σ irradiancia (W/m²) de las muestras de 06:00–18:00 en [0, 1400] × (2/60) / 1000

    Devuelve {día: (H en kWh/m², válido)}; un día es válido si tiene al menos el 80 % de las 360
    muestras diurnas esperadas y 0 < H ≤ 8 kWh/m²."""
    sums = {}
    counts = {}
    for row in rows:
        irr = row['irradiance']
        local = row['date'].astimezone(COLOMBIA_TZ)
        if not (PR_DAYLIGHT_START_HOUR <= local.hour < PR_DAYLIGHT_END_HOUR):
            continue
        day = local.date()
        sums.setdefault(day, 0.0)
        counts.setdefault(day, 0)
        if irr is None or not (0.0 <= float(irr) <= PR_IRRADIANCE_MAX_WM2):
            continue
        sums[day] += float(irr)
        counts[day] += 1

    result = {}
    min_samples = PR_MIN_COVERAGE * PR_EXPECTED_DAYLIGHT_SAMPLES
    for day, total in sums.items():
        h = total * (2 / 60) / 1000
        # H = 0 con cobertura completa es un sensor muerto, no un día sin sol.
        ok = counts[day] >= min_samples and 0.0 < h <= PR_MAX_DAILY_KWH_M2
        result[day] = (h, ok)
    return result
