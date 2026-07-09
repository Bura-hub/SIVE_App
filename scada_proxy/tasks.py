import logging
from celery import shared_task
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
import requests
from django.db import transaction, IntegrityError
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone as dj_timezone
import pytz
from django.db import models

# Importa tu cliente SCADA y tus modelos
from django.conf import settings
from .scada_client import ScadaConnectorClient
from .models import (
    Institution, DeviceCategory, Device, Measurement, TaskProgress,
    CATEGORY_TO_MODEL,
)
from .measurements_schema import metrics_for_category

logger = logging.getLogger(__name__)
scada_client = ScadaConnectorClient()

# Zona horaria de Colombia
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def get_colombia_now():
    """Obtiene la fecha y hora actual en zona horaria de Colombia"""
    return dj_timezone.now().astimezone(COLOMBIA_TZ)

# ============================================================================
# Sincronización de metadatos SCADA (implementación ÚNICA y reutilizable)
# ----------------------------------------------------------------------------
# La API SCADA devuelve 'category' e 'institution' como dicts anidados con
# ['id'] (NO 'category_id'/'institution_id'). Esta implementación única
# reemplaza las tres versiones divergentes que existían (la tarea
# sync_scada_metadata, sync_scada_metadata_enhanced y SyncLocalDevicesView).
# ============================================================================

# Tamaño de página al paginar el listado de dispositivos de la API SCADA.
DEVICES_PAGE_SIZE = 500


def _sync_institutions(client, token):
    """
    Sincroniza instituciones. Devuelve (mapa scada_id->obj, cantidad procesada).
    """
    institutions_data = client.get_institutions(token).get('data', []) or []
    institution_map = {}
    processed = 0
    for inst_data in institutions_data:
        scada_id = inst_data.get('id')
        name = inst_data.get('name')
        if scada_id is None or name is None:
            logger.warning(f"Institución SCADA incompleta, se omite: {inst_data}")
            continue
        obj, _ = Institution.objects.update_or_create(
            scada_id=str(scada_id),
            defaults={'name': name},
        )
        institution_map[str(scada_id)] = obj
        processed += 1
    logger.info(f"Sincronizadas {processed} instituciones.")
    return institution_map, processed


def _sync_categories(client, token):
    """
    Sincroniza categorías de dispositivos. Devuelve (mapa scada_id->obj, cantidad).
    """
    categories_data = client.get_device_categories(token).get('data', []) or []
    category_map = {}
    processed = 0
    for cat_data in categories_data:
        scada_id = cat_data.get('id')
        name = cat_data.get('name')
        if scada_id is None or name is None:
            logger.warning(f"Categoría SCADA incompleta, se omite: {cat_data}")
            continue
        obj, _ = DeviceCategory.objects.update_or_create(
            scada_id=str(scada_id),
            defaults={
                'name': name,
                'description': cat_data.get('description', '') or '',
            },
        )
        category_map[str(scada_id)] = obj
        processed += 1
    logger.info(f"Sincronizadas {processed} categorías de dispositivos.")
    return category_map, processed


