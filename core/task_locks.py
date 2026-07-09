"""
Lock distribuido simple para tareas Celery (anti-solape).

Usa cache.add (Redis) que es atómico: si la clave ya existe, otra instancia
de la tarea está corriendo y esta corrida se omite con un log. El TTL es la
red de seguridad si el proceso muere sin liberar (elegir ~2× el soft limit).
"""
import logging
from functools import wraps

from django.core.cache import cache

logger = logging.getLogger(__name__)


def single_instance(key: str, ttl: int):
    """Decorador: garantiza una sola ejecución concurrente de la tarea.

    Aplicar DEBAJO de @shared_task (decora la función, no la Task)::

        @shared_task(bind=True)
        @single_instance('mi-tarea', ttl=1200)
        def mi_tarea(self): ...
    """
    lock_key = f'task-lock:{key}'

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not cache.add(lock_key, '1', ttl):
                logger.warning(
                    f"Tarea '{key}' omitida: ya hay una instancia en ejecución "
                    f"(lock '{lock_key}' activo, TTL {ttl}s)."
                )
                return f'skipped: lock {key} activo'
            try:
                return fn(*args, **kwargs)
            finally:
                cache.delete(lock_key)
        return wrapper
    return decorator
