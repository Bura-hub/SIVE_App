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
from .scada_client import ScadaConnectorClient
from .models import Institution, DeviceCategory, Device, Measurement, TaskProgress

logger = logging.getLogger(__name__)
scada_client = ScadaConnectorClient()

# Zona horaria de Colombia
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def get_colombia_now():
    """Obtiene la fecha y hora actual en zona horaria de Colombia"""
    return dj_timezone.now().astimezone(COLOMBIA_TZ)

# Tarea para sincronizar metadatos (instituciones y categorías de dispositivos)
@shared_task(bind=True, retry_backoff=60, max_retries=3)
def sync_scada_metadata(self):
    try:
        token = scada_client.get_token()

        # Sincronizar Instituciones
        institutions_data = scada_client.get_institutions(token).get('data', [])
        for inst_data in institutions_data:
            Institution.objects.update_or_create(
                scada_id=str(inst_data['id']),
                defaults={'name': inst_data['name']}
            )
        logger.info(f"Sincronizadas {len(institutions_data)} instituciones.")

        # Sincronizar Categorías de Dispositivos
        categories_data = scada_client.get_device_categories(token).get('data', [])
        for cat_data in categories_data:
            DeviceCategory.objects.update_or_create(
                scada_id=str(cat_data['id']),
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data.get('description', '')
                }
            )
        logger.info(f"Sincronizadas {len(categories_data)} categorías de dispositivos.")

        # Sincronizar Dispositivos (todos los que la API SCADA liste)
        # Puede que necesites paginar esta llamada si hay muchos dispositivos
        all_devices_data = scada_client.get_devices(token).get('data', []) # Asume que esta llamada no necesita category/institution_id para listar todos
        existing_scada_device_ids = set(Device.objects.values_list('scada_id', flat=True))
        fetched_scada_device_ids = set()

        for device_data in all_devices_data:
            fetched_scada_device_ids.add(str(device_data['id']))
            category_obj = None
            if device_data.get('category_id'): # Asume que la API de dispositivos devuelve 'category_id'
                try:
                    category_obj = DeviceCategory.objects.get(scada_id=str(device_data['category_id']))
                except DeviceCategory.DoesNotExist:
                    logger.warning(f"Categoría {device_data['category_id']} no encontrada para el dispositivo {device_data['name']}. Sincroniza las categorías primero.")

            institution_obj = None
            if device_data.get('institution_id'): # Asume que la API de dispositivos devuelve 'institution_id'
                try:
                    institution_obj = Institution.objects.get(scada_id=str(device_data['institution_id']))
                except Institution.DoesNotExist:
                    logger.warning(f"Institución {device_data['institution_id']} no encontrada para el dispositivo {device_data['name']}. Sincroniza las instituciones primero.")

            device, created = Device.objects.update_or_create(
                scada_id=str(device_data['id']),
                defaults={
                    'name': device_data['name'],
                    'status': device_data.get('status', ''),
                    'is_active': True, # Asumimos que los dispositivos fetched están activos
                    # IMPORTANTE: Solo incluir category e institution si tenemos objetos válidos
                }
            )
            
            # Actualizar relaciones solo si tenemos objetos válidos
            if category_obj:
                device.category = category_obj
            if institution_obj:
                device.institution = institution_obj
            
            # Solo guardar si hubo cambios en las relaciones
            if category_obj or institution_obj:
                device.save()
            
            if created:
                logger.info(f"Dispositivo '{device.name}' ({device.scada_id}) creado/actualizado.")

        # Desactivar dispositivos que ya no existen en la API SCADA
        devices_to_deactivate = existing_scada_device_ids - fetched_scada_device_ids
        if devices_to_deactivate:
            Device.objects.filter(scada_id__in=list(devices_to_deactivate)).update(is_active=False)
            logger.info(f"Desactivados {len(devices_to_deactivate)} dispositivos que ya no se encuentran en la API SCADA.")


    except requests.exceptions.RequestException as e:
        logger.error(f"Error de red/API al sincronizar metadatos: {e}")
        raise self.retry(exc=e, countdown=self.request.retries * 60) # Reintentar con backoff
    except Exception as e:
        logger.error(f"Error inesperado al sincronizar metadatos: {e}", exc_info=True)
        raise