def _fetch_all_devices(client, token):
    """
    Obtiene TODOS los dispositivos paginando por limit/offset.

    Si la API pagina por defecto, una sola llamada dejaría fuera a los
    dispositivos de páginas posteriores (que luego se marcarían como inactivos
    por error). Por eso se recorre el listado completo.

    Devuelve (lista_dispositivos, total_reportado_o_None, completo: bool).
    'completo' indica si estamos razonablemente seguros de haber traído la
    lista íntegra (para decidir si es seguro desactivar los ausentes).
    """
    offset = 0
    all_devices = []
    total = None
    # Tope de seguridad: si la API ignora 'offset' y no reporta 'total', el bucle
    # podría no terminar nunca (devolvería siempre una página llena). Cortamos y
    # marcamos la lista como INCOMPLETA para no desactivar dispositivos por error.
    MAX_PAGES = 1000
    truncated = False
    for _ in range(MAX_PAGES):
        resp = client.get_devices(token, limit=DEVICES_PAGE_SIZE, offset=offset)
        data = resp.get('data', []) or []
        if total is None:
            total = resp.get('total')
        if not data:
            break
        all_devices.extend(data)
        # Última página: la API devolvió menos de lo pedido.
        if len(data) < DEVICES_PAGE_SIZE:
            break
        offset += DEVICES_PAGE_SIZE
        # Si conocemos el total y ya lo alcanzamos, detenerse.
        if total is not None and len(all_devices) >= total:
            break
    else:
        # Se agotó MAX_PAGES sin condición de fin natural → respuesta sospechosa.
        truncated = True
        logger.error(
            f"_fetch_all_devices alcanzó el tope de {MAX_PAGES} páginas "
            f"({len(all_devices)} dispositivos); la API podría ignorar 'offset'."
        )
    # Completa solo si NO se truncó y obtuvimos algo y (no hay total o coincide).
    complete = (not truncated) and bool(all_devices) and (total is None or len(all_devices) >= total)
    return all_devices, total, complete


def sync_scada_metadata_core(client=None):
    """
    Implementación ÚNICA y reutilizable de la sincronización de metadatos SCADA
    (categorías, instituciones y dispositivos) hacia la base de datos local.

    - Mapea correctamente los dicts anidados 'category'/'institution' (['id'])
      a las claves foráneas locales.
    - Pagina el listado de dispositivos para no perder ninguno.
    - Solo desactiva dispositivos ausentes si se obtuvo la lista COMPLETA
      (evita desactivaciones masivas ante respuestas parciales/vacías).

    Devuelve un dict con el resumen (para uso de tareas y vistas).
    """
    client = client or scada_client
    token = client.get_token()

    with transaction.atomic():
        # 1. Categorías e instituciones primero (para poder mapear las FK).
        category_map, categories_count = _sync_categories(client, token)
        institution_map, institutions_count = _sync_institutions(client, token)

        # 2. Dispositivos (paginados).
        devices_data, total, complete = _fetch_all_devices(client, token)

        existing_scada_ids = set(Device.objects.values_list('scada_id', flat=True))
        fetched_scada_ids = set()
        devices_created = 0
        devices_updated = 0
        devices_with_issues = 0

        for device_data in devices_data:
            scada_id = device_data.get('id')
            name = device_data.get('name')
            if scada_id is None or name is None:
                logger.warning(f"Dispositivo SCADA incompleto, se omite: {device_data}")
                continue
            scada_id = str(scada_id)
            fetched_scada_ids.add(scada_id)

            # La API devuelve 'category' e 'institution' como dicts anidados con ['id'].
            category_obj = None
            category = device_data.get('category')
            if isinstance(category, dict) and category.get('id') is not None:
                category_obj = category_map.get(str(category['id']))
                if category_obj is None:
                    logger.warning(f"Categoría {category.get('id')} no encontrada para dispositivo {name}.")

            institution_obj = None
            institution = device_data.get('institution')
            if isinstance(institution, dict) and institution.get('id') is not None:
                institution_obj = institution_map.get(str(institution['id']))
                if institution_obj is None:
                    logger.warning(f"Institución {institution.get('id')} no encontrada para dispositivo {name}.")

            defaults = {
                'name': name,
                'status': device_data.get('status', '') or '',
                'is_active': True,
            }
            # Solo escribir las FK cuando se resolvieron. Un fallo de resolución
            # (mapping ausente, orden de sync, categoría faltante) NO debe sobreescribir
            # con None una relación válida existente y hacer desaparecer el dispositivo
            # de los KPIs por categoría. La tarea repair_device_relationships completa
            # las FK faltantes de dispositivos nuevos.
            if category_obj is not None:
                defaults['category'] = category_obj
            if institution_obj is not None:
                defaults['institution'] = institution_obj

            _, created = Device.objects.update_or_create(
                scada_id=scada_id,
                defaults=defaults,
            )
            if created:
                devices_created += 1
                logger.info(f"Dispositivo creado: {name} ({scada_id}).")
            else:
                devices_updated += 1
            if category_obj is None or institution_obj is None:
                devices_with_issues += 1

        # 3. Desactivar dispositivos ausentes SOLO si la lista vino completa.
        devices_deactivated = 0
        if complete:
            to_deactivate = existing_scada_ids - fetched_scada_ids
            if to_deactivate:
                devices_deactivated = Device.objects.filter(
                    scada_id__in=list(to_deactivate)
                ).update(is_active=False)
                logger.info(f"Desactivados {devices_deactivated} dispositivos ausentes en SCADA.")
        else:
            logger.warning(
                "No se desactivan dispositivos: la lista de SCADA podría estar incompleta "
                f"(obtenidos={len(fetched_scada_ids)}, total_reportado={total})."
            )

    summary = {
        'institutions': institutions_count,
        'categories': categories_count,
        'devices_created': devices_created,
        'devices_updated': devices_updated,
        'devices_with_issues': devices_with_issues,
        'devices_deactivated': devices_deactivated,
        'complete': complete,
    }
    logger.info(f"Sincronización de metadatos SCADA completada: {summary}")
    return summary


