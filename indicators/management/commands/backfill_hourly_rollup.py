"""
Comando de backfill del rollup horario (vista horaria, Opción B).

Encola `calculate_hourly_rollup` en modo rango explícito (start_hour_str/end_hour_str)
por lotes de horas, igual estilo que `calculate_historical_electrical.py` pero
recorriendo horas en vez de días/meses. Lo corre el usuario manualmente tras desplegar
las migraciones (NUNCA se ejecuta migrate/flush automáticamente desde aquí).
"""
from datetime import datetime, timedelta

import pytz
from django.core.management.base import BaseCommand

from indicators.tasks import calculate_hourly_rollup


class Command(BaseCommand):
    help = (
        'Encola por lotes el backfill del rollup horario (HourlyMeterIndicators/'
        'HourlyInverterIndicators/HourlyWeatherIndicators) para un rango de fechas '
        '(hora de Bogotá, 00:00 del start-date a 23:00 del end-date).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            required=True,
            help='Fecha de inicio en formato YYYY-MM-DD (hora de Bogotá, 00:00).'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            required=True,
            help='Fecha de fin en formato YYYY-MM-DD (hora de Bogotá, incluye hasta las 23:00).'
        )
        parser.add_argument(
            '--institution-id',
            type=int,
            help='ID de la institución específica (opcional).'
        )
        parser.add_argument(
            '--device-id',
            type=str,
            help='SCADA ID del dispositivo específico (opcional).'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=24,
            help='Número de horas a procesar por lote/tarea Celery (default: 24 = 1 día).'
        )

    def handle(self, *args, **options):
        colombia_tz = pytz.timezone('America/Bogota')

        try:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'❌ Error en formato de fecha: {e}'))
            return

        institution_id = options.get('institution_id')
        device_id = options.get('device_id')
        batch_size = options['batch_size']

        if start_date > end_date:
            self.stdout.write(self.style.ERROR('❌ --start-date no puede ser posterior a --end-date.'))
            return

        if batch_size < 1:
            self.stdout.write(self.style.ERROR('❌ --batch-size debe ser al menos 1.'))
            return

        start_hour = colombia_tz.localize(datetime.combine(start_date, datetime.min.time()))
        # Última hora del día end_date: 23:00-24:00 (rango inclusivo, igual criterio
        # que colombia_day_range para el día completo).
        end_hour = colombia_tz.localize(datetime.combine(end_date, datetime.min.time())) + timedelta(hours=23)

        total_hours = int((end_hour - start_hour).total_seconds() // 3600) + 1

        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f'🚀 Iniciando backfill de rollup horario...\n'
                    f'📅 Rango: {start_hour.isoformat()} a {end_hour.isoformat()} ({total_hours} horas)\n'
                    f'🏢 Institución: {institution_id if institution_id else "Todas"}\n'
                    f'🔌 Dispositivo: {device_id if device_id else "Todos"}\n'
                    f'📦 Tamaño de lote: {batch_size} horas'
                )
            )

            current_start = start_hour
            total_batches = 0

            while current_start <= end_hour:
                current_end = min(current_start + timedelta(hours=batch_size - 1), end_hour)

                self.stdout.write(
                    f'📊 Procesando lote {total_batches + 1}: '
                    f'{current_start.isoformat()} a {current_end.isoformat()}'
                )

                task = calculate_hourly_rollup.delay(
                    start_hour_str=current_start.isoformat(),
                    end_hour_str=current_end.isoformat(),
                    institution_id=institution_id,
                    device_id=device_id,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Lote {total_batches + 1} enviado a Celery (Task ID: {task.id})'
                    )
                )

                total_batches += 1
                current_start = current_end + timedelta(hours=1)

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎉 ¡Backfill de rollup horario encolado!\n'
                    f'📊 Total de lotes enviados: {total_batches}\n'
                    f'⏰ Total de horas a procesar: {total_hours}\n'
                    f'🔍 Monitorea el progreso en Celery (logs de celery_worker) y en la BD '
                    f'(HourlyMeterIndicators/HourlyInverterIndicators/HourlyWeatherIndicators).'
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error inesperado: {e}'))
