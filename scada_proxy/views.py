from datetime import datetime, timezone
import logging
import re
import requests
import uuid # ¡Importar el módulo uuid!

from django.db.models import Avg, Max, Min, Sum, F, FloatField, Q
from django.db.models.functions import TruncDay, Cast
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from celery.result import AsyncResult
from celery import current_app

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, OpenApiTypes
from .models import (
    Institution, DeviceCategory, Device, TaskProgress, CATEGORY_TO_MODEL,
    measurement_model_for_category,
)
from .measurements_schema import CATEGORY_METRICS
from .serializers import (
    InstitutionSerializer, DeviceCategorySerializer, DeviceSerializer,
    MeasurementSerializer, TaskProgressSerializer, SCADAResponseSerializer,
)
from .scada_client import ScadaConnectorClient
from .tasks import fetch_historical_measurements_for_all_devices, sync_scada_metadata_core

logger = logging.getLogger(__name__)
scada_client = ScadaConnectorClient()

# ========================= SCADA Proxy Base =========================

class ScadaProxyView(APIView):
    permission_classes = [IsAuthenticated]

    def get_scada_token(self):
        """
        Obtiene el token de SCADA o devuelve una respuesta de error.
        """
        try:
            return scada_client.get_token()
        except EnvironmentError as e:
            logger.error(f"Error de configuración de SCADA: {e}")
            return Response({"detail": "Error de configuración del servidor SCADA."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener token de SCADA: {e}")
            return Response({"detail": "No se pudo autenticar con la API SCADA."},
                            status=status.HTTP_502_BAD_GATEWAY)


def check_scada_connection():
    """
    Verifica la conexión real con SCADA: token y una llamada ligera (instituciones).
    Retorna (connected: bool, message: str) para uso en vistas o endpoint.
    """
    try:
        token = scada_client.get_token()
        scada_client.get_institutions(token)
        return True, "Conectado a SCADA"
    except EnvironmentError as e:
        logger.warning(f"Configuración SCADA: {e}")
        return False, "Error de configuración del servidor SCADA (credenciales o URL)."
    except requests.exceptions.RequestException as e:
        logger.warning(f"Conexión SCADA: {e}")
        return False, "No se pudo conectar con la API SCADA. Revise credenciales y conectividad."


@extend_schema(
    tags=["SCADA Proxy"],
    description="Verifica el estado de conexión con el sistema SCADA (token y API).",
    responses={
        200: OpenApiResponse(
            description="Conexión correcta",
            response=OpenApiTypes.OBJECT,
            examples=[OpenApiExample("Conectado", value={"connected": True, "message": "Conectado a SCADA"})]
        ),
        503: OpenApiResponse(
            description="Sin conexión SCADA",
            response=OpenApiTypes.OBJECT,
            examples=[OpenApiExample("Desconectado", value={"connected": False, "message": "No se pudo conectar con la API SCADA."})]
        ),
    },
)
class ScadaConnectionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connected, message = check_scada_connection()
        payload = {"connected": connected, "message": message}
        status_code = status.HTTP_200_OK if connected else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=status_code)


# ========================= SCADA Proxy Views =========================

@extend_schema(
    tags=["SCADA Proxy"],
    description="Obtiene la lista de instituciones desde el sistema SCADA.",
    responses={200: SCADAResponseSerializer}
)
@method_decorator(cache_page(60 * 60 * 2), name='dispatch')
class InstitutionsView(ScadaProxyView):
    serializer_class = InstitutionSerializer

    def get(self, request, *args, **kwargs):
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
        try:
            resp = scada_client.get_institutions(token)
            return Response({"data": resp.get("data", []), "total": resp.get("total", 0)})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener instituciones: {e}")
            return Response({"detail": "Error al comunicarse con el servicio SCADA."}, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    tags=["SCADA Proxy"],
    description="Obtiene las categorías de dispositivos desde el sistema SCADA.",
    responses={200: SCADAResponseSerializer}
)
@method_decorator(cache_page(60 * 60 * 2), name='dispatch')
class DeviceCategoriesView(ScadaProxyView):
    serializer_class = DeviceCategorySerializer

    def get(self, request, *args, **kwargs):
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
        try:
            resp = scada_client.get_device_categories(token)
            return Response({"data": resp.get("data", []), "total": resp.get("total", 0)})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener categorías de SCADA: {e}")
            return Response({"detail": "Error al comunicarse con el servicio SCADA."}, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    tags=["SCADA Proxy"],
    description="Obtiene dispositivos desde el sistema SCADA, filtrando por categoría, institución o nombre.",
    parameters=[
        OpenApiParameter("category_id", str, OpenApiParameter.QUERY, description="Filtrar por ID de categoría (UUID de SCADA) o nombre de categoría (ej. 'inverter')"),
        OpenApiParameter("institution_id", str, OpenApiParameter.QUERY, description="Filtrar por ID de institución"),
        OpenApiParameter("name", str, OpenApiParameter.QUERY, description="Filtrar por nombre de dispositivo (si 'category_id' es UUID) o por nombre de categoría (si 'category_id' no es un UUID o no está presente)"),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY, description="Cantidad máxima de resultados"),
        OpenApiParameter("offset", int, OpenApiParameter.QUERY, description="Paginación - desplazamiento inicial"),
    ],
    responses={200: SCADAResponseSerializer}
)
@method_decorator(cache_page(60 * 5), name='dispatch')
class DevicesView(ScadaProxyView):
    serializer_class = DeviceSerializer

    def get(self, request, *args, **kwargs):
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
        try:
            # Inicializar un diccionario para los parámetros que se enviarán a scada_client.get_devices
            scada_client_params = {}

            # Manejar el parámetro 'category_id' de la solicitud de Django
            # Puede ser un SCADA ID (UUID) o un nombre de categoría.
            request_category_id = request.query_params.get('category_id')
            if request_category_id:
                try:
                    # Intentar convertir a UUID. Si tiene éxito, es un SCADA ID de categoría.
                    uuid.UUID(request_category_id)
                    scada_client_params["category_scada_id"] = request_category_id
                except ValueError:
                    # Si no es un UUID, asumir que es un nombre de categoría (ej. "inverter").
                    scada_client_params["category_name_filter"] = request_category_id
            
            # Manejar el parámetro 'name' de la solicitud de Django.
            # Según las pruebas de Thunderclient, la API de SCADA usa 'name' para filtrar por nombre de CATEGORÍA.
            # Esto entra en conflicto con la descripción de OpenApiParameter "Filtrar por nombre del dispositivo".
            # Priorizaremos 'category_id' si ya se usó para filtrar por nombre de categoría.
            request_name = request.query_params.get('name')
            if request_name:
                # Si 'category_name_filter' NO fue establecido por 'category_id' (es decir, 'category_id' fue un UUID o no se proporcionó)
                # entonces usamos el 'name' de la request como filtro de nombre de categoría para SCADA.
                if "category_name_filter" not in scada_client_params:
                    scada_client_params["category_name_filter"] = request_name
                else:
                    # Si 'category_id' ya fue interpretado como un nombre de categoría,
                    # y también se proporcionó 'name', loguear una advertencia de conflicto y 'name' no se usará como category_name_filter.
                    # Si 'name' fuera para 'device_name', se necesitaría una lógica adicional para determinarlo.
                    logger.warning(
                        f"Parámetros de filtro de categoría en conflicto: 'category_id' (como nombre) "
                        f"y 'name' proporcionados. Priorizando 'category_id' para el filtro de nombre de categoría."
                    )

            # Añadir otros parámetros que se mapean directamente
            if request.query_params.get('institution_id'):
                scada_client_params["institution_id"] = request.query_params.get('institution_id')
            if request.query_params.get('limit'):
                scada_client_params["limit"] = request.query_params.get('limit')
            if request.query_params.get('offset'):
                scada_client_params["offset"] = request.query_params.get('offset')

            # Llamar a scada_client.get_devices con los parámetros correctamente mapeados
            resp = scada_client.get_devices(token, **scada_client_params)
            return Response({"data": resp.get("data", []), "total": resp.get("total", 0)})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener dispositivos: {e}")
            return Response({"detail": "Error al comunicarse con el servicio SCADA."}, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    tags=["SCADA Proxy"],
    description="Obtiene mediciones de un dispositivo desde el sistema SCADA.",
    parameters=[
        OpenApiParameter("from_date", str, OpenApiParameter.QUERY, description="Fecha de inicio en formato ISO 8601"),
        OpenApiParameter("to_date", str, OpenApiParameter.QUERY, description="Fecha final en formato ISO 8601"),
        OpenApiParameter("order_by", str, OpenApiParameter.QUERY, description="Campo y orden para ordenar resultados"),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY, description="Cantidad máxima de resultados"),
        OpenApiParameter("offset", int, OpenApiParameter.QUERY, description="Paginación - desplazamiento inicial"),
    ],
    responses={200: SCADAResponseSerializer}
)
class MeasurementsView(ScadaProxyView):
    serializer_class = MeasurementSerializer

    def get(self, request, device_id, *args, **kwargs):
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
        try:
            params = {
                "device_id": device_id,
                "from_date": request.query_params.get('from_date'),
                "to_date": request.query_params.get('to_date'),
                "order_by": request.query_params.get('order_by', 'date desc'),
                "limit": request.query_params.get('limit'),
                "offset": request.query_params.get('offset')
            }
            resp = scada_client.get_measurements(token, **params)
            return Response({"data": resp.get("data", []), "total": resp.get("total", 0)})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener mediciones para {device_id}: {e}")
            return Response({"detail": "Error al comunicarse con el servicio SCADA."}, status=status.HTTP_502_BAD_GATEWAY)

