from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class EnergyPrice(models.Model):
    """Modelo para almacenar precios de energía desde fuentes externas"""
    
    date = models.DateField(unique=True)
    price_per_kwh = models.DecimalField(
        max_digits=8, 
        decimal_places=4,
        validators=[MinValueValidator(0)]
    )
    source = models.CharField(max_length=100, default='XM')  # XM, CREG, etc.
    region = models.CharField(max_length=100, default='Colombia')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Precio de Energía'
        verbose_name_plural = 'Precios de Energía'
    
    def __str__(self):
        return f"{self.date} - {self.price_per_kwh} COP/kWh"


class EnergySavings(models.Model):
    """Modelo para calcular y almacenar ahorros de energía"""
    
    date = models.DateField(unique=True)
    total_consumed_kwh = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    total_generated_kwh = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    average_price_kwh = models.DecimalField(
        max_digits=8, 
        decimal_places=4,
        validators=[MinValueValidator(0)]
    )
    total_savings_cop = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    savings_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    self_consumption_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    excess_energy_kwh = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Ahorro de Energía'
        verbose_name_plural = 'Ahorros de Energía'
    
    def __str__(self):
        return f"{self.date} - Ahorro: {self.total_savings_cop} COP"
    
    # Sin save() propio: antes recalculaba el ahorro como min(generación, consumo) × precio, lo que pisaba el
    # cálculo con la tarifa al usuario y el autoconsumo real (external_energy.tasks.calculate_energy_savings).


class EnergyPriceForecast(models.Model):
    """Modelo para pronósticos de precios de energía"""
    
    date = models.DateField()
    predicted_price_kwh = models.DecimalField(
        max_digits=8, 
        decimal_places=4,
        validators=[MinValueValidator(0)]
    )
    confidence_level = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    source = models.CharField(max_length=100, default='XM')
    algorithm = models.CharField(max_length=100, default='ML_Model')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date']
        verbose_name = 'Pronóstico de Precio'
        verbose_name_plural = 'Pronósticos de Precios'
        unique_together = ['date', 'source']
    
    def __str__(self):
        return f"{self.date} - {self.predicted_price_kwh} COP/kWh ({self.confidence_level}%)"


class EnergyMarketData(models.Model):
    """Modelo para datos del mercado de energía"""
    
    date = models.DateField(unique=True)
    demand_mw = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    supply_mw = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    hydro_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    thermal_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    renewable_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    market_price_cop_mwh = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Dato del Mercado de Energía'
        verbose_name_plural = 'Datos del Mercado de Energía'
    
    def __str__(self):
        return f"{self.date} - Demanda: {self.demand_mw}MW, Precio: {self.market_price_cop_mwh} COP/MWh"


class EnergyAlert(models.Model):
    """Modelo para alertas relacionadas con energía"""
    
    ALERT_TYPES = [
        ('price_spike', 'Pico de Precio'),
        ('high_demand', 'Alta Demanda'),
        ('low_generation', 'Baja Generación'),
        ('market_volatility', 'Volatilidad del Mercado'),
        ('weather_impact', 'Impacto del Clima'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField()
    affected_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Alerta de Energía'
        verbose_name_plural = 'Alertas de Energía'
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.title} ({self.get_severity_display()})"