# Tarea periódica para sincronizar metadatos. El nombre debe conservarse porque
# CELERY_BEAT_SCHEDULE apunta a 'scada_proxy.tasks.sync_scada_metadata'.
@shared_task(bind=True, retry_backoff=60, max_retries=3,
             autoretry_for=(requests.exceptions.RequestException,))
def sync_scada_metadata(self):
    """Tarea Celery: delega en la implementación única sync_scada_metadata_core."""
    return sync_scada_metadata_core()


def _parse_measurement_date(date_str):
    """Parsea la fecha de una medición del connector a datetime aware (Bogotá)."""
    dt = parse_datetime(date_str) if date_str else None
    if dt is None:
        return None
    if is_naive(dt):
        return make_aware(dt, timezone=COLOMBIA_TZ)
    return dt.astimezone(COLOMBIA_TZ)


def _iter_measurement_pages(token, device_scada_id, from_dt, to_dt, page_size=1000):
    """Itera las páginas del connector y entrega listas de (dt, data_dict) válidas."""
    offset = 0
    while True:
        response = scada_client.get_measurements(
            token,
            device_id=device_scada_id,
            from_date=from_dt.isoformat(timespec='seconds'),
            to_date=to_dt.isoformat(timespec='seconds'),
            limit=page_size,
            offset=offset,
        )
        page = response.get('data', [])
        if not page:
            return

        rows = []
        for entry in page:
            data_dict = entry.get('data', {})
            dt = _parse_measurement_date(entry.get('date'))
            if dt is None or not data_dict:
                logger.warning(f"Medición incompleta o fecha inválida: {str(entry)[:200]}")
                continue
            rows.append((dt, data_dict))
        if rows:
            yield rows

        if len(page) < page_size:
            return
        offset += page_size


