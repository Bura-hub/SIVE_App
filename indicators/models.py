from django.db import models

class MonthlyConsumptionKPI(models.Model):
    """
    Modelo para almacenar los KPIs de consumo, generación y balance total mensual pre-calculados.
    Solo debe haber una instancia de este modelo.
    """
    total_consumption_current_month = models.FloatField(default=0.0, help_text="Consumo NETO acumulado del mes actual en kWh (importación − exportación, net metering).")
    total_consumption_previous_month = models.FloatField(default=0.0, help_text="Consumo NETO acumulado del mes anterior en kWh (importación − exportación, net metering).")

    total_gross_consumption_current_month = models.FloatField(default=0.0, help_text="Consumo BRUTO acumulado del mes actual en kWh (solo energía tomada de la red; inyección clampeada a 0).")
    total_gross_consumption_previous_month = models.FloatField(default=0.0, help_text="Consumo BRUTO acumulado del mes anterior en kWh (solo energía tomada de la red; inyección clampeada a 0).")

    total_generation_current_month = models.FloatField(default=0.0, help_text="Generación total acumulada del mes actual en kWh.")
    total_generation_previous_month = models.FloatField(default=0.0, help_text="Generación total acumulada del mes anterior en kWh.")

    avg_instantaneous_power_current_month = models.FloatField(default=0.0, help_text="Potencia instantánea promedio de inversores del mes actual en Watts.")
    avg_instantaneous_power_previous_month = models.FloatField(default=0.0, help_text="Potencia instantánea promedio de inversores del mes anterior en Watts.")

    avg_daily_temp_current_month = models.FloatField(default=0.0, help_text="Temperatura promedio diaria del mes actual en °C.")
    avg_daily_temp_previous_month = models.FloatField(default=0.0, help_text="Temperatura promedio diaria del mes anterior en °C.")

    avg_relative_humidity_current_month = models.FloatField(default=0.0, help_text="Humedad relativa promedio del mes actual en %RH.")
    avg_relative_humidity_previous_month = models.FloatField(default=0.0, help_text="Humedad relativa promedio del mes anterior en %RH.")

    # Nuevos campos para la velocidad del viento promedio (en km/h)
    avg_wind_speed_current_month = models.FloatField(default=0.0, help_text="Velocidad del viento promedio del mes actual en km/h.")
    avg_wind_speed_previous_month = models.FloatField(default=0.0, help_text="Velocidad del viento promedio del mes anterior en km/h.")

    # Nuevos campos para la irradiancia solar promedio (en W/m²)
    avg_irradiance_current_month = models.FloatField(default=0.0, help_text="Irradiancia solar promedio del mes actual en W/m².")
    avg_irradiance_previous_month = models.FloatField(default=0.0, help_text="Irradiancia solar promedio del mes anterior en W/m².")

    last_calculated = models.DateTimeField(auto_now=True, help_text="Fecha y hora de la última vez que se calculó este KPI.")

    class Meta:
        verbose_name = "KPI de Consumo, Generación y Balance Mensual"
        verbose_name_plural = "KPIs de Consumo, Generación y Balance Mensual"

    def __str__(self):
        return f"KPI Mensual (Actualizado: {self.last_calculated.strftime('%Y-%m-%d %H:%M')})"


class DailyChartData(models.Model):
    """
    Nuevo modelo para almacenar datos agregados diariamente,
    ideales para mostrar en gráficos.
    """
    date = models.DateField(unique=True, help_text="Fecha del registro.")
    daily_consumption = models.FloatField(default=0.0, help_text="Consumo NETO diario en kWh (importación − exportación, net metering).")
    daily_gross_consumption = models.FloatField(default=0.0, help_text="Consumo BRUTO diario en kWh (solo energía tomada de la red; inyección clampeada a 0).")
    daily_generation = models.FloatField(default=0.0, help_text="Generación total diaria en kWh.")  # Cambiar a kWh
    daily_balance = models.FloatField(default=0.0, help_text="Balance energético diario en kWh.")
    avg_daily_temp = models.FloatField(default=0.0, help_text="Temperatura promedio diaria en °C.")
    
    # Nuevos campos para velocidad del viento e irradiancia
    avg_wind_speed = models.FloatField(default=0.0, help_text="Velocidad del viento promedio diaria en km/h.")
    avg_irradiance = models.FloatField(default=0.0, help_text="Irradiancia solar promedio diaria en W/m².")

    class Meta:
        verbose_name = "Datos Diarios de Gráfico"
        verbose_name_plural = "Datos Diarios de Gráfico"
    
    def __str__(self):
        return f"Datos para {self.date.isoformat()}"


class ElectricMeterConsumption(models.Model):
    """
    Modelo para almacenar el consumo acumulado de energía por medidor eléctrico
    en diferentes rangos de tiempo (diario/mensual).
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='electric_consumption')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='electric_consumption')
    
    # Rangos de tiempo
    date = models.DateField(help_text="Fecha del registro (para datos diarios) o primer día del mes (para datos mensuales).")
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ], help_text="Tipo de rango de tiempo del registro.")
    
    # Datos de consumo
    cumulative_active_power = models.FloatField(default=0.0, help_text="Energía activa acumulada en kWh.")
    total_active_power = models.FloatField(default=0.0, help_text="Total de energía activa consumida en kWh.")
    peak_demand = models.FloatField(default=0.0, help_text="Demanda pico en kW.")
    avg_demand = models.FloatField(default=0.0, help_text="Demanda promedio en kW.")
    
    # Metadatos
    measurement_count = models.IntegerField(default=0, help_text="Número de mediciones procesadas.")
    last_measurement_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de la última medición procesada.")
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Consumo de Medidor Eléctrico"
        verbose_name_plural = "Consumos de Medidores Eléctricos"
        unique_together = ['device', 'date', 'time_range']
        indexes = [
            models.Index(fields=['device', 'date', 'time_range']),
            models.Index(fields=['institution', 'date', 'time_range']),
            models.Index(fields=['date', 'time_range']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date} ({self.get_time_range_display()})"


class ElectricMeterChartData(models.Model):
    """
    Modelo para almacenar datos de gráficos específicos por medidor eléctrico,
    optimizado para consultas de rangos de fechas.
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='chart_data')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='chart_data')
    date = models.DateField(help_text="Fecha del registro.")
    
    # Datos para gráficos
    hourly_consumption = models.JSONField(default=list, help_text="Consumo por hora del día en kWh.")
    daily_consumption = models.FloatField(default=0.0, help_text="Consumo total del día en kWh.")
    peak_hour = models.IntegerField(default=0, help_text="Hora del pico de consumo (0-23).")
    peak_value = models.FloatField(default=0.0, help_text="Valor del pico de consumo en kW.")
    
    # Metadatos
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Datos de Gráfico de Medidor Eléctrico"
        verbose_name_plural = "Datos de Gráficos de Medidores Eléctricos"
        unique_together = ['device', 'date']
        indexes = [
            models.Index(fields=['device', 'date']),
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date}"

# indicators/models.py    
class ElectricMeterEnergyConsumption(models.Model):
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE)
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE)
    date = models.DateField()
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ])
    
    # Energía importada (kWh)
    imported_energy_low = models.FloatField(default=0.0)  # kWh
    imported_energy_high = models.FloatField(default=0.0)  # MWh convertido a kWh
    total_imported_energy = models.FloatField(default=0.0)  # Total en kWh
    
    # Energía exportada (kWh)
    exported_energy_low = models.FloatField(default=0.0)  # kWh
    exported_energy_high = models.FloatField(default=0.0)  # MWh convertido a kWh
    total_exported_energy = models.FloatField(default=0.0)  # Total en kWh
    
    # Balance neto
    net_energy_consumption = models.FloatField(default=0.0)  # kWh
    
    # Metadatos
    measurement_count = models.IntegerField(default=0)
    last_measurement_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['device', 'institution', 'date', 'time_range']
        indexes = [
            models.Index(fields=['device', 'date', 'time_range']),
            models.Index(fields=['institution', 'date', 'time_range'])
        ]


class ElectricMeterIndicators(models.Model):
    """
    Modelo para almacenar todos los indicadores eléctricos calculados por medidor
    en diferentes rangos de tiempo (diario/mensual).
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='electric_indicators')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='electric_indicators')
    
    # Rangos de tiempo
    date = models.DateField(help_text="Fecha del registro (para datos diarios) o primer día del mes (para datos mensuales).")
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ], help_text="Tipo de rango de tiempo del registro.")
    
    # 3.2. Energía Consumida Acumulada
    imported_energy_kwh = models.FloatField(default=0.0, help_text="Energía importada total en kWh.")
    exported_energy_kwh = models.FloatField(default=0.0, help_text="Energía exportada total en kWh.")
    net_energy_consumption_kwh = models.FloatField(default=0.0, help_text="Energía neta consumida en kWh.")
    
    # 3.3. Demanda Pico
    peak_demand_kw = models.FloatField(default=0.0, help_text="Demanda pico en kW.")
    avg_demand_kw = models.FloatField(default=0.0, help_text="Demanda promedio en kW.")
    
    # 3.4. Factor de Carga
    load_factor_pct = models.FloatField(default=0.0, help_text="Factor de carga en porcentaje.")
    
    # 3.5. Factor de Potencia Promedio
    avg_power_factor = models.FloatField(default=0.0, help_text="Factor de potencia promedio.")
    
    # 3.6. Desbalance de Fases
    max_voltage_unbalance_pct = models.FloatField(default=0.0, help_text="Desbalance máximo de tensión en porcentaje.")
    max_current_unbalance_pct = models.FloatField(default=0.0, help_text="Desbalance máximo de corriente en porcentaje.")
    
    # 3.7. Distorsión Armónica Total (THD) y Demanda de Distorsión Total (TDD)
    max_voltage_thd_pct = models.FloatField(default=0.0, help_text="THD máximo de tensión en porcentaje.")
    max_current_thd_pct = models.FloatField(default=0.0, help_text="THD máximo de corriente en porcentaje.")
    max_current_tdd_pct = models.FloatField(default=0.0, help_text="TDD máximo de corriente en porcentaje.")
    
    # Metadatos
    measurement_count = models.IntegerField(default=0, help_text="Número de mediciones procesadas.")
    last_measurement_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de la última medición procesada.")
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Indicadores de Medidor Eléctrico"
        verbose_name_plural = "Indicadores de Medidores Eléctricos"
        unique_together = ['device', 'date', 'time_range']
        indexes = [
            models.Index(fields=['device', 'date', 'time_range']),
            models.Index(fields=['institution', 'date', 'time_range']),
            models.Index(fields=['date', 'time_range']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date} ({self.get_time_range_display()})"


class InverterIndicators(models.Model):
    """
    Modelo para almacenar todos los indicadores de inversores calculados
    en diferentes rangos de tiempo (diario/mensual).
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='inverter_indicators')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='inverter_indicators')
    
    # Rangos de tiempo
    date = models.DateField(help_text="Fecha del registro (para datos diarios) o primer día del mes (para datos mensuales).")
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ], help_text="Tipo de rango de tiempo del registro.")
    
    # 4.1. Eficiencia de Conversión DC-AC
    dc_ac_efficiency_pct = models.FloatField(default=0.0, help_text="Eficiencia de conversión DC-AC en porcentaje.")
    energy_ac_daily_kwh = models.FloatField(default=0.0, help_text="Energía AC generada diaria en kWh.")
    energy_dc_daily_kwh = models.FloatField(default=0.0, help_text="Energía DC recibida diaria en kWh.")
    
    # 4.2. Energía Total Generada
    total_generated_energy_kwh = models.FloatField(default=0.0, help_text="Energía total generada en kWh.")
    
    # 4.3. Performance Ratio (PR)
    performance_ratio_pct = models.FloatField(default=0.0, help_text="Performance Ratio en porcentaje.")
    reference_energy_kwh = models.FloatField(default=0.0, help_text="Energía de referencia en kWh.")
    
    # 4.4. Curva de Generación vs. Irradiancia/Temperatura
    avg_irradiance_wm2 = models.FloatField(default=0.0, help_text="Irradiancia promedio en W/m².")
    avg_temperature_c = models.FloatField(default=0.0, help_text="Temperatura promedio en °C.")
    max_power_w = models.FloatField(default=0.0, help_text="Potencia máxima generada en W.")
    min_power_w = models.FloatField(default=0.0, help_text="Potencia mínima generada en W.")
    
    # 4.5. Factor de Potencia y Calidad de Inyección
    avg_power_factor_pct = models.FloatField(default=0.0, help_text="Factor de potencia promedio en porcentaje.")
    avg_reactive_power_var = models.FloatField(default=0.0, help_text="Potencia reactiva promedio en VAr.")
    avg_apparent_power_va = models.FloatField(default=0.0, help_text="Potencia aparente promedio en VA.")
    avg_frequency_hz = models.FloatField(default=0.0, help_text="Frecuencia promedio en Hz.")
    frequency_stability_pct = models.FloatField(default=0.0, help_text="Estabilidad de frecuencia en porcentaje.")
    
    # 4.6. Desbalance de Fases en Inyección
    max_voltage_unbalance_pct = models.FloatField(default=0.0, help_text="Desbalance máximo de tensión en porcentaje.")
    max_current_unbalance_pct = models.FloatField(default=0.0, help_text="Desbalance máximo de corriente en porcentaje.")
    
    # 4.7. Análisis de Anomalías Operativas
    anomaly_score = models.FloatField(default=0.0, help_text="Puntuación de anomalías (0-100, 0=sin anomalías).")
    anomaly_details = models.JSONField(default=dict, help_text="Detalles de anomalías detectadas.")
    
    # Metadatos
    measurement_count = models.IntegerField(default=0, help_text="Número de mediciones procesadas.")
    last_measurement_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de la última medición procesada.")
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Indicadores de Inversor"
        verbose_name_plural = "Indicadores de Inversores"
        unique_together = ['device', 'date', 'time_range']
        indexes = [
            models.Index(fields=['device', 'date', 'time_range']),
            models.Index(fields=['institution', 'date', 'time_range']),
            models.Index(fields=['date', 'time_range']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date} ({self.get_time_range_display()})"


class InverterChartData(models.Model):
    """
    Modelo para almacenar datos de gráficos específicos por inversor,
    optimizado para consultas de rangos de fechas.
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='inverter_chart_data')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='inverter_chart_data')
    date = models.DateField(help_text="Fecha del registro.")
    
    # Datos para gráficos de eficiencia
    hourly_efficiency = models.JSONField(default=list, help_text="Eficiencia por hora del día en porcentaje.")
    hourly_generation = models.JSONField(default=list, help_text="Generación por hora del día en kWh.")
    hourly_irradiance = models.JSONField(default=list, help_text="Irradiancia por hora del día en W/m².")
    hourly_temperature = models.JSONField(default=list, help_text="Temperatura por hora del día en °C.")
    
    # Datos para gráficos de potencia
    hourly_dc_power = models.JSONField(default=list, help_text="Potencia DC por hora del día en W.")
    hourly_ac_power = models.JSONField(default=list, help_text="Potencia AC por hora del día en W.")
    
    # Metadatos
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Datos de Gráfico de Inversor"
        verbose_name_plural = "Datos de Gráficos de Inversores"
        unique_together = ['device', 'date']
        indexes = [
            models.Index(fields=['device', 'date']),
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date}"


class WeatherStationIndicators(models.Model):
    """
    Modelo para almacenar todos los indicadores de estaciones meteorológicas calculados
    en diferentes rangos de tiempo (diario/mensual).
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='weather_indicators')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='weather_indicators')
    
    # Rangos de tiempo
    date = models.DateField(help_text="Fecha del registro (para datos diarios) o primer día del mes (para datos mensuales).")
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ], help_text="Tipo de rango de tiempo del registro.")
    
    # 5.1. Irradiancia Acumulada Diaria
    daily_irradiance_kwh_m2 = models.FloatField(default=0.0, help_text="Irradiancia acumulada diaria en kWh/m².")
    
    # 5.2. Horas Solares Pico (HSP)
    daily_hsp_hours = models.FloatField(default=0.0, help_text="Horas solares pico diarias.")
    
    # 5.3. Viento: Velocidad Media y Rosa de los Vientos
    avg_wind_speed_kmh = models.FloatField(default=0.0, help_text="Velocidad media del viento en km/h.")
    wind_direction_distribution = models.JSONField(default=dict, help_text="Distribución de direcciones del viento (rosa de los vientos).")
    wind_speed_distribution = models.JSONField(default=dict, help_text="Distribución de velocidades del viento.")
    
    # 5.4. Precipitación Acumulada
    daily_precipitation_cm = models.FloatField(default=0.0, help_text="Precipitación acumulada diaria en cm.")
    
    # 5.5. Generación Fotovoltaica Potencia (basada en irradiancia)
    theoretical_pv_power_w = models.FloatField(default=0.0, help_text="Potencia fotovoltaica teórica basada en irradiancia en W.")
    
    # Datos adicionales para análisis
    avg_temperature_c = models.FloatField(default=0.0, help_text="Temperatura promedio en °C.")
    avg_humidity_pct = models.FloatField(default=0.0, help_text="Humedad relativa promedio en %.")
    max_temperature_c = models.FloatField(default=0.0, help_text="Temperatura máxima en °C.")
    min_temperature_c = models.FloatField(default=0.0, help_text="Temperatura mínima en °C.")
    
    # Metadatos
    measurement_count = models.IntegerField(default=0, help_text="Número de mediciones procesadas.")
    last_measurement_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de la última medición procesada.")
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Indicadores de Estación Meteorológica"
        verbose_name_plural = "Indicadores de Estaciones Meteorológicas"
        unique_together = ['device', 'date', 'time_range']
        indexes = [
            models.Index(fields=['device', 'date', 'time_range']),
            models.Index(fields=['institution', 'date', 'time_range']),
            models.Index(fields=['date', 'time_range']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date} ({self.get_time_range_display()})"


class WeatherStationChartData(models.Model):
    """
    Modelo para almacenar datos de gráficos específicos por estación meteorológica,
    optimizado para consultas de rangos de fechas.
    """
    device = models.ForeignKey('scada_proxy.Device', on_delete=models.CASCADE, related_name='weather_chart_data')
    institution = models.ForeignKey('scada_proxy.Institution', on_delete=models.CASCADE, related_name='weather_chart_data')
    date = models.DateField(help_text="Fecha del registro.")
    
    # Datos para gráficos de irradiancia
    hourly_irradiance = models.JSONField(default=list, help_text="Irradiancia por hora del día en W/m².")
    daily_irradiance_kwh_m2 = models.FloatField(default=0.0, help_text="Irradiancia acumulada diaria en kWh/m².")
    
    # Datos para gráficos de temperatura
    hourly_temperature = models.JSONField(default=list, help_text="Temperatura por hora del día en °C.")
    avg_daily_temperature_c = models.FloatField(default=0.0, help_text="Temperatura promedio diaria en °C.")
    
    # Datos para gráficos de humedad
    hourly_humidity = models.JSONField(default=list, help_text="Humedad por hora del día en %.")
    avg_daily_humidity_pct = models.FloatField(default=0.0, help_text="Humedad promedio diaria en %.")
    
    # Datos para gráficos de viento
    hourly_wind_speed = models.JSONField(default=list, help_text="Velocidad del viento por hora del día en km/h.")
    hourly_wind_direction = models.JSONField(default=list, help_text="Dirección del viento por hora del día en grados.")
    avg_daily_wind_speed_kmh = models.FloatField(default=0.0, help_text="Velocidad promedio del viento diaria en km/h.")
    
    # Datos para gráficos de precipitación
    hourly_precipitation = models.JSONField(default=list, help_text="Precipitación por hora del día en cm.")
    daily_precipitation_cm = models.FloatField(default=0.0, help_text="Precipitación acumulada diaria en cm.")
    
    # Metadatos
    calculated_at = models.DateTimeField(auto_now=True, help_text="Fecha y hora del cálculo.")
    
    class Meta:
        verbose_name = "Datos de Gráfico de Estación Meteorológica"
        verbose_name_plural = "Datos de Gráficos de Estaciones Meteorológicas"
        unique_together = ['device', 'date']
        indexes = [
            models.Index(fields=['device', 'date']),
            models.Index(fields=['institution', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.device.name} - {self.date}"


class GeneratedReport(models.Model):
    """
    Modelo para almacenar información sobre reportes generados
    """
    task_id = models.CharField(max_length=255, unique=True, help_text="ID de la tarea de Celery")
    user_id = models.IntegerField(help_text="ID del usuario que solicitó el reporte")
    
    # Información del reporte
    report_type = models.CharField(max_length=100, help_text="Tipo de reporte generado")
    category = models.CharField(max_length=50, help_text="Categoría de dispositivo")
    institution_id = models.IntegerField(help_text="ID de la institución")
    institution_name = models.CharField(max_length=255, help_text="Nombre de la institución")
    devices = models.JSONField(default=list, help_text="Lista de IDs de dispositivos")
    
    # Configuración del reporte
    time_range = models.CharField(max_length=20, choices=[
        ('daily', 'Diario'),
        ('monthly', 'Mensual')
    ], help_text="Rango de tiempo del reporte")
    start_date = models.DateField(help_text="Fecha de inicio del reporte")
    end_date = models.DateField(help_text="Fecha de fin del reporte")
    format = models.CharField(max_length=10, choices=[
        ('CSV', 'CSV'),
        ('PDF', 'PDF'),
        ('Excel', 'Excel')
    ], help_text="Formato del reporte")
    
    # Estado y resultados
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido')
    ], default='pending', help_text="Estado de generación del reporte")
    
    # Información del archivo generado
    file_path = models.CharField(max_length=500, null=True, blank=True, help_text="Ruta del archivo generado")
    file_size = models.CharField(max_length=20, null=True, blank=True, help_text="Tamaño del archivo (ej: '2.5 MB')")
    record_count = models.IntegerField(default=0, help_text="Número de registros en el reporte")
    
    # Metadatos
    error_message = models.TextField(null=True, blank=True, help_text="Mensaje de error si falló la generación")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Fecha de creación de la solicitud")
    updated_at = models.DateTimeField(auto_now=True, help_text="Fecha de última actualización")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="Fecha de finalización")
    
    class Meta:
        verbose_name = "Reporte Generado"
        verbose_name_plural = "Reportes Generados"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', 'status']),
            models.Index(fields=['institution_id', 'category']),
            models.Index(fields=['created_at']),
            models.Index(fields=['task_id']),
        ]
    
    def __str__(self):
        return f"Reporte {self.report_type} - {self.institution_name} ({self.get_status_display()})"
    
    def get_file_size_display(self):
        """Retorna el tamaño del archivo en formato legible"""
        if not self.file_size:
            return "N/A"
        return self.file_size
    
    def get_record_count_display(self):
        """Retorna el número de registros en formato legible"""
        if self.record_count == 0:
            return "N/A"
        return f"{self.record_count:,}"
    
    def get_duration_display(self):
        """Retorna la duración de generación en formato legible"""
        if not self.completed_at:
            return "En proceso"
        
        duration = self.completed_at - self.created_at
        if duration.total_seconds() < 60:
            return f"{int(duration.total_seconds())}s"
        elif duration.total_seconds() < 3600:
            return f"{int(duration.total_seconds() / 60)}m"
        else:
            return f"{int(duration.total_seconds() / 3600)}h {int((duration.total_seconds() % 3600) / 60)}m"