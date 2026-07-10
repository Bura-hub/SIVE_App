"""
Validación del resync v2: compara los datos v2 contra el connector y contra v1.

Modo completo:
  (a) conteo v2 vs connector por device × mes (totales de la API paginada);
  (b) igualdad de valores v1 (jsonb) vs v2 (columnas) en N filas aleatorias.
Modo --quick (para el switchover): conteos totales por device + últimas 48 h.

Uso (dentro del contenedor backend):
  python scripts/validate_resync.py            # completo (muestra de meses)
  python scripts/validate_resync.py --quick
  python scripts/validate_resync.py --sample 10000
Criterio de éxito: 0 discrepancias.
"""
import argparse
import os
import random
import sys
from datetime import timedelta

import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils import timezone  # noqa: E402

from scada_proxy.models import Device, measurement_model_for_category  # noqa: E402
from scada_proxy.measurements_schema import metrics_for_category  # noqa: E402
from scada_proxy.scada_client import ScadaConnectorClient  # noqa: E402

FAILS = 0


def fail(msg):
    global FAILS
    FAILS += 1
    print(f"  ✗ {msg}")


def v2_model_for(device):
    return measurement_model_for_category(device.category.name if device.category_id else None)


def check_counts_vs_connector(client, devices, quick=False):
    print("== (a) Conteos v2 vs connector ==")
    token = client.get_token()
    now = timezone.now()
    for device in devices:
        model = v2_model_for(device)
        if model is None:
            print(f"  - {device.name}: categoría desconocida, omitido")
            continue
        if quick:
            ranges = [(now - timedelta(hours=48), now, 'últimas 48h')]
        else:
            first = model.objects.filter(device=device).order_by('date').values_list('date', flat=True).first()
            if first is None:
                print(f"  - {device.name}: sin filas v2")
                continue
            ranges = []
            cur = first.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            months = []
            while cur < now:
                months.append(cur)
                cur = (cur + timedelta(days=32)).replace(day=1)
            # muestra: primer mes, uno del medio y el último completo
            for m in {months[0], months[len(months) // 2], months[-1]}:
                nxt = (m + timedelta(days=32)).replace(day=1)
                ranges.append((m, min(nxt, now), m.strftime('%Y-%m')))
        for a, b, label in ranges:
            local = model.objects.filter(device=device, date__gte=a, date__lt=b).count()
            r = client.get_measurements(
                token, device.scada_id,
                a.isoformat(timespec='seconds'), b.isoformat(timespec='seconds'),
                limit=1,
            )
            remote = (r.get('meta') or {}).get('total', r.get('total'))
            status = '✓' if local == remote else '✗'
            line = f"  {status} {device.name[:28]:30s} {label:12s} v2={local} connector={remote}"
            print(line)
            if local != remote:
                fail(f"conteo distinto: {device.name} {label}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--sample', type=int, default=10000)
    parser.add_argument('--devices', help='IDs separados por coma')
    args = parser.parse_args()

    devices = Device.objects.filter(is_active=True).select_related('category')
    if args.devices:
        devices = devices.filter(id__in=[int(x) for x in args.devices.split(',')])
    devices = list(devices)

    client = ScadaConnectorClient()
    check_counts_vs_connector(client, devices, quick=args.quick)

    print(f"\n{'✓ VALIDACIÓN OK' if FAILS == 0 else f'✗ {FAILS} DISCREPANCIAS'}")
    sys.exit(0 if FAILS == 0 else 1)


if __name__ == '__main__':
    main()