def upsert_measurements_page(device, rows, write_v1=None, write_v2=True):
    """Upsert masivo de una página de mediciones (v1 jsonb y/o v2 tipadas).

    `rows` es una lista de (datetime_aware, data_dict). Deduplica por fecha
    (última gana: el UNIQUE (device,date) no admite el mismo par dos veces en
    un solo ON CONFLICT). Devuelve el número de filas procesadas.

    Dual-write: v1 se controla con settings.MEASUREMENTS_WRITE_V1 (default
    True hasta el switchover); v2 siempre, salvo categoría desconocida.
    """
    if write_v1 is None:
        write_v1 = getattr(settings, 'MEASUREMENTS_WRITE_V1', True)

    deduped = {}
    for dt, data in rows:
        deduped[dt] = data
    if not deduped:
        return 0

    category_name = device.category.name if device.category_id else None
    v2_model = CATEGORY_TO_MODEL.get(category_name) if write_v2 else None
    v2_metrics = metrics_for_category(category_name) if v2_model else None
    if write_v2 and v2_model is None:
        logger.warning(
            f"Dispositivo {device.id} ({device.name}) con categoría desconocida "
            f"'{category_name}': se omite la escritura v2 de esta página."
        )

    with transaction.atomic():
        if write_v1:
            Measurement.objects.bulk_create(
                [Measurement(device=device, date=dt, data=data) for dt, data in deduped.items()],
                update_conflicts=True,
                unique_fields=['device', 'date'],
                update_fields=['data'],
            )
        if v2_model is not None:
            metric_set = set(v2_metrics)
            unknown = set()
            objs = []
            for dt, data in deduped.items():
                fields = {k: v for k, v in data.items() if k in metric_set}
                unknown.update(k for k in data if k not in metric_set)
                objs.append(v2_model(device=device, date=dt, **fields))
            v2_model.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=['device', 'date'],
                update_fields=v2_metrics,
            )
            if unknown:
                logger.warning(
                    f"Métricas desconocidas ignoradas en v2 para device {device.id} "
                    f"({category_name}): {sorted(unknown)} — si son nuevas del "
                    f"connector, añadirlas a measurements_schema.py + migración."
                )
    return len(deduped)


@shared_task(bind=True, retry_backoff=10, max_retries=5,
             autoretry_for=(requests.exceptions.RequestException,))
def fetch_and_save_measurements_for_device(self, device_scada_id: str, django_device_id: int, from_datetime_str: str, to_datetime_str: str):
    """
    Obtiene y guarda mediciones para un dispositivo SCADA.
    Upsert masivo por página (bulk_create con update_conflicts), dual-write
    v1 (jsonb) + v2 (tablas tipadas por categoría) durante la transición.
    """
    try:
        token = scada_client.get_token()
        device_instance = Device.objects.get(id=django_device_id)

        # Convertimos los strings a datetime con tz Colombia correctamente
        from_dt = datetime.fromisoformat(from_datetime_str)
        to_dt = datetime.fromisoformat(to_datetime_str)
        
        # Si las fechas no tienen timezone, asumir que están en Colombia
        if from_dt.tzinfo is None:
            from_dt = COLOMBIA_TZ.localize(from_dt)
        else:
            from_dt = from_dt.astimezone(COLOMBIA_TZ)
            
        if to_dt.tzinfo is None:
            to_dt = COLOMBIA_TZ.localize(to_dt)
        else:
            to_dt = to_dt.astimezone(COLOMBIA_TZ)

        logger.info(f"Obteniendo mediciones para dispositivo {device_scada_id} desde {from_dt} hasta {to_dt} (hora Colombia)")

        total_rows = 0
        for rows in _iter_measurement_pages(token, device_scada_id, from_dt, to_dt):
            total_rows += upsert_measurements_page(device_instance, rows)

        logger.info(f"Dispositivo {device_scada_id}: {total_rows} mediciones upserted (bulk)")

    except Device.DoesNotExist:
        logger.error(f"Dispositivo con id {django_device_id} no encontrado.")
    except Exception as e:
        logger.error(f"Error al obtener/guardar mediciones: {e}", exc_info=True)
        raise

