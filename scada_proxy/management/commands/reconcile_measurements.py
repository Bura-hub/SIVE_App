"""
Reconciliación manual de mediciones con el connector.

Usa la misma función que la tarea periódica reconcile_recent_measurements: por
dispositivo y día de Bogotá compara el conteo local con `meta.total` del
connector, re-descarga con upsert los días distintos y (salvo --no-recalc)
encola el recálculo solo de lo tocado.

Uso:
  python manage.py reconcile_measurements --from 2026-09-01 --to 2026-10-10
  python manage.py reconcile_measurements --from ... --to ... --devices 3,5,7 --no-recalc
  (--from y --to inclusive; --devices son IDs Django; por defecto, todos los activos)
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from scada_proxy.tasks import reconcile_measurements


class Command(BaseCommand):
    help = "Reconcilia las mediciones de SIVE con el connector, día a día, y recalcula lo tocado."

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='date_from', required=True, help='YYYY-MM-DD (inclusive)')
        parser.add_argument('--to', dest='date_to', required=True, help='YYYY-MM-DD (inclusive)')
        parser.add_argument('--devices', help='IDs Django separados por coma (default: todos los activos)')
        parser.add_argument('--no-recalc', action='store_true',
                            help='Solo reconciliar mediciones; no encolar el recálculo de indicadores')

    def handle(self, *args, **opts):
        try:
            date_from = datetime.strptime(opts['date_from'], '%Y-%m-%d').date()
            date_to = datetime.strptime(opts['date_to'], '%Y-%m-%d').date()
        except ValueError as e:
            raise CommandError(f"Fecha inválida: {e}")
        if date_from > date_to:
            raise CommandError("--from debe ser anterior o igual a --to")

        devices = None
        if opts['devices']:
            try:
                devices = [int(x) for x in opts['devices'].split(',') if x.strip()]
            except ValueError as e:
                raise CommandError(f"--devices inválido: {e}")

        results = reconcile_measurements(
            date_from, date_to, devices=devices, recalc=not opts['no_recalc'],
        )
        if not results:
            raise CommandError("No se revisó ningún dispositivo-día (¿dispositivos activos con categoría?).")

        by_device = {}
        for r in results:
            by_device.setdefault(r.device, []).append(r)

        self.stdout.write(f"Reconciliación {date_from} → {date_to}:")
        total_added = total_mismatch = 0
        for device, rows in sorted(by_device.items(), key=lambda kv: kv[0].id):
            refetched = [r for r in rows if r.refetched]
            added = sum(r.local_after - r.local_before for r in rows)
            mismatch = [r for r in rows if r.mismatch]
            total_added += added
            total_mismatch += len(mismatch)
            self.stdout.write(
                f"  [{device.id}] {device.name}: {len(rows)} días, {len(refetched)} re-descargados, "
                f"{added:+d} filas, {len(mismatch)} con diferencia"
            )
            for r in mismatch:
                remote = 'sin respuesta' if r.remote is None else r.remote
                self.stdout.write(self.style.ERROR(
                    f"      {r.day}: local {r.local_before} → {r.local_after}, connector {remote}"
                ))

        summary = (f"Total: {len(results)} dispositivo-días, {total_added:+d} filas, "
                   f"{total_mismatch} con diferencia persistente.")
        if total_mismatch:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
        if opts['no_recalc']:
            self.stdout.write("Recálculo omitido (--no-recalc).")