@shared_task(bind=True, retry_backoff=10, max_retries=5)
def fetch_and_save_measurements_for_device(self, device_scada_id: str, django_device_id: int, from_datetime_str: str, to_datetime_str: str):
    """
    Obtiene y guarda mediciones para un dispositivo SCADA.
    Cada medición se guarda como un solo JSON por timestamp.
    Usa update_or_create para evitar duplicados.
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

        page_size = 1000
        offset = 0
        total_created, total_updated = 0, 0

        while True:
            measurements_response = scada_client.get_measurements(
                token,
                device_id=device_scada_id,
                from_date=from_dt.isoformat(timespec='seconds'),
                to_date=to_dt.isoformat(timespec='seconds'),
                limit=page_size,
                offset=offset
            )
            measurements_data = measurements_response.get('data', [])

            if not measurements_data:
                break

            for measurement_entry in measurements_data:
                date_str = measurement_entry.get('date')
                data_dict = measurement_entry.get('data', {})

                if not date_str or not data_dict:
                    logger.warning(f"Medición incompleta: {measurement_entry}")
                    continue

                dt = parse_datetime(date_str)
                if dt is None:
                    logger.warning(f"Fecha inválida: {date_str}")
                    continue

                if is_naive(dt):  # Hacer aware si está en naive
                    dt = make_aware(dt, timezone=COLOMBIA_TZ)
                else:
                    # Convertir a zona horaria de Colombia si ya tiene timezone
                    dt = dt.astimezone(COLOMBIA_TZ)

                _, created = Measurement.objects.update_or_create(
                    device=device_instance,
                    date=dt,
                    defaults={"data": data_dict}
                )

                if created:
                    total_created += 1
                else:
                    total_updated += 1

            if len(measurements_data) < page_size:
                break
            offset += page_size

        logger.info(f"Dispositivo {device_scada_id}: {total_created} nuevas, {total_updated} actualizadas")

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
                ).get('data', [])
                
                if devices_data:
                    device_data = devices_data[0]  # Tomar el primer resultado
                    
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

@shared_task(bind=True, retry_backoff=60, max_retries=3)
def sync_scada_metadata_enhanced(self):
    """
    Versión mejorada de la sincronización que maneja mejor las relaciones
    y proporciona más información de logging.
    """
    try:
        token = scada_client.get_token()
        logger.info("Iniciando sincronización mejorada de metadatos SCADA")
        
        with transaction.atomic():
            # 1. Sincronizar categorías primero
            categories_data = scada_client.get_device_categories(token).get('data', [])
            category_map = {}
            for cat_data in categories_data:
                category_obj, created = DeviceCategory.objects.update_or_create(
                    scada_id=str(cat_data['id']),
                    defaults={
                        'name': cat_data['name'],
                        'description': cat_data.get('description', '')
                    }
                )
                category_map[str(cat_data['id'])] = category_obj
                if created:
                    logger.info(f"Nueva categoría creada: {cat_data['name']}")
            
            # 2. Sincronizar instituciones
            institutions_data = scada_client.get_institutions(token).get('data', [])
            institution_map = {}
            for inst_data in institutions_data:
                institution_obj, created = Institution.objects.update_or_create(
                    scada_id=str(inst_data['id']),
                    defaults={
                        'name': inst_data['name']
                    }
                )
                institution_map[str(inst_data['id'])] = institution_obj
                if created:
                    logger.info(f"Nueva institución creada: {inst_data['name']}")
            
            # 3. Sincronizar dispositivos con relaciones
            devices_data = scada_client.get_devices(token).get('data', [])
            existing_device_ids = set(Device.objects.values_list('scada_id', flat=True))
            fetched_device_ids = set()
            
            for device_data in devices_data:
                device_scada_id = str(device_data['id'])
                fetched_device_ids.add(device_scada_id)
                
                # Obtener categoría e institución
                category_obj = None
                institution_obj = None
                
                if device_data.get('category'):
                    category_scada_id = str(device_data['category']['id'])
                    category_obj = category_map.get(category_scada_id)
                    if not category_obj:
                        logger.warning(f"Categoría no encontrada para dispositivo {device_data['name']}")
                
                if device_data.get('institution'):
                    institution_scada_id = str(device_data['institution']['id'])
                    institution_obj = institution_map.get(institution_scada_id)
                    if not institution_obj:
                        logger.warning(f"Institución no encontrada para dispositivo {device_data['name']}")
                
                # Crear o actualizar dispositivo
                device, created = Device.objects.update_or_create(
                    scada_id=device_scada_id,
                    defaults={
                        'name': device_data['name'],
                        'status': device_data.get('status', ''),
                        'is_active': True
                        # IMPORTANTE: Solo incluir category e institution si tenemos objetos válidos
                    }
                )
                
                # Actualizar relaciones solo si tenemos objetos válidos
                if category_obj:
                    device.category = category_obj
                if institution_obj:
                    device.institution = institution_obj
                
                # Solo guardar si hubo cambios en las relaciones
                if category_obj or institution_obj:
                    device.save()
                
                if created:
                    logger.info(f"Nuevo dispositivo creado: {device.name}")
                elif device.category != category_obj or device.institution != institution_obj:
                    logger.info(f"Relaciones actualizadas para dispositivo: {device.name}")
            
            # 4. Desactivar dispositivos que ya no existen
            devices_to_deactivate = existing_device_ids - fetched_device_ids
            if devices_to_deactivate:
                Device.objects.filter(scada_id__in=list(devices_to_deactivate)).update(is_active=False)
                logger.info(f"Desactivados {len(devices_to_deactivate)} dispositivos obsoletos")
        
        logger.info("Sincronización mejorada completada exitosamente")
        
    except Exception as e:
        logger.error(f"Error en sincronización mejorada: {e}")
        raise self.retry(exc=e, countdown=self.request.retries * 60)

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