# ========================= Local Models Views =========================

@extend_schema(
    tags=["Datos Locales"],
    description="Lista todas las instituciones locales registradas.",
    parameters=[OpenApiParameter("search", str, OpenApiParameter.QUERY, description="Buscar por nombre de institución")],
    responses={200: InstitutionSerializer(many=True)}
)
class LocalInstitutionListView(generics.ListAPIView):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

@extend_schema(
    tags=["Datos Locales"],
    description="Lista todas las categorías de dispositivos locales con datos SCADA enriquecidos (sin indicatorConfigurations).",
    parameters=[OpenApiParameter("search", str, OpenApiParameter.QUERY, description="Buscar por nombre de categoría (inverter, electricmeter, weatherstation)")],
    responses={200: DeviceCategorySerializer(many=True)}
)
class LocalDeviceCategoryListView(generics.ListAPIView):
    queryset = DeviceCategory.objects.all()
    serializer_class = DeviceCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)

        try:
            token = scada_client.get_token()
            scada_categories = scada_client.get_device_categories(token).get('data', []) or []
            # Usar .get() y saltar categorías sin 'id' para no romper el enriquecimiento.
            scada_map = {str(cat['id']): cat for cat in scada_categories if cat.get('id') is not None}

            for item in response.data:
                scada_id = item.get('scada_id')
                if scada_id and scada_id in scada_map:
                    # Sobrescribir solo campos relevantes
                    scada_charts = scada_map[scada_id].get('charts', [])
                    # Removemos indicatorConfigurations si existiera
                    for chart in scada_charts:
                        chart.pop('indicatorConfigurations', None)
                    item['charts'] = scada_charts
        except Exception as e:
            logger.warning(f"No se pudo enriquecer categorías con SCADA: {e}")

        return response


