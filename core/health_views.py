"""
Vistas de health check para el sistema.
"""
import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check real: verifica conectividad con la base de datos y con la
    caché/Redis. Devuelve 200 solo si ambas responden; 503 en caso contrario,
    para que los orquestadores (Docker healthcheck) detecten dependencias caídas.
    """
    checks = {}
    healthy = True

    # Base de datos
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check: base de datos no disponible: %s", exc)
        checks["database"] = f"error: {exc}"
        healthy = False

    # Caché / Redis (round-trip de escritura+lectura)
    try:
        cache.set("healthcheck", "ok", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "ok" else "error: sin readback"
        healthy = healthy and checks["cache"] == "ok"
    except Exception as exc:
        logger.error("Health check: caché no disponible: %s", exc)
        checks["cache"] = f"error: {exc}"
        healthy = False

    data = {
        "status": "healthy" if healthy else "unhealthy",
        "checks": checks,
        "timestamp": timezone.now().isoformat(),
    }
    return JsonResponse(data, status=200 if healthy else 503)
