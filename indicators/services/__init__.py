"""
Capa de servicios de `indicators`: lógica de negocio PURA (sin Celery ni DRF).

El cálculo vive aquí
y `tasks.py`/`views.py` se vuelven envoltorios finos. Nada en `services/` importa Celery
ni Django REST Framework, así que es testeable sin infraestructura.
"""
