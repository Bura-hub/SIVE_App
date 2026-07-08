import logging
from celery import shared_task

from .services import XMEnergyService

logger = logging.getLogger(__name__)


@shared_task(bind=True, retry_backoff=60, max_retries=3)
def sync_external_energy_data(self):
    """Sincroniza datos externos de energía (XM) fuera del ciclo request/response de Django.

    Persiste los precios de XM agregados a nivel diario (ver `XMEnergyService.sync_all_data`).
    Ejecutar las llamadas a XM dentro de una tarea Celery evita bloquear las vistas HTTP con
    peticiones de red potencialmente lentas.
    """
    try:
        service = XMEnergyService()
        result = service.sync_all_data()

        if 'error' in result:
            logger.error(
                "Sincronización XM finalizó con error: %s", result['error']
            )
        else:
            logger.info(
                "Sincronización XM completada: %s precios (%s nuevos, %s actualizados)",
                result.get('prices_synced', 0),
                result.get('prices_created', 0),
                result.get('prices_updated', 0),
            )
        return result

    except Exception as e:
        logger.error(
            "Error inesperado en la tarea sync_external_energy_data: %s", str(e),
            exc_info=True,
        )
        raise
