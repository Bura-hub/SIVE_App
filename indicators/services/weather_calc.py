"""
Cálculo PURO de indicadores meteorológicos por día y por mes (Ola 5).

Extraído verbatim de tasks.py: reciben filas dict de `.values()` y devuelven el dict
de indicadores. Puras (no tocan la BD ni Celery). Descartan lecturas fuera de rango
físico plausible antes de promediar (arreglo de datos de la Ola 1).
"""
from indicators.services.date_ranges import COLOMBIA_TZ


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
        irr = data['irradiance']
        if irr is not None and 0.0 <= float(irr) <= 1100.0:
            ts = data['date']
            try:
                hour = ts.astimezone(COLOMBIA_TZ).hour
            except (ValueError, AttributeError):
                hour = 12  # sin tz utilizable: no descartar por hora
            if 6 <= hour < 18:
                irradiance_values.append(float(irr))

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
    
    # Calcular indicadores
    indicators = {}
    
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
        day = measurement['date'].date()
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
    
    # Calcular promedios mensuales
    monthly_indicators = {}
    
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


def calculate_single_day_weather_chart_data(measurements):
    """
    Calcula datos de gráficos para un día específico.

    Recibe filas dict (v2: `.values('date', <columnas meteorológicas>)`).
    """
    if not measurements:
        return {}

    # Agrupar mediciones por hora
    hourly_data = {i: {'irradiance': [], 'temperature': [], 'humidity': [], 'wind_speed': [], 'wind_direction': [], 'precipitation': []} for i in range(24)}

    for data in measurements:
        hour = data['date'].hour

        if data['irradiance'] is not None:
            hourly_data[hour]['irradiance'].append(float(data['irradiance']))
        if data['temperature'] is not None:
            hourly_data[hour]['temperature'].append(float(data['temperature']))
        if data['humidity'] is not None:
            hourly_data[hour]['humidity'].append(float(data['humidity']))
        if data['windSpeed'] is not None:
            hourly_data[hour]['wind_speed'].append(float(data['windSpeed']))
        if data['windDirection'] is not None:
            hourly_data[hour]['wind_direction'].append(float(data['windDirection']))
        if data['precipitation'] is not None:
            hourly_data[hour]['precipitation'].append(float(data['precipitation']))
    
    # Calcular promedios por hora
    chart_data = {
        'hourly_irradiance': [],
        'hourly_temperature': [],
        'hourly_humidity': [],
        'hourly_wind_speed': [],
        'hourly_wind_direction': [],
        'hourly_precipitation': []
    }
    
    for hour in range(24):
        # Irradiancia promedio por hora
        if hourly_data[hour]['irradiance']:
            chart_data['hourly_irradiance'].append(sum(hourly_data[hour]['irradiance']) / len(hourly_data[hour]['irradiance']))
        else:
            chart_data['hourly_irradiance'].append(0)
        
        # Temperatura promedio por hora
        if hourly_data[hour]['temperature']:
            chart_data['hourly_temperature'].append(sum(hourly_data[hour]['temperature']) / len(hourly_data[hour]['temperature']))
        else:
            chart_data['hourly_temperature'].append(0)
        
        # Humedad promedio por hora
        if hourly_data[hour]['humidity']:
            chart_data['hourly_humidity'].append(sum(hourly_data[hour]['humidity']) / len(hourly_data[hour]['humidity']))
        else:
            chart_data['hourly_humidity'].append(0)
        
        # Velocidad del viento promedio por hora
        if hourly_data[hour]['wind_speed']:
            chart_data['hourly_wind_speed'].append(sum(hourly_data[hour]['wind_speed']) / len(hourly_data[hour]['wind_speed']))
        else:
            chart_data['hourly_wind_speed'].append(0)
        
        # Dirección del viento promedio por hora
        if hourly_data[hour]['wind_direction']:
            chart_data['hourly_wind_direction'].append(sum(hourly_data[hour]['wind_direction']) / len(hourly_data[hour]['wind_direction']))
        else:
            chart_data['hourly_wind_direction'].append(0)
        
        # Precipitación acumulada por hora (si es acumulador)
        if hourly_data[hour]['precipitation']:
            chart_data['hourly_precipitation'].append(hourly_data[hour]['precipitation'][len(hourly_data[hour]['precipitation'])-1])  # Último valor
        else:
            chart_data['hourly_precipitation'].append(0)
    
    # Calcular valores diarios
    chart_data['daily_irradiance_kwh_m2'] = sum(chart_data['hourly_irradiance']) * (2/60) / 1000  # kWh/m²
    chart_data['avg_daily_temperature_c'] = sum(chart_data['hourly_temperature']) / 24
    chart_data['avg_daily_humidity_pct'] = sum(chart_data['hourly_humidity']) / 24
    chart_data['avg_daily_wind_speed_kmh'] = sum(chart_data['hourly_wind_speed']) / 24
    chart_data['daily_precipitation_cm'] = chart_data['hourly_precipitation'][len(chart_data['hourly_precipitation'])-1] if chart_data['hourly_precipitation'] else 0
    
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
