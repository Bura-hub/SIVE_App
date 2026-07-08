# Comando de gestión para encolar la carga inicial de datos SCADA cuando la BD está vacía.
from django.core.management.base import BaseCommand
from scada_proxy.models import Measurement, Device
from indicators.models import MonthlyConsumptionKPI
from scada_proxy.tasks import bootstrap_scada_data


class Command(BaseCommand):
    help = (
        'Encola la tarea de bootstrap SCADA (sync + fetch 1 año histórico + cálculos) '
        'si no hay datos. Útil para arranque en frío o después de migraciones.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Encolar bootstrap aunque ya existan datos.',
        )

    def handle(self, *args, **options):
        force = options['force']
        has_measurements = Measurement.objects.exists()
        has_devices = Device.objects.filter(is_active=True).exists()
        has_kpis = MonthlyConsumptionKPI.objects.exists()

        if not force and has_measurements and has_kpis:
            self.stdout.write(
                self.style.SUCCESS('Ya hay datos (mediciones y KPIs). No se encola bootstrap.')
            )
            return

        if not force and not has_devices:
            self.stdout.write(
                self.style.WARNING('No hay dispositivos. Encolando bootstrap para sincronizar y cargar datos.')
            )
        elif not force:
            self.stdout.write(
                self.style.WARNING('Pocos o ningún dato de indicadores. Encolando bootstrap.')
            )
        else:
            self.stdout.write(self.style.WARNING('--force: encolando bootstrap de todas formas.'))

        result = bootstrap_scada_data.delay()
        self.stdout.write(self.style.SUCCESS(f'Bootstrap encolado. Task ID: {result.id}'))
        self.stdout.write(
            'La sincronización y la carga de datos se ejecutarán en el worker de Celery.'
        )
