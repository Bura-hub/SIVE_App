from django.db import models
from django.contrib.postgres.fields import JSONField # Si usas Django < 3.1, para 3.1+ es models.JSONField
from django.utils import timezone
import uuid

# =========================
# Instituciones
# =========================
class Institution(models.Model):
    scada_id = models.CharField(max_length=255, unique=True, db_index=True)  # ID en la API SCADA
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Institutions"


# =========================
# Categorías de Dispositivos
# =========================
class DeviceCategory(models.Model):
    scada_id = models.CharField(max_length=255, unique=True, db_index=True)  # ID en la API SCADA
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    charts = models.JSONField(default=list, blank=True)  # Nuevo campo

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Device Categories"


# =========================
# Dispositivos
# =========================
class Device(models.Model):
    # ID local
    id = models.AutoField(primary_key=True)  # Ahora es entero autoincremental

    # ID remoto en SCADA
    scada_id = models.CharField(max_length=255, unique=True, db_index=True)

    # Información básica
    name = models.CharField(max_length=255)

    # Relaciones
    category = models.ForeignKey(DeviceCategory, on_delete=models.SET_NULL, null=True, related_name='devices')
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, related_name='devices')

    # Estado del dispositivo
    status = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.scada_id})"


# =========================
# Mediciones históricas
# =========================
class Measurement(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='measurements')
    date = models.DateTimeField(db_index=True)  # Fecha/hora exacta de la medición (compatible con la API)
    data = models.JSONField()  # Datos completos en formato JSON

    class Meta:
        unique_together = ('device', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.device.name} - {self.date}"
    
class TaskProgress(models.Model):
    task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50, default='PENDING')  # PENDING, IN_PROGRESS, SUCCESS, FAILURE, CANCELLED
    processed_devices = models.IntegerField(default=0)
    total_devices = models.IntegerField(default=0)
    message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    is_cancelled = models.BooleanField(default=False)  # NUEVO CAMPO

    def progress_percent(self):
        return (self.processed_devices / self.total_devices * 100) if self.total_devices > 0 else 0

    def __str__(self):
        return f"Task {self.task_id} - {self.status}"


# =========================
# Mediciones v2 — tablas anchas tipadas por categoría (una columna float8
# por métrica; nombres = claves exactas del connector, ver
# measurements_schema.py). Reemplazan a Measurement (jsonb) tras el
# switchover; conviven con ella durante la transición (dual-write).
# =========================
from .measurements_schema import METER_METRICS, INVERTER_METRICS, WEATHER_METRICS


class MeterMeasurement(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='meter_measurements')
    date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['device', 'date'], name='uq_meter_meas_device_date'),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.date}"


class InverterMeasurement(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='inverter_measurements')
    date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['device', 'date'], name='uq_inverter_meas_device_date'),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.date}"


class WeatherStationMeasurement(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='weather_measurements')
    date = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['device', 'date'], name='uq_weather_meas_device_date'),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.date}"


# Los campos de métricas se generan desde el catálogo canónico: una columna
# FloatField(null=True) por métrica (clave ausente en el connector → NULL).
for _name in METER_METRICS:
    MeterMeasurement.add_to_class(_name, models.FloatField(null=True))
for _name in INVERTER_METRICS:
    InverterMeasurement.add_to_class(_name, models.FloatField(null=True))
for _name in WEATHER_METRICS:
    WeatherStationMeasurement.add_to_class(_name, models.FloatField(null=True))

# Modelo → categoría (para la ingesta y el resync)
CATEGORY_TO_MODEL = {
    'electricMeter': MeterMeasurement,
    'inverter': InverterMeasurement,
    'weatherStation': WeatherStationMeasurement,
}

_CATEGORY_TO_MODEL_LOWER = {k.lower(): v for k, v in CATEGORY_TO_MODEL.items()}


def measurement_model_for_category(category_name):
    """Modelo v2 de una categoría (case-insensitive, como category__name__iexact)."""
    return _CATEGORY_TO_MODEL_LOWER.get((category_name or '').lower())


class MeasurementSyncChunk(models.Model):
    """Checkpoint de resync v2: un chunk device×rango ya sincronizado.

    Permite reanudar el comando resync_measurements_v2 tras interrupciones
    y auditar huecos de sincronización.
    """
    STATUS_CHOICES = [('pending', 'pending'), ('done', 'done'), ('failed', 'failed')]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sync_chunks')
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rows = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['device', 'start', 'end'], name='uq_sync_chunk_device_range'),
        ]

    def __str__(self):
        return f"{self.device_id} {self.start:%Y-%m-%d}..{self.end:%Y-%m-%d} {self.status}"
