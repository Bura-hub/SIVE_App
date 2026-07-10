"""
Configuración de pytest para el directorio tests/.

El directorio mezcla TestCases reales de Django con SCRIPTS DE DIAGNÓSTICO de un solo
uso (debug_*.py, validate_*.py y varios test_*.py) que hacen `django.setup()` a nivel
de módulo, llaman a APIs reales (requests.get) y mutan/leen datos de producción. El
runner de Django solo ejecuta subclases de TestCase, así que hoy no corren; pero pytest
recolecta por nombre `test_*.py` y ejecutaría sus funciones `test_*` (y el setup de
módulo) contra la configuración real. Este conftest evita ese footgun antes de montar CI.

Si algún script se convierte en un TestCase de verdad, quítalo de `collect_ignore`.
"""

# Scripts test_*.py que NO son suites (diagnóstico manual, se corren con `python tests/<x>.py`).
collect_ignore = [
    "test_celery_tasks.py",
    "test_device_repair.py",
    "test_external_energy.py",
    "test_weather_api.py",
    "test_weather_historical_calculation.py",
]

# Herramientas de diagnóstico/validación: nunca son tests.
collect_ignore_glob = ["debug_*.py", "validate_*.py"]
