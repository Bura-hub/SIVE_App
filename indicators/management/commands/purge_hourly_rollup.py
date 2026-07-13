"""
Comando MANUAL de purga del rollup horario (vista horaria, Opción B).

Decisión del usuario (ver diseño): retención de 18 meses, purga por comando manual,
SIN tarea periódica de Celery Beat. Borra por `hour__lt` en las 3 tablas dedicadas de
grano horario. Nunca toca las tablas diarias/mensuales existentes.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone

from indicators.models import (
    HourlyMeterIndicators,
    HourlyInverterIndicators,
    HourlyWeatherIndicators,
)

# 18 meses ~= 548 días (retención confirmada por el usuario).
DEFAULT_RETENTION_DAYS = 548


class Command(BaseCommand):
    help = (
        'Purga manualmente filas antiguas del rollup horario (HourlyMeterIndicators/'
        'HourlyInverterIndicators/HourlyWeatherIndicators). Retención por defecto: '
        f'{DEFAULT_RETENTION_DAYS} días (18 meses). Comando MANUAL: no existe tarea '
        'periódica que lo dispare automáticamente (decisión del proyecto).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-days',
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=(
                f'Borra filas con hour anterior a "ahora - N días" (default: '
                f'{DEFAULT_RETENTION_DAYS} = 18 meses).'
            )
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo reporta cuántas filas se borrarían en cada tabla, sin borrar nada.'
        )

    def handle(self, *args, **options):
        older_than_days = options['older_than_days']
        dry_run = options['dry_run']

        if older_than_days < 0:
            self.stdout.write(self.style.ERROR('❌ --older-than-days no puede ser negativo.'))
            return

        cutoff = django_timezone.now() - timedelta(days=older_than_days)

        self.stdout.write(
            f'🗑️  Purga de rollup horario: filas con hour < {cutoff.isoformat()} '
            f'(retención solicitada: {older_than_days} días)'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo --dry-run: no se borrará nada, solo se reporta.'))

        models_to_purge = [
            ('HourlyMeterIndicators', HourlyMeterIndicators),
            ('HourlyInverterIndicators', HourlyInverterIndicators),
            ('HourlyWeatherIndicators', HourlyWeatherIndicators),
        ]

        total_rows = 0

        for name, model in models_to_purge:
            queryset = model.objects.filter(hour__lt=cutoff)

            if dry_run:
                count = queryset.count()
                total_rows += count
                self.stdout.write(f'  {name}: {count} fila(s) se borrarían.')
            else:
                deleted, _ = queryset.delete()
                total_rows += deleted
                self.stdout.write(self.style.SUCCESS(f'  {name}: {deleted} fila(s) borradas.'))

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'\n🔍 Total (dry-run): {total_rows} fila(s) se borrarían en total.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Purga completada: {total_rows} fila(s) borradas en total.')
            )
