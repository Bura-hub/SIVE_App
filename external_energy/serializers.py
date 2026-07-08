from rest_framework import serializers
from .models import (
    EnergyPrice, 
    EnergySavings, 
    EnergyPriceForecast, 
    EnergyMarketData, 
    EnergyAlert
)


class EnergyPriceSerializer(serializers.ModelSerializer):
    """Serializer para precios de energía"""
    
    class Meta:
        model = EnergyPrice
        fields = [
            'id', 'date', 'price_per_kwh', 'source', 'region', 
            'created_at', 'updated_at'
        ]


class EnergySavingsSerializer(serializers.ModelSerializer):
    """Serializer para ahorros de energía"""
    
    class Meta:
        model = EnergySavings
        fields = [
            'id', 'date', 'total_consumed_kwh', 'total_generated_kwh',
            'average_price_kwh', 'total_savings_cop', 'savings_percentage',
            'self_consumption_percentage', 'excess_energy_kwh',
            'created_at', 'updated_at'
        ]


class EnergyPriceForecastSerializer(serializers.ModelSerializer):
    """Serializer para pronósticos de precios"""
    
    class Meta:
        model = EnergyPriceForecast
        fields = [
            'id', 'date', 'predicted_price_kwh', 'confidence_level',
            'source', 'algorithm', 'created_at'
        ]


class EnergyMarketDataSerializer(serializers.ModelSerializer):
    """Serializer para datos del mercado de energía"""
    
    class Meta:
        model = EnergyMarketData
        fields = [
            'id', 'date', 'demand_mw', 'supply_mw', 'hydro_percentage',
            'thermal_percentage', 'renewable_percentage', 'market_price_cop_mwh',
            'created_at'
        ]


class EnergyAlertSerializer(serializers.ModelSerializer):
    """Serializer para alertas de energía"""
    
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = EnergyAlert
        fields = [
            'id', 'alert_type', 'alert_type_display', 'severity', 'severity_display',
            'title', 'description', 'affected_date', 'is_active', 'created_at', 'resolved_at'
        ]


class ExternalEnergySummarySerializer(serializers.Serializer):
    """Serializer para resumen de datos externos de energía"""
    
    # Datos de precios
    average_price = serializers.DecimalField(max_digits=8, decimal_places=4)
    max_price = serializers.DecimalField(max_digits=8, decimal_places=4)
    min_price = serializers.DecimalField(max_digits=8, decimal_places=4)
    price_variation = serializers.DecimalField(max_digits=5, decimal_places=2)
    price_trend = serializers.CharField(max_length=20)
    price_history = serializers.ListField(child=serializers.DictField())
    price_forecast = serializers.ListField(child=serializers.DictField())
    
    # Alertas
    alerts = serializers.ListField(child=serializers.CharField())
    
    # Métricas del mercado
    market_demand = serializers.DecimalField(max_digits=10, decimal_places=2)
    market_supply = serializers.DecimalField(max_digits=10, decimal_places=2)
    renewable_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    source = serializers.CharField(max_length=20, required=False, default='XM')


class EnergySavingsSummarySerializer(serializers.Serializer):
    """Serializer para resumen de ahorros de energía"""
    
    # Totales
    total_consumed = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_generated = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_savings = serializers.DecimalField(max_digits=12, decimal_places=2)
    avoided_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Porcentajes
    savings_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    self_consumption = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Métricas adicionales
    excess_energy = serializers.DecimalField(max_digits=10, decimal_places=2)
    capacity_factor = serializers.DecimalField(max_digits=5, decimal_places=2)
    roi = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Datos mensuales
    monthly_savings = serializers.ListField(child=serializers.DictField())