@extend_schema(
    tags=["Datos Locales"],
    description="Lista todos los dispositivos locales activos, con soporte de filtros, búsqueda y ordenamiento.",
    parameters=[
        OpenApiParameter("category", int, OpenApiParameter.QUERY, description="ID de la categoría(1:inv 2:Med 3:Est)"),
        OpenApiParameter("institution", int, OpenApiParameter.QUERY, description="ID de la institución(1:Udenar 2:Cesmag 3:Mar 4:UCC 5:HUDN)"),
        OpenApiParameter("is_active", bool, OpenApiParameter.QUERY, description="Filtrar dispositivos activos"),
        OpenApiParameter("search", str, OpenApiParameter.QUERY, description="Buscar por nombre o SCADA ID"),
        OpenApiParameter("ordering", str, OpenApiParameter.QUERY, description="Ordenar por campos como 'name'"),
    ],
    responses={200: DeviceSerializer(many=True)}
)
class LocalDeviceListView(generics.ListAPIView):
    queryset = Device.objects.filter(is_active=True).select_related('category', 'institution')
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'institution', 'is_active']
    search_fields = ['name', 'scada_id']
    ordering_fields = ['name', 'category__name', 'institution__name']

    # NOTA: un GET debe ser de solo lectura. La reparación de relaciones
    # faltantes se realiza en la tarea Celery 'repair_device_relationships' y en
    # el comando de gestión 'repair_device_relationships', no aquí. Antes este
    # get_queryset hacía device.save() (escrituras en BD durante un GET) y con
    # consultas N+1; se eliminó.