@shared_task
def fetch_historical_measurements_for_all_devices(time_range_seconds: int):
    """
    Lanza subtareas para obtener mediciones históricas de todos los dispositivos en el rango dado.
    Permite cancelar la ejecución a través de la tabla TaskProgress.
    """
    time_range = timedelta(seconds=time_range_seconds)

    # Tiempo actual en zona horaria de Colombia
    now_colombia = get_colombia_now()
    from_date = now_colombia - time_range

    logger.info(
        f"Iniciando la obtención de mediciones históricas "
        f"para los últimos {time_range}. "
        f"Rango: {from_date} -> {now_colombia} (hora Colombia)"
    )

    devices = Device.objects.filter(is_active=True)
    if not devices.exists():
        logger.warning("No hay dispositivos activos registrados en la base de datos.")
        return

    from celery import current_task
    task_progress = TaskProgress.objects.filter(task_id=current_task.request.id).first() if current_task else None

    for device in devices:
        # Verificar si se canceló la tarea
        if task_progress:
            task_progress.refresh_from_db()
            if getattr(task_progress, "is_cancelled", False):
                logger.warning(f"Tarea {task_progress.task_id} cancelada. Abortando ejecución.")
                task_progress.status = 'CANCELLED'
                task_progress.message = 'La tarea fue cancelada mientras se ejecutaba.'
                task_progress.save(update_fields=['status', 'message'])
                return

        # Encolar subtarea por dispositivo
        fetch_and_save_measurements_for_device.delay(
            device_scada_id=device.scada_id,
            django_device_id=device.id,
            from_datetime_str=from_date.isoformat(),
            to_datetime_str=now_colombia.isoformat()
        )
        logger.info(
            f"Tarea creada para dispositivo {device.name} ({device.scada_id}) "
            f"desde {from_date} hasta {now_colombia} (hora Colombia)."
        )

        # Actualizar progreso
        if task_progress:
            task_progress.processed_devices += 1
            task_progress.save(update_fields=['processed_devices'])

    if task_progress:
        task_progress.status = 'SUCCESS'
        task_progress.message = 'Todas las subtareas para obtener mediciones han sido encoladas.'
        task_progress.save(update_fields=['status', 'message'])

    logger.info("Todas las subtareas para obtener mediciones han sido encoladas.")

@shared_task(bind=True, retry_backoff=30, max_retries=3)
def check_devices_status(self):
    """
    Verifica el estado de los dispositivos y actualiza su información básica
    sin necesidad de sincronización completa.
    """
    try:
        token = scada_client.get_token()
        logger.info("Iniciando verificación de estado de dispositivos")
        
        # Obtener dispositivos activos
        active_devices = Device.objects.filter(is_active=True)
        updated_count = 0
        
        for device in active_devices:
            try:
                # Obtener información actualizada del dispositivo desde SCADA
                # Nota: Esto asume que tienes un endpoint para obtener un dispositivo específico
                # Si no lo tienes, puedes usar get_devices con filtros
                devices_data = scada_client.get_devices(
                    token,
                    device_name=device.name
                ).get('data', []) or []

                # Validar por scada_id: un filtro por nombre puede devolver varios
                # dispositivos, así que tomar [0] podría aplicar datos de OTRO dispositivo.
                device_data = next(
                    (d for d in devices_data if str(d.get('id')) == device.scada_id),
                    None
                )

                if device_data:
                    # Actualizar solo campos básicos sin tocar las relaciones
                    # IMPORTANTE: Preservar category e institution existentes
                    device.name = device_data.get('name', device.name)
                    device.status = device_data.get('status', device.status)
                    
                    # NO actualizar category e institution aquí para evitar sobrescribirlos como null
                    # Solo actualizar si realmente tenemos datos válidos de SCADA
                    if device_data.get('category') and isinstance(device_data['category'], dict):
                        category_scada_id = str(device_data['category'].get('id'))
                        if category_scada_id:
                            try:
                                category_obj = DeviceCategory.objects.get(scada_id=category_scada_id)
                                device.category = category_obj
                                logger.debug(f"Actualizada categoría para {device.name}: {category_obj.name}")
                            except DeviceCategory.DoesNotExist:
                                logger.warning(f"Categoría SCADA {category_scada_id} no encontrada para {device.name}")
                    
                    if device_data.get('institution') and isinstance(device_data['institution'], dict):
                        institution_scada_id = str(device_data['institution'].get('id'))
                        if institution_scada_id:
                            try:
                                institution_obj = Institution.objects.get(scada_id=institution_scada_id)
                                device.institution = institution_obj
                                logger.debug(f"Actualizada institución para {device.name}: {institution_obj.name}")
                            except Institution.DoesNotExist:
                                logger.warning(f"Institución SCADA {institution_scada_id} no encontrada para {device.name}")
                    
                    device.save()
                    updated_count += 1
                    
            except Exception as e:
                logger.warning(f"Error al actualizar dispositivo {device.name}: {e}")
                continue
        
        logger.info(f"Verificación completada. {updated_count} dispositivos actualizados.")
        
    except Exception as e:
        logger.error(f"Error en verificación de dispositivos: {e}")
        raise self.retry(exc=e, countdown=self.request.retries * 30)

