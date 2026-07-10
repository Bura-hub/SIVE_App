"""
Capa de servicios de `indicators`: lógica de negocio PURA (sin Celery ni DRF).

Refactor de Ola 5 (ver AUDITORIA_SIVE/PLAN_REFACTOR_GODMODULES.md): el cálculo vive aquí
y `tasks.py`/`views.py` se vuelven envoltorios finos. Nada en `services/` importa Celery
ni Django REST Framework, así que es testeable sin infraestructura.
"""
