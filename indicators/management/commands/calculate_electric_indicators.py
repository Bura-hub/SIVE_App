from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from indicators.tasks import calculate_electric_meter_indicators
from scada_proxy.models import Device, Institution
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Calcula indicadores eléctricos para todos los medidores en un rango de fechas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Fecha de inicio (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='Fecha de fin (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--time-range',
            type=str,
            choices=['daily', 'monthly'],
            default='daily',
            help='Rango de tiempo para los cálculos (daily/monthly)',
        )
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución específica',
        )
        parser.add_argument(
            '--device-id',
            type=int,
            help='ID del dispositivo específico',
        )

    def handle(self, *args, **options):
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        time_range = options['time_range']
        institution_id = options['institution_id']
        device_id = options['device_id']

        # Si no se especifican fechas, usar el último mes
        if not start_date_str:
            end_date = timezone.localdate()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = start_date + timedelta(days=30)

        self.stdout.write(
            self.style.SUCCESS(
                f'Calculando indicadores eléctricos desde {start_date} hasta {end_date}'
            )
        )

        # Obtener dispositivos a procesar
        if device_id:
            devices = Device.objects.filter(id=device_id, category__name='electricMeter')
        elif institution_id:
            devices = Device.objects.filter(
                institution_id=institution_id,
                category__name='electricMeter'
            )
        else:
            devices = Device.objects.filter(category__name='electricMeter')

        self.stdout.write(f'Procesando {devices.count()} dispositivos...')

        # Calcular indicadores para cada dispositivo
        for device in devices:
            try:
                self.stdout.write(f'Procesando dispositivo: {device.name}')
                
                # Calcular para cada día en el rango
                current_date = start_date
                while current_date <= end_date:
                    if time_range == 'daily':
                        # Calcular indicadores diarios
                        calculate_electric_meter_indicators.delay(
                            device.id, 
                            current_date.strftime('%Y-%m-%d'), 
                            'daily'
                        )
                        current_date += timedelta(days=1)
                    else:
                        # Calcular indicadores mensuales
                        if current_date.day == 1:  # Solo el primer día del mes
                            calculate_electric_meter_indicators.delay(
                                device.id, 
                                current_date.strftime('%Y-%m-%d'), 
                                'monthly'
                            )
                        current_date += timedelta(days=1)

                self.stdout.write(
                    self.style.SUCCESS(f'✓ Dispositivo {device.name} procesado')
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error procesando {device.name}: {str(e)}')
                )
                logger.error(f'Error procesando dispositivo {device.name}: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso completado. Se han enviado tareas para calcular indicadores eléctricos.'
            )
        )
