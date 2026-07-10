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

# Umbral de frescura del pipeline: si la medición más reciente es más antigua que
# esto, el pipeline se considera "stale" (degradado, no caído).
FRESHNESS_THRESHOLD_HOURS = 6


def _check_freshness(checks):
    """Frescura del PIPELINE (no de dispositivos individuales — eso es del alerting):
    cuándo corrió por última vez el cálculo de KPIs. Se usa MonthlyConsumptionKPI.
    last_calculated (1 fila, consulta instantánea) en vez de MAX(date) sobre las
    tablas de mediciones (6.3M filas, sin índice útil para MAX global → lento y
    colgaría el healthcheck). Check SOFT: marca 'degraded', no cambia 200/503."""
    try:
        from indicators.models import MonthlyConsumptionKPI
        kpi = MonthlyConsumptionKPI.objects.values('last_calculated').first()
        last = kpi['last_calculated'] if kpi else None
        if last is None:
            checks['data_freshness'] = 'sin cálculo de KPIs aún'
            return True
        age_h = (timezone.now() - last).total_seconds() / 3600.0
        fresh = age_h <= FRESHNESS_THRESHOLD_HOURS
        checks['data_freshness'] = (
            f"{'ok' if fresh else 'stale'} (KPIs calculados hace {age_h:.1f} h)"
        )
        return not fresh
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check: frescura no evaluable: %s", exc)
        checks['data_freshness'] = f"error: {exc}"
        return True


def _check_celery(checks):
    """Responsividad de Celery vía inspect().ping(). SOFT. Puede tardar → solo ?full=1."""
    try:
        from core.celery import app
        replies = app.control.inspect(timeout=1.5).ping() or {}
        workers = list(replies.keys())
        checks['celery'] = f"ok ({len(workers)} worker(s))" if workers else "sin workers"
        return not workers
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check: Celery no evaluable: %s", exc)
        checks['celery'] = f"error: {exc}"
        return True


def _check_connector(checks):
    """Alcanzabilidad del SCADA connector. SOFT (su caída no tumba la app, que sirve
    datos locales precalculados). Solo ?full=1 porque hace I/O de red."""
    try:
        from scada_proxy.scada_client import ScadaConnectorClient
        ScadaConnectorClient().get_token()
        checks['scada_connector'] = 'ok'
        return False
    except Exception as exc:  # noqa: BLE001
        checks['scada_connector'] = f"inalcanzable: {str(exc)[:80]}"
        return True


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check. Checks DUROS (determinan 200/503, porque la app web los necesita):
    base de datos y caché/Redis. Checks BLANDOS (se reportan y marcan 'degraded' pero
    NO cambian el código de estado, para no reiniciar el contenedor por dependencias
    externas): frescura del pipeline (siempre), y Celery + SCADA connector (solo con
    ?full=1, porque implican I/O más lento).
    """
    checks = {}
    healthy = True
    degraded = False

    # --- Checks DUROS ---
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check: base de datos no disponible: %s", exc)
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        cache.set("healthcheck", "ok", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "ok" else "error: sin readback"
        healthy = healthy and checks["cache"] == "ok"
    except Exception as exc:
        logger.error("Health check: caché no disponible: %s", exc)
        checks["cache"] = f"error: {exc}"
        healthy = False

    # --- Checks BLANDOS ---
    degraded |= _check_freshness(checks)
    if request.GET.get("full") in ("1", "true", "yes"):
        degraded |= _check_celery(checks)
        degraded |= _check_connector(checks)

    if not healthy:
        status_str = "unhealthy"
    elif degraded:
        status_str = "degraded"
    else:
        status_str = "healthy"

    data = {
        "status": status_str,
        "checks": checks,
        "timestamp": timezone.now().isoformat(),
    }
    # 503 solo si un check DURO falla; 'degraded' sigue devolviendo 200 (la app funciona).
    return JsonResponse(data, status=200 if healthy else 503)
