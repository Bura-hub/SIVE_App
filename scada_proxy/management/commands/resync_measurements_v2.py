"""
Resync del histórico de mediciones al esquema v2 (tablas tipadas).

Itera device × chunk de días, descarga del connector y hace upsert masivo
SOLO en v2 (no toca Measurement v1). Reanudable: cada chunk completado se
registra en MeasurementSyncChunk y se salta en corridas posteriores.

Uso:
  python manage.py resync_measurements_v2 --from 2025-02-25 --to 2026-07-10
  python manage.py resync_measurements_v2 --from ... --to ... --devices 3,5,7
  python manage.py resync_measurements_v2 --from ... --to ... --category inverter
  (--chunk-days 7 por defecto; --force re-procesa chunks ya 'done')
"""
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from scada_proxy.models import Device, MeasurementSyncChunk
from scada_proxy.scada_client import ScadaConnectorClient
from scada_proxy.tasks import (
    COLOMBIA_TZ, _iter_measurement_pages, upsert_measurements_page,
)


class Command(BaseCommand):
    help = "Resincroniza el histórico de mediciones del connector al esquema v2 (reanudable)."

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='date_from', required=True, help='YYYY-MM-DD (inclusive)')
        parser.add_argument('--to', dest='date_to', required=True, help='YYYY-MM-DD (exclusive)')
        parser.add_argument('--devices', help='IDs Django separados por coma (default: todos los activos)')
        parser.add_argument('--category', help='Solo esta categoría (electricMeter|inverter|weatherStation)')
        parser.add_argument('--chunk-days', type=int, default=7)
        parser.add_argument('--sleep', type=float, default=0.1, help='Pausa entre chunks (s), para no saturar el connector')
        parser.add_argument('--force', action='store_true', help='Re-procesar chunks ya done')

    def handle(self, *args, **opts):
        try:
            start = COLOMBIA_TZ.localize(datetime.strptime(opts['date_from'], '%Y-%m-%d'))
            end = COLOMBIA_TZ.localize(datetime.strptime(opts['date_to'], '%Y-%m-%d'))
        except ValueError as e:
            raise CommandError(f"Fecha inválida: {e}")
        if start >= end:
            raise CommandError("--from debe ser anterior a --to")

        devices = Device.objects.filter(is_active=True).select_related('category')
        if opts['devices']:
            devices = devices.filter(id__in=[int(x) for x in opts['devices'].split(',')])
        if opts['category']:
            devices = devices.filter(category__name=opts['category'])
        devices = list(devices)
        if not devices:
            raise CommandError("No hay dispositivos que coincidan con los filtros.")

        chunk = timedelta(days=opts['chunk_days'])
        total_chunks = sum(1 for _ in self._iter_ranges(start, end, chunk)) * len(devices)
        self.stdout.write(f"{len(devices)} dispositivos × chunks de {opts['chunk_days']}d "
                          f"({opts['date_from']} → {opts['date_to']}) = {total_chunks} chunks")

        client = ScadaConnectorClient()
        done = skipped = failed = 0
        rows_total = 0
        t0 = time.monotonic()

        for device in devices:
            for c_start, c_end in self._iter_ranges(start, end, chunk):
                record, _ = MeasurementSyncChunk.objects.get_or_create(
                    device=device, start=c_start, end=c_end,
                )
                if record.status == 'done' and not opts['force']:
                    skipped += 1
                    continue
                try:
                    token = client.get_token()
                    rows = 0
                    for page in _iter_measurement_pages(token, device.scada_id, c_start, c_end):
                        rows += upsert_measurements_page(device, page)
                    record.status = 'done'
                    record.rows = rows
                    record.save(update_fields=['status', 'rows', 'updated_at'])
                    done += 1
                    rows_total += rows
                except Exception as e:
                    record.status = 'failed'
                    record.save(update_fields=['status', 'updated_at'])
                    failed += 1
                    self.stderr.write(f"FALLO {device.name} {c_start:%Y-%m-%d}..{c_end:%Y-%m-%d}: {e}")
                processed = done + skipped + failed
                if processed % 25 == 0 or processed == total_chunks:
                    rate = processed / max(time.monotonic() - t0, 1e-6)
                    eta_s = (total_chunks - processed) / max(rate, 1e-6)
                    self.stdout.write(
                        f"[{processed}/{total_chunks}] done={done} skip={skipped} fail={failed} "
                        f"filas={rows_total} ETA={eta_s/60:.1f} min"
                    )
                time.sleep(opts['sleep'])

        self.stdout.write(self.style.SUCCESS(
            f"Resync terminado: done={done} skipped={skipped} failed={failed} filas={rows_total}"
        ))
        if failed:
            self.stdout.write(self.style.WARNING(
                "Hay chunks failed: re-ejecuta el mismo comando (reanuda solo lo pendiente)."
            ))

    @staticmethod
    def _iter_ranges(start, end, chunk):
        cur = start
        while cur < end:
            nxt = min(cur + chunk, end)
            yield cur, nxt
            cur = nxt