@extend_schema(
    tags=["Datos Locales"],
    description="Lista mediciones históricas filtradas por dispositivo y rango de fechas.",
    parameters=[
        OpenApiParameter("device", str, OpenApiParameter.QUERY, description="ID o SCADA_ID del dispositivo (string)"),
        OpenApiParameter("from_date", str, OpenApiParameter.QUERY, description="Fecha de inicio (ISO 8601) 2025-01-18T13:00:00"),
        OpenApiParameter("to_date", str, OpenApiParameter.QUERY, description="Fecha final (ISO 8601) 2025-01-18T13:00:00"),
        OpenApiParameter("ordering", str, OpenApiParameter.QUERY, description="Ordenar por 'date' (usar '-date' para descendente)"),
    ],
    responses={200: MeasurementSerializer(many=True)}
)
class HistoricalMeasurementsView(generics.ListAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [IsAuthenticated]
    # v2: las mediciones viven en 3 tablas tipadas (una por categoría). Los
    # filtros se aplican por tabla y se combinan; el filtro por dispositivo
    # solo produce filas en la tabla de su categoría. La respuesta conserva el
    # contrato v1: el campo `data` se reconstruye desde las columnas tipadas
    # (columna NULL ⇔ clave ausente en el antiguo jsonb).
    ordering_fields = ['date']

    def list(self, request, *args, **kwargs):
        device_param = request.query_params.get('device')
        from_date = self._parse_date(request.query_params.get('from_date'))
        to_date = self._parse_date(request.query_params.get('to_date'))

        # Mismo contrato que OrderingFilter con ordering_fields=['date']:
        # solo 'date'/'-date' son válidos; por defecto '-date' (el antiguo
        # Meta.ordering del modelo Measurement v1).
        ordering = request.query_params.get('ordering')
        if ordering not in ('date', '-date'):
            ordering = '-date'

        rows = []
        for category_name, model in CATEGORY_TO_MODEL.items():
            qs = model.objects.all()

            if device_param:
                if device_param.isdigit():  # Si es un número entero
                    qs = qs.filter(device__id=int(device_param))
                else:  # Si no es número, asumimos que es un SCADA_ID
                    qs = qs.filter(device__scada_id=device_param)

            if from_date:
                qs = qs.filter(date__gte=from_date)
            if to_date:
                qs = qs.filter(date__lte=to_date)

            metrics = CATEGORY_METRICS[category_name]
            for obj in qs.select_related('device').order_by(ordering).iterator(chunk_size=2000):
                obj.data = {
                    metric: value for metric in metrics
                    if (value := getattr(obj, metric)) is not None
                }
                rows.append(obj)

        rows.sort(key=lambda o: o.date, reverse=(ordering == '-date'))

        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)

    def _parse_date(self, date_str):
        try:
            return datetime.fromisoformat(date_str).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None