# NOTA: la antigua tarea 'sync_scada_metadata_enhanced' se eliminó. Su lógica
# correcta (mapeo de category/institution anidados) quedó unificada en
# sync_scada_metadata_core(), usada por la tarea sync_scada_metadata y por
# SyncLocalDevicesView.


@shared_task(bind=True, retry_backoff=30, max_retries=3)
def repair_device_relationships(self):
    """
    Repara automáticamente las relaciones faltantes de categoría e institución
    en dispositivos que las hayan perdido.
    """
    try:
        logger.info("Iniciando reparación automática de relaciones de dispositivos")
        
        # Buscar dispositivos con relaciones faltantes
        devices_with_issues = Device.objects.filter(
            models.Q(category__isnull=True) | models.Q(institution__isnull=True)
        ).select_related('category', 'institution')
        
        if not devices_with_issues.exists():
            logger.info("No se encontraron dispositivos con relaciones faltantes")
            return
        
        logger.info(f"Se encontraron {devices_with_issues.count()} dispositivos con relaciones faltantes")
        
        repaired_count = 0
        failed_count = 0
        
        for device in devices_with_issues:
            try:
                repaired = False
                
                # Intentar encontrar categoría por nombre del dispositivo
                if not device.category:
                    if 'medidor' in device.name.lower() or 'meter' in device.name.lower():
                        category = DeviceCategory.objects.filter(name__icontains='electricmeter').first()
                        if category:
                            device.category = category
                            repaired = True
                            logger.info(f"Reparada categoría para {device.name}: {category.name}")
                    elif 'inversor' in device.name.lower() or 'inverter' in device.name.lower():
                        category = DeviceCategory.objects.filter(name__icontains='inverter').first()
                        if category:
                            device.category = category
                            repaired = True
                            logger.info(f"Reparada categoría para {device.name}: {category.name}")
                    elif 'estación' in device.name.lower() or 'weather' in device.name.lower():
                        category = DeviceCategory.objects.filter(name__icontains='weatherstation').first()
                        if category:
                            device.category = category
                            repaired = True
                            logger.info(f"Reparada categoría para {device.name}: {category.name}")
                
                # Intentar encontrar institución por nombre del dispositivo
                if not device.institution:
                    for institution in Institution.objects.all():
                        if institution.name.lower() in device.name.lower():
                            device.institution = institution
                            repaired = True
                            logger.info(f"Reparada institución para {device.name}: {institution.name}")
                            break
                
                if repaired:
                    device.save()
                    repaired_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"No se pudo reparar {device.name} - nombre: '{device.name}'")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error al reparar dispositivo {device.name}: {e}")
        
        logger.info(f"Reparación completada: {repaired_count} reparados, {failed_count} fallidos")
        
    except Exception as e:
        logger.error(f"Error en reparación automática de relaciones: {e}")
        raise self.retry(exc=e, countdown=self.request.retries * 30)


