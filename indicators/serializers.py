from rest_framework import serializers
from .models import MonthlyConsumptionKPI, DailyChartData, ElectricMeterIndicators, InverterIndicators, InverterChartData, WeatherStationIndicators, WeatherStationChartData

class MonthlyConsumptionKPISerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyConsumptionKPI
        fields = '__all__'

class DailyChartDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyChartData
        fields = '__all__'

# Serializer para el endpoint de cálculo de medidores eléctricos
class ElectricMeterCalculationRequestSerializer(serializers.Serializer):
    time_range = serializers.ChoiceField(
        choices=[('daily', 'Diario'), ('monthly', 'Mensual')],
        default='daily',
        help_text="Rango de tiempo para el cálculo: 'daily' o 'monthly'"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio en formato YYYY-MM-DD"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin en formato YYYY-MM-DD"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID específico del medidor (opcional)"
    )

# Serializer para la respuesta del cálculo de medidores eléctricos
class ElectricMeterCalculationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(
        help_text="Indica si el cálculo se ejecutó exitosamente"
    )
    message = serializers.CharField(
        help_text="Mensaje descriptivo del resultado del cálculo"
    )
    task_id = serializers.CharField(
        help_text="ID de la tarea asíncrona ejecutada"
    )
    time_range = serializers.CharField(
        help_text="Rango de tiempo del cálculo (daily/monthly)"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio del período calculado"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin del período calculado"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución procesada"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID del medidor específico (si se especificó)"
    )
    processed_records = serializers.IntegerField(
        help_text="Número de registros procesados"
    )
    estimated_completion_time = serializers.CharField(
        help_text="Tiempo estimado de finalización de la tarea"
    )

class ElectricMeterIndicatorsSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    time_range_display = serializers.CharField(source='get_time_range_display', read_only=True)
    
    class Meta:
        model = ElectricMeterIndicators
        fields = [
            'id', 'device', 'device_name', 'institution', 'institution_name',
            'date', 'time_range', 'time_range_display',
            'imported_energy_kwh', 'exported_energy_kwh', 'net_energy_consumption_kwh',
            'peak_demand_kw', 'avg_demand_kw', 'load_factor_pct', 'avg_power_factor',
            'max_voltage_unbalance_pct', 'max_current_unbalance_pct',
            'max_voltage_thd_pct', 'max_current_thd_pct', 'max_current_tdd_pct',
            'measurement_count', 'last_measurement_date', 'calculated_at'
        ]
        read_only_fields = ['calculated_at']


class InverterIndicatorsSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    time_range_display = serializers.CharField(source='get_time_range_display', read_only=True)
    
    class Meta:
        model = InverterIndicators
        fields = [
            'id', 'device', 'device_name', 'institution', 'institution_name',
            'date', 'time_range', 'time_range_display',
            'dc_ac_efficiency_pct', 'energy_ac_daily_kwh', 'energy_dc_daily_kwh',
            'total_generated_energy_kwh', 'performance_ratio_pct', 'reference_energy_kwh',
            'avg_irradiance_wm2', 'avg_temperature_c', 'max_power_w', 'min_power_w',
            'avg_power_factor_pct', 'avg_reactive_power_var', 'avg_apparent_power_va',
            'avg_frequency_hz', 'frequency_stability_pct',
            'max_voltage_unbalance_pct', 'max_current_unbalance_pct',
            'anomaly_score', 'anomaly_details',
            'measurement_count', 'last_measurement_date', 'calculated_at'
        ]
        read_only_fields = ['calculated_at']


class InverterChartDataSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    
    class Meta:
        model = InverterChartData
        fields = [
            'id', 'device', 'device_name', 'institution', 'institution_name',
            'date', 'hourly_efficiency', 'hourly_generation', 'hourly_irradiance',
            'hourly_temperature', 'hourly_dc_power', 'hourly_ac_power',
            'calculated_at'
        ]
        read_only_fields = ['calculated_at']


class InverterCalculationRequestSerializer(serializers.Serializer):
    time_range = serializers.ChoiceField(
        choices=[('daily', 'Diario'), ('monthly', 'Mensual')],
        default='daily',
        help_text="Rango de tiempo para el cálculo: 'daily' o 'monthly'"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio en formato YYYY-MM-DD"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin en formato YYYY-MM-DD"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID específico del inversor (opcional)"
    )


class InverterCalculationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(
        help_text="Indica si el cálculo se ejecutó exitosamente"
    )
    message = serializers.CharField(
        help_text="Mensaje descriptivo del resultado del cálculo"
    )
    task_id = serializers.CharField(
        help_text="ID de la tarea asíncrona ejecutada"
    )
    time_range = serializers.CharField(
        help_text="Rango de tiempo del cálculo (daily/monthly)"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio del período calculado"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin del período calculado"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución procesada"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID del inversor específico (si se especificó)"
    )
    processed_records = serializers.IntegerField(
        help_text="Número de registros procesados"
    )
    estimated_completion_time = serializers.CharField(
        help_text="Tiempo estimado de finalización de la tarea"
    )

# Serializers para estaciones meteorológicas
class WeatherStationIndicatorsSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    
    class Meta:
        model = WeatherStationIndicators
        fields = [
            'id', 'device', 'device_name', 'institution', 'institution_name',
            'date', 'time_range', 'daily_irradiance_kwh_m2', 'daily_hsp_hours',
            'avg_wind_speed_kmh', 'wind_direction_distribution', 'wind_speed_distribution',
            'daily_precipitation_cm', 'theoretical_pv_power_w', 'avg_temperature_c',
            'avg_humidity_pct', 'max_temperature_c', 'min_temperature_c',
            'measurement_count', 'last_measurement_date', 'calculated_at'
        ]


class WeatherStationChartDataSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    
    class Meta:
        model = WeatherStationChartData
        fields = [
            'id', 'device', 'device_name', 'institution', 'institution_name',
            'date', 'hourly_irradiance', 'daily_irradiance_kwh_m2',
            'hourly_temperature', 'avg_daily_temperature_c', 'hourly_humidity',
            'avg_daily_humidity_pct', 'hourly_wind_speed', 'hourly_wind_direction',
            'avg_daily_wind_speed_kmh', 'hourly_precipitation', 'daily_precipitation_cm',
            'calculated_at'
        ]


# Serializer para la solicitud de cálculo de estaciones meteorológicas
class WeatherStationCalculationRequestSerializer(serializers.Serializer):
    time_range = serializers.ChoiceField(
        choices=[('daily', 'Diario'), ('monthly', 'Mensual')],
        default='daily',
        help_text="Rango de tiempo para el cálculo: 'daily' o 'monthly'"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio en formato YYYY-MM-DD"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin en formato YYYY-MM-DD"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID específico de la estación meteorológica (opcional)"
    )


# Serializer para la respuesta del cálculo de estaciones meteorológicas
class WeatherStationCalculationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(
        help_text="Indica si el cálculo se ejecutó exitosamente"
    )
    message = serializers.CharField(
        help_text="Mensaje descriptivo del resultado del cálculo"
    )
    task_id = serializers.CharField(
        help_text="ID de la tarea asíncrona ejecutada"
    )
    time_range = serializers.CharField(
        help_text="Rango de tiempo del cálculo (daily/monthly)"
    )
    start_date = serializers.DateField(
        help_text="Fecha de inicio del período calculado"
    )
    end_date = serializers.DateField(
        help_text="Fecha de fin del período calculado"
    )
    institution_id = serializers.IntegerField(
        help_text="ID de la institución procesada"
    )
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID de la estación meteorológica específica (si se especificó)"
    )
    processed_records = serializers.IntegerField(
        help_text="Número de registros procesados"
    )
    estimated_completion_time = serializers.CharField(
        help_text="Tiempo estimado de finalización de la tarea"
    )

class DashboardChartUnitsSerializer(serializers.Serializer):
    """Unidades (ya escaladas) de cada punto del gráfico del dashboard."""
    consumption = serializers.CharField()
    generation = serializers.CharField()
    balance = serializers.CharField()
    temperature = serializers.CharField()
    wind_speed = serializers.CharField()
    irradiance = serializers.CharField()


class DashboardChartPointSerializer(serializers.Serializer):
    """Un punto (día) del gráfico del dashboard (ChartDataView). Los valores de energía
    vienen ya escalados a la unidad de `units`. Reemplaza el schema inline del @extend_schema
    y hace explícita la forma de la respuesta (Ola 5)."""
    date = serializers.CharField()
    daily_consumption = serializers.FloatField()
    daily_generation = serializers.FloatField()
    daily_balance = serializers.FloatField()
    avg_daily_temp = serializers.FloatField(allow_null=True)
    avg_wind_speed = serializers.FloatField()
    avg_irradiance = serializers.FloatField()
    units = DashboardChartUnitsSerializer()