@extend_schema(
    tags=["Datos Locales"],
    description="Obtiene un resumen diario (promedio, máximo, mínimo y suma) de las mediciones de un dispositivo.",
    parameters=[
        OpenApiParameter("device", str, OpenApiParameter.QUERY, description="Scada_ID del dispositivo (UUID o string)"),
        OpenApiParameter("variable_key", str, OpenApiParameter.QUERY, description="Clave de la variable medida (dentro de `data`)"),
        OpenApiParameter("from_date", str, OpenApiParameter.QUERY, description="Fecha de inicio (ISO 8601)"),
        OpenApiParameter("to_date", str, OpenApiParameter.QUERY, description="Fecha final (ISO 8601)"),
    ],
    responses={200: OpenApiExample(
        "Ejemplo Resumen Diario",
        value=[{
            "date": "2025-07-10",
            "average": 15.3,
            "max": 30.1,
            "min": 5.4,
            "sum": 153.2
        }]
    )}
)
@method_decorator(cache_page(60 * 30), name='dispatch')
class DailySummaryMeasurementsView(ScadaProxyView):
    serializer_class = MeasurementSerializer

    def get(self, request, *args, **kwargs):
        device_id = request.query_params.get('device')
        variable_key = request.query_params.get('variable_key')
        from_date = self._parse_date(request.query_params.get('from_date'))
        to_date = self._parse_date(request.query_params.get('to_date'))

        if not all([device_id, variable_key, from_date, to_date]):
            return Response(
                {"detail": "Se requieren 'device', 'variable_key', 'from_date' y 'to_date'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar 'variable_key': se interpola directamente en lookups ORM (nombre
        # de columna del esquema v2), así que debe ser un identificador seguro
        # (letras, dígitos y '_'), sin '__' para evitar inyectar lookups anidados
        # o transformaciones. Además se valida contra el catálogo de métricas de
        # la categoría del dispositivo más abajo.
        if not re.fullmatch(r'[A-Za-z0-9_]+', variable_key) or '__' in variable_key:
            return Response(
                {"detail": "El parámetro 'variable_key' no es válido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # v2: la variable es una columna tipada en la tabla de la categoría
            # del dispositivo; se resuelve el dispositivo para elegir la tabla.
            # Si es un entero, busca por device_id; de lo contrario, por scada_id
            try:
                if device_id.isdigit():
                    device = Device.objects.select_related('category').get(id=int(device_id))
                else:
                    device = Device.objects.select_related('category').get(scada_id=device_id)
            except Device.DoesNotExist:
                # Igual que en v1 con un dispositivo inexistente: sin filas
                return Response([])

            category_name = device.category.name if device.category else None
            model = measurement_model_for_category(category_name)
            metrics = CATEGORY_METRICS.get(category_name, [])
            if model is None or variable_key not in metrics:
                # Igual que en v1 con una clave inexistente en `data`: sin filas
                return Response([])

            queryset = model.objects.filter(
                device=device,
                date__range=(from_date, to_date),
                **{f"{variable_key}__isnull": False}
            )

            summary = (
                queryset
                .annotate(day=TruncDay('date'))
                .values('day')
                .annotate(
                    average=Avg(variable_key),
                    max=Max(variable_key),
                    min=Min(variable_key),
                    sum=Sum(variable_key),
                )
                .order_by('day')
            )

            return Response([
                {
                    'date': s['day'].date().isoformat(),
                    'average': s['average'],
                    'max': s['max'],
                    'min': s['min'],
                    'sum': s['sum']
                } for s in summary
            ])

        except Exception as e:
            logger.error(f"Error al calcular el resumen diario: {e}", exc_info=True)
            return Response(
                {"detail": "Error al calcular el resumen."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_date(self, date_str):
        try:
            return datetime.fromisoformat(date_str).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None

# ========================= Celery Tasks Views =========================

@extend_schema(
    tags=["Tareas"],
    description="Lanza una tarea para obtener mediciones históricas.",
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            "Ejemplo de body",
            value={"time_range_seconds": 1000},
            request_only=True
        )
    ],
    responses={
        202: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Respuesta tras encolar la tarea",
            examples=[
                OpenApiExample(
                    "Ejemplo de respuesta",
                    value={
                        "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                        "message": "Tarea encolada."
                    }
                )
            ]
        )
    }
)
class HistoricalMeasurementsTaskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            seconds = int(request.data.get('time_range_seconds', 31536000))
            task = fetch_historical_measurements_for_all_devices.delay(seconds)
            TaskProgress.objects.create(
                task_id=task.id,
                status='PENDING',
                total_devices=Device.objects.filter(is_active=True).count(),
                message="Tarea de obtención histórica encolada."
            )
            return Response(
                {"task_id": task.id, "message": "Tarea encolada."},
                status=status.HTTP_202_ACCEPTED
            )
        except Exception as e:
            logger.error(f"Error al lanzar tarea: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Tareas"],
    description="Consulta el estado de una tarea por su ID.",
    parameters=[OpenApiParameter("task_id", str, OpenApiParameter.PATH, description="ID de la tarea")],
    responses={200: TaskProgressSerializer}
)
class TaskProgressView(APIView):
    serializer_class = TaskProgressSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        try:
            progress = TaskProgress.objects.get(task_id=task_id)
            return Response({
                "task_id": progress.task_id,
                "status": progress.status,
                "processed_devices": progress.processed_devices,
                "total_devices": progress.total_devices,
                "progress_percent": progress.progress_percent(),
                "message": progress.message,
                "started_at": progress.started_at,
                "finished_at": progress.finished_at
            })
        except TaskProgress.DoesNotExist:
            result = AsyncResult(task_id)
            if result.state in ["PENDING", "STARTED", "SUCCESS", "FAILURE"]:
                return Response({
                    "task_id": task_id,
                    "status": result.state,
                    "message": "No hay registro en la BD, mostrando estado desde Celery."
                })
            return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=["Tareas"],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            "Ejemplo de body",
            value={"task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
            request_only=True
        )
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Respuesta tras cancelar una tarea",
            examples=[
                OpenApiExample(
                    "Ejemplo de respuesta",
                    value={
                        "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                        "message": "Cancelación solicitada."
                    }
                )
            ]
        )
    }
)
class CancelTaskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response({"error": "task_id es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        TaskProgress.objects.filter(task_id=task_id).update(
            is_cancelled=True,
            status='CANCELLED',
            message='Tarea cancelada desde API.'
        )
        AsyncResult(task_id).revoke(terminate=False)
        return Response({"task_id": task_id, "message": "Cancelación solicitada."})
    
@extend_schema(
    tags=["Tareas"],
    description="Obtiene las tareas activas, reservadas y programadas en Celery.",
    responses={200: OpenApiExample(
        "Respuesta Ejemplo",
        value={
            "active_tasks": [],
            "reserved_tasks": [],
            "scheduled_tasks": []
        }
    )}
)
class ActiveTasksView(APIView):
    serializer_class = TaskProgressSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            insp = current_app.control.inspect()
            active = insp.active() or {}
            reserved = insp.reserved() or {}
            scheduled = insp.scheduled() or {}

            return Response({
                "active_tasks": active,
                "reserved_tasks": reserved,
                "scheduled_tasks": scheduled
            })
        except Exception as e:
            logger.error(f"Error al inspeccionar tareas activas: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Tareas"],
    description="Lista el historial de tareas ejecutadas en el sistema.",
    responses={200: TaskProgressSerializer(many=True)}
)
class TaskHistoryView(generics.ListAPIView):
    queryset = TaskProgress.objects.all().order_by('-started_at')
    serializer_class = TaskProgressSerializer
    permission_classes = [IsAuthenticated]
    
