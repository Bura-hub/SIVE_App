from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample
from .models import DeviceCategory, Device, Institution, TaskProgress

# ========================= Institution =========================

class InstitutionSerializer(serializers.ModelSerializer):
    """
    Serializador para Instituciones.
    """

    class Meta:
        model = Institution
        fields = '__all__'
        extra_kwargs = {
            'name': {'help_text': 'Nombre de la institución'},
            'scada_id': {'help_text': 'Identificador en el sistema SCADA'},
        }


# ========================= DeviceCategory =========================

class DeviceCategorySerializer(serializers.ModelSerializer):
    """
    Serializador para Categorías de Dispositivos.
    """

    class Meta:
        model = DeviceCategory
        fields = '__all__'
        extra_kwargs = {
            'name': {'help_text': 'Nombre de la categoría de dispositivo'},
            'description': {'help_text': 'Descripción breve de la categoría'},
        }


# ========================= Device =========================

class DeviceSerializer(serializers.ModelSerializer):
    """
    Serializador para Dispositivos locales con categoría e institución completas.
    """
    category = DeviceCategorySerializer(read_only=True)
    institution = InstitutionSerializer(read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'scada_id', 'name', 'status', 'is_active',
            'category', 'institution'
        ]
        extra_kwargs = {
            'name': {'help_text': 'Nombre del dispositivo'},
            'scada_id': {'help_text': 'Identificador en SCADA'},
            'is_active': {'help_text': 'Indica si el dispositivo está activo'},
        }

# ========================= Measurement =========================

class MeasurementSerializer(serializers.Serializer):
    """
    Serializador para Mediciones de Dispositivos.
    """
    device_name = serializers.CharField(
        source='device.name',
        read_only=True,
        help_text="Nombre del dispositivo al que pertenece la medición."
    )
    scada_id = serializers.CharField(
        source='device.scada_id',
        read_only=True,
        help_text="Identificador SCADA del dispositivo al que pertenece la medición."
    )

    # v2: ya no hay modelo Measurement; los datos vienen reconstruidos de las
    # tablas tipadas con el mismo contrato (id, device, date, data).
    id = serializers.IntegerField(read_only=True)
    date = serializers.DateTimeField(read_only=True)
    data = serializers.JSONField(read_only=True)

# ========================= TaskProgress =========================

class TaskProgressSerializer(serializers.ModelSerializer):
    """
    Serializador para el progreso de tareas asíncronas (Celery).
    """
    progress_percent = serializers.SerializerMethodField(
        help_text="Porcentaje de progreso calculado de la tarea."
    )

    class Meta:
        model = TaskProgress
        fields = [
            'task_id',
            'status',
            'processed_devices',
            'total_devices',
            'progress_percent',
            'message',
            'started_at',
            'finished_at'
        ]
        extra_kwargs = {
            'task_id': {'help_text': 'ID único de la tarea en Celery'},
            'status': {'help_text': 'Estado actual de la tarea'},
            'processed_devices': {'help_text': 'Número de dispositivos ya procesados'},
            'total_devices': {'help_text': 'Número total de dispositivos que deben procesarse'},
            'message': {'help_text': 'Mensaje descriptivo del estado actual'},
            'started_at': {'help_text': 'Fecha/hora de inicio de la tarea'},
            'finished_at': {'help_text': 'Fecha/hora de finalización de la tarea'},
        }

    def get_progress_percent(self, obj):
        return obj.progress_percent()


# ========================= SCADA Response Helper =========================

class SCADAResponseSerializer(serializers.Serializer):
    """
    Estructura estándar para respuestas SCADA: 
    incluye datos y total de elementos.
    """
    data = serializers.ListField(
        child=serializers.DictField(),
        help_text="Lista de elementos obtenidos del SCADA."
    )
    total = serializers.IntegerField(help_text="Número total de registros disponibles.")

    class Meta:
        ref_name = "SCADAResponse"
        examples = [
            OpenApiExample(
                'Ejemplo SCADA Response',
                value={
                    "data": [
                        {"id": 1, "name": "Institución Ejemplo"}
                    ],
                    "total": 1
                }
            )
        ]