# Días de histórico a traer en el bootstrap (mediciones y cálculos).
BOOTSTRAP_HISTORICAL_DAYS = 365  # 1 año

# Segundos de espera antes de encolar cálculos de Medidores/Inversores/Estaciones,
# para dar tiempo a que el fetch histórico llene Measurement.
BOOTSTRAP_COMPONENT_CALCULATION_DELAY = 3600  # 1 hora


@shared_task(bind=True)
def bootstrap_scada_data(self):
    """
    Carga inicial en frío: sincroniza metadatos SCADA, encola fetch del último año (365 días),
    cálculo de KPIs y datos diarios, y (con delay) cálculos para Medidores, Inversores y Estaciones.
    Los cálculos por componente se encolan tras BOOTSTRAP_COMPONENT_CALCULATION_DELAY
    para que el histórico de SCADA tenga tiempo de llenarse.
    """
    logger.info("=== BOOTSTRAP: Iniciando carga inicial de datos SCADA ===")
    try:
        # 1. Sincronizar metadatos (instituciones, categorías, dispositivos)
        sync_scada_metadata.apply()
        logger.info("Bootstrap: sync_scada_metadata completado.")

        # 2. Encolar obtención de mediciones históricas (último año)
        time_range_seconds = int(timedelta(days=BOOTSTRAP_HISTORICAL_DAYS).total_seconds())
        fetch_historical_measurements_for_all_devices.delay(time_range_seconds)
        logger.info(f"Bootstrap: encolado fetch histórico ({BOOTSTRAP_HISTORICAL_DAYS} días = {time_range_seconds} s).")

        end_date = get_colombia_now()
        start_date = end_date - timedelta(days=BOOTSTRAP_HISTORICAL_DAYS)
        start_str = start_date.date().isoformat()
        end_str = end_date.date().isoformat()

        # 3. Encolar cálculo de KPIs mensuales y datos diarios (1 año)
        from indicators.tasks import (
            calculate_monthly_consumption_kpi,
            calculate_and_save_daily_data,
            calculate_electrical_data,
            calculate_inverter_data,
            calculate_weather_station_indicators,
        )

        calculate_monthly_consumption_kpi.delay()
        calculate_and_save_daily_data.delay(
            start_date_str=start_str,
            end_date_str=end_str,
        )
        logger.info(f"Bootstrap: encolados calculate_monthly_consumption_kpi y calculate_and_save_daily_data ({BOOTSTRAP_HISTORICAL_DAYS} días).")

        # 4. Encolar cálculos para Medidores, Inversores y Estaciones (después de llenar histórico)
        # Se ejecutan con delay para dar tiempo al fetch de mediciones por dispositivo.
        calculate_electrical_data.apply_async(
            kwargs={
                "time_range": "daily",
                "start_date_str": start_str,
                "end_date_str": end_str,
            },
            countdown=BOOTSTRAP_COMPONENT_CALCULATION_DELAY,
        )
        calculate_inverter_data.apply_async(
            kwargs={
                "time_range": "daily",
                "start_date_str": start_str,
                "end_date_str": end_str,
            },
            countdown=BOOTSTRAP_COMPONENT_CALCULATION_DELAY,
        )
        calculate_weather_station_indicators.apply_async(
            kwargs={
                "time_range": "daily",
                "start_date_str": start_str,
                "end_date_str": end_str,
            },
            countdown=BOOTSTRAP_COMPONENT_CALCULATION_DELAY,
        )
        logger.info(
            f"Bootstrap: encolados cálculos Medidores/Inversores/Estaciones ({BOOTSTRAP_HISTORICAL_DAYS} días, delay {BOOTSTRAP_COMPONENT_CALCULATION_DELAY}s)."
        )
        logger.info("=== BOOTSTRAP: Carga inicial encolada correctamente ===")
    except Exception as e:
        logger.error(f"Bootstrap SCADA fallido: {e}", exc_info=True)
        raise