# ========================= Sincronización Local =========================

from django.db import models

@extend_schema(
    tags=["Sincronización"],
    description="Sincroniza categorías, instituciones y dispositivos desde SCADA hacia la base local.",
    responses={200: OpenApiExample(
        "Ejemplo Respuesta",
        value={"detail": "Sincronización completada con éxito."}
    )}
)
class SyncLocalDevicesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delega en la implementación ÚNICA de sincronización (sync_scada_metadata_core),
        # que mapea correctamente las relaciones anidadas, pagina el listado de
        # dispositivos y solo desactiva ausentes si la lista vino completa.
        try:
            summary = sync_scada_metadata_core()
            return Response(
                {"detail": "Sincronización completada con éxito.", "summary": summary},
                status=status.HTTP_200_OK,
            )
        except EnvironmentError as e:
            logger.error(f"Error de configuración de SCADA al sincronizar: {e}")
            return Response({"detail": "Error de configuración del servidor SCADA."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red/API al sincronizar datos locales: {e}")
            return Response({"detail": "No se pudo sincronizar con la API SCADA."},
                            status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.error(f"Error al sincronizar datos locales: {e}", exc_info=True)
            return Response({"detail": "Error durante la sincronización."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Sincronización"],
    description="Repara las relaciones faltantes de categoría e institución en dispositivos específicos o todos los dispositivos.",
    request=OpenApiExample(
        "Ejemplo Request",
        value={"device_ids": [15, 16], "repair_all": False}
    ),
    responses={200: OpenApiExample(
        "Ejemplo Respuesta",
        value={"detail": "Reparación completada con éxito.", "repaired_count": 2}
    )}
)
class RepairDeviceRelationshipsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Repara las relaciones faltantes de dispositivos.
        Parámetros opcionales:
        - device_ids: Lista de IDs de dispositivos específicos a reparar
        - repair_all: Si es True, repara todos los dispositivos con problemas
        """
        try:
            device_ids = request.data.get('device_ids', [])
            repair_all = request.data.get('repair_all', False)
            
            if repair_all:
                # Reparar todos los dispositivos con problemas
                devices_to_repair = Device.objects.filter(
                    models.Q(category__isnull=True) | models.Q(institution__isnull=True)
                ).select_related('category', 'institution')
            elif device_ids:
                # Reparar dispositivos específicos
                devices_to_repair = Device.objects.filter(
                    id__in=device_ids
                ).select_related('category', 'institution')
            else:
                return Response(
                    {"detail": "Debe especificar device_ids o establecer repair_all=True"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not devices_to_repair.exists():
                return Response(
                    {"detail": "No se encontraron dispositivos para reparar"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            repaired_count = 0
            failed_count = 0
            repair_details = []
            
            for device in devices_to_repair:
                try:
                    repaired = False
                    repair_info = {"device_id": device.id, "name": device.name, "changes": []}
                    
                    # Intentar encontrar categoría por nombre del dispositivo
                    if not device.category:
                        if 'medidor' in device.name.lower() or 'meter' in device.name.lower():
                            category = DeviceCategory.objects.filter(name__icontains='electricmeter').first()
                            if category:
                                device.category = category
                                repaired = True
                                repair_info["changes"].append(f"Categoría asignada: {category.name}")
                        elif 'inversor' in device.name.lower() or 'inverter' in device.name.lower():
                            category = DeviceCategory.objects.filter(name__icontains='inverter').first()
                            if category:
                                device.category = category
                                repaired = True
                                repair_info["changes"].append(f"Categoría asignada: {category.name}")
                        elif 'estación' in device.name.lower() or 'weather' in device.name.lower():
                            category = DeviceCategory.objects.filter(name__icontains='weatherstation').first()
                            if category:
                                device.category = category
                                repaired = True
                                repair_info["changes"].append(f"Categoría asignada: {category.name}")
                    
                    # Intentar encontrar institución por nombre del dispositivo
                    if not device.institution:
                        for institution in Institution.objects.all():
                            if institution.name.lower() in device.name.lower():
                                device.institution = institution
                                repaired = True
                                repair_info["changes"].append(f"Institución asignada: {institution.name}")
                                break
                    
                    if repaired:
                        device.save()
                        repaired_count += 1
                        repair_info["status"] = "success"
                        logger.info(f"Dispositivo {device.name} reparado - Categoría: {device.category}, Institución: {device.institution}")
                    else:
                        failed_count += 1
                        repair_info["status"] = "failed"
                        repair_info["changes"].append("No se pudo determinar categoría o institución")
                    
                    repair_details.append(repair_info)
                    
                except Exception as e:
                    failed_count += 1
                    repair_details.append({
                        "device_id": device.id,
                        "name": device.name,
                        "status": "error",
                        "changes": [f"Error: {str(e)}"]
                    })
                    logger.error(f"Error al reparar dispositivo {device.name}: {e}")
            
            return Response({
                "detail": "Reparación completada",
                "summary": {
                    "total_processed": len(repair_details),
                    "repaired_count": repaired_count,
                    "failed_count": failed_count
                },
                "repair_details": repair_details
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en reparación de relaciones: {e}", exc_info=True)
            return Response(
                {"detail": f"Error durante la reparación: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )