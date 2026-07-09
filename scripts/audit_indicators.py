#!/usr/bin/env python
"""
Auditoría de indicadores de energía de SIVE.

Inspirado en los scripts data_quality_audit.py / audit_clean.py de la tesis
Optimalidad-p2p-col: valida los datos crudos, determina empíricamente el intervalo
de muestreo (Δt) y las UNIDADES de la potencia (W vs kW), y recalcula el consumo y
la generación con la fórmula canónica Σ(P)·Δt/1000 para compararlos contra lo que
el sistema tiene almacenado (MonthlyConsumptionKPI / DailyChartData) y contra los
contadores acumulados (ElectricMeterEnergyConsumption).

USO (dentro del contenedor backend):
    docker compose -f docker-compose.prod.yml exec backend python scripts/audit_indicators.py
    # opcional: acotar a un mes concreto
    docker compose -f docker-compose.prod.yml exec backend python scripts/audit_indicators.py --days 30

Solo LEE la base de datos; no escribe nada.
"""
import os
import sys
import argparse
from datetime import timedelta

# --- Bootstrap de Django (permite ejecutarlo como script suelto) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django  # noqa: E402
django.setup()  # noqa: E402

from django.db.models import Sum, Count, Min, Max  # noqa: E402

from scada_proxy.models import (  # noqa: E402
    Device,
    MeterMeasurement,
    InverterMeasurement,
    WeatherStationMeasurement,
    CATEGORY_TO_MODEL,
)
from indicators.models import (  # noqa: E402
    MonthlyConsumptionKPI,
    DailyChartData,
    ElectricMeterEnergyConsumption,
)
from indicators.energy import (  # noqa: E402
    consumption_energy_kwh,
    generation_energy_kwh,
    energy_kwh_from_power_sum,
    SAMPLE_INTERVAL_HOURS,
    POWER_UNIT_KW,
    POWER_UNIT_WATTS,
)


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def power_sum(qs, field):
    """Σ de una columna de potencia (v2, tipada), ignorando nulos."""
    return qs.filter(**{f"{field}__isnull": False}).aggregate(s=Sum(field))["s"]


def measurement_model(device):
    """Modelo de mediciones v2 según la categoría del dispositivo."""
    category_name = device.category.name if device.category else None
    return CATEGORY_TO_MODEL.get(category_name)


def detect_delta_t(device, sample=2000):
    """Estima Δt (horas) como la mediana de las diferencias entre mediciones
    consecutivas de un dispositivo."""
    model = measurement_model(device)
    if model is None:
        return None
    dates = list(
        model.objects.filter(device=device)
        .order_by("-date")
        .values_list("date", flat=True)[:sample]
    )
    if len(dates) < 3:
        return None
    dates.sort()
    diffs = [
        (dates[i + 1] - dates[i]).total_seconds()
        for i in range(len(dates) - 1)
        if (dates[i + 1] - dates[i]).total_seconds() > 0
    ]
    if not diffs:
        return None
    diffs.sort()
    median_s = diffs[len(diffs) // 2]
    return median_s / 3600.0


def main():
    parser = argparse.ArgumentParser(description="Auditoría de indicadores de energía SIVE")
    parser.add_argument("--days", type=int, default=30,
                        help="Ventana de días hacia atrás a auditar (default 30).")
    args = parser.parse_args()

    hr("CONFIGURACIÓN DE LA FÓRMULA CANÓNICA (indicators/energy.py)")
    print(f"  SAMPLE_INTERVAL_HOURS (Δt) = {SAMPLE_INTERVAL_HOURS:.6f} h "
          f"({SAMPLE_INTERVAL_HOURS*60:.1f} min)  →  {1/SAMPLE_INTERVAL_HOURS:.0f} muestras/hora")
    print(f"  Unidad consumo (totalActivePower): factor {POWER_UNIT_KW}  (1 = kW, sin /1000)")
    print(f"  Unidad generación (acPower):       factor {POWER_UNIT_WATTS}  (1000 = W, /1000)")

    meters = list(Device.objects.filter(category__name="electricMeter"))
    inverters = list(Device.objects.filter(category__name="inverter"))
    hr("INVENTARIO")
    total_measurements = (
        MeterMeasurement.objects.count()
        + InverterMeasurement.objects.count()
        + WeatherStationMeasurement.objects.count()
    )
    print(f"  Medidores eléctricos: {len(meters)}")
    print(f"  Inversores:           {len(inverters)}")
    print(f"  Mediciones totales:   {total_measurements:,}")

    # ---------- 1. Δt empírico ----------
    hr("1. INTERVALO DE MUESTREO (Δt) EMPÍRICO")
    deltas = []
    for d in (meters + inverters)[:10]:
        dt = detect_delta_t(d)
        if dt:
            deltas.append(dt)
            print(f"  {d.name[:40]:40s}  Δt ≈ {dt*60:.2f} min")
    if deltas:
        deltas.sort()
        med = deltas[len(deltas) // 2]
        print(f"\n  Δt mediano observado ≈ {med*60:.2f} min "
              f"(la fórmula asume {SAMPLE_INTERVAL_HOURS*60:.1f} min)")
        if abs(med - SAMPLE_INTERVAL_HOURS) > SAMPLE_INTERVAL_HOURS * 0.25:
            print("  ⚠️  El Δt real difiere >25% del asumido: revisar SAMPLE_INTERVAL_HOURS.")
    else:
        print("  (sin datos suficientes para estimar Δt)")

    # ---------- 2. Calidad de datos (potencia) ----------
    hr("2. CALIDAD DE DATOS — potencia activa (medidores)")
    for model, field, label, devs in (
            (MeterMeasurement, "totalActivePower", "totalActivePower", meters),
            (InverterMeasurement, "acPower", "acPower", inverters)):
        qs = model.objects.filter(device__in=devs, **{f"{field}__isnull": False})
        agg = qs.aggregate(
            n=Count("id"),
            mn=Min(field),
            mx=Max(field),
        )
        n = agg["n"] or 0
        if not n:
            print(f"  {label}: sin datos")
            continue
        neg = qs.filter(**{f"{field}__lt": 0}).count()
        # magnitud típica: media
        avg = (power_sum(qs, field) or 0.0) / n
        print(f"  {label}: n={n:,}  min={agg['mn']:.2f}  max={agg['mx']:.2f}  "
              f"media={avg:.2f}  negativos={neg}")
        print(f"     → magnitud media {avg:.1f}: "
              + ("parece Watts (>1000)" if avg > 1000 else
                 "parece kW (<100)" if avg < 100 else "ambiguo (100–1000)"))

    # ---------- 3. Determinación de unidades vs contadores ----------
    hr("3. UNIDADES (W vs kW): integración de potencia vs contadores acumulados")
    # Rangos aware Bogotá equivalentes al antiguo date__date / date__date__range
    from indicators.tasks import colombia_day_range  # import tardío
    ec = ElectricMeterEnergyConsumption.objects.filter(time_range="daily").order_by("-date")
    checked = 0
    ratios = []
    for rec in ec[:50]:
        day_a, day_b = colombia_day_range(rec.date, rec.date)
        integ = power_sum(
            MeterMeasurement.objects.filter(device=rec.device, date__gte=day_a, date__lt=day_b),
            "totalActivePower",
        )
        if not integ:
            continue
        integrated_kwh = consumption_energy_kwh(integ)  # totalActivePower en kW (factor confirmado)
        counter_kwh = rec.total_imported_energy or rec.net_energy_consumption
        if not counter_kwh:
            continue
        ratio = counter_kwh / integrated_kwh if integrated_kwh else None
        if ratio:
            ratios.append(ratio)
            checked += 1
    if ratios:
        ratios.sort()
        med_ratio = ratios[len(ratios) // 2]
        print(f"  Comparadas {checked} filas medidor-día.")
        print(f"  ratio mediano (energía_contador / energía_integrada_kW) = {med_ratio:.4f}")
        if 0.5 <= med_ratio <= 2:
            print("  ✅ ratio ≈ 1  → el factor kW del consumo (sin /1000) es CORRECTO.")
        elif 500 <= med_ratio <= 2000:
            print("  ⚠️  ratio ≈ 1000  → totalActivePower estaría en W: usar POWER_UNIT_WATTS.")
        elif 0.0005 <= med_ratio <= 0.002:
            print("  ⚠️  ratio ≈ 1/1000  → factor invertido: revisar la conversión.")
        else:
            print("  ⚠️  ratio inesperado: totalActivePower puede no ser comparable con el "
                  "contador (neto vs bruto, exportación, etc.). Revisar manualmente.")
    else:
        print("  (no hay datos de ElectricMeterEnergyConsumption para comparar; "
              "usa la magnitud típica de la sección 2 como indicio)")

    # ---------- 4. KPI mensual: almacenado vs recalculado (canónico) ----------
    hr("4. KPI MENSUAL — almacenado vs recalculado con la fórmula canónica")
    kpi = MonthlyConsumptionKPI.objects.filter(pk=1).first()
    # Recalcular para la ventana --days como aproximación comparativa
    from indicators.tasks import get_colombia_date  # import tardío
    today = get_colombia_date()
    start = today - timedelta(days=args.days)
    win_a, win_b = colombia_day_range(start, today)
    cons = consumption_energy_kwh(
        power_sum(MeterMeasurement.objects.filter(device__in=meters, date__gte=win_a, date__lt=win_b),
                  "totalActivePower"))
    gen = generation_energy_kwh(
        power_sum(InverterMeasurement.objects.filter(device__in=inverters, date__gte=win_a, date__lt=win_b),
                  "acPower"))
    print(f"  Ventana recalculada: {start} → {today} ({args.days} días)")
    print(f"    Consumo (canónico)   = {cons:,.2f} kWh")
    print(f"    Generación (canónico)= {gen:,.2f} kWh")
    print(f"    Balance              = {gen - cons:,.2f} kWh")
    if kpi:
        print("\n  MonthlyConsumptionKPI almacenado (mes en curso):")
        print(f"    total_consumption_current_month = {kpi.total_consumption_current_month:,.2f} kWh")
        print(f"    total_generation_current_month  = {kpi.total_generation_current_month:,.2f} kWh")
        print("  (Nota: la ventana no coincide exactamente con el mes; sirve para ver el "
              "ORDEN DE MAGNITUD. Un desfase de ~30× o ~1000× indica el bug corregido.)")
    else:
        print("  (no hay MonthlyConsumptionKPI almacenado todavía)")

    hr("FIN DE LA AUDITORÍA")
    print("Unidades confirmadas: consumo en kW (factor 1), generación en W (÷1000).")
    print("Si el ratio de la sección 3 se aleja de 1, revisar POWER_UNIT_* en indicators/energy.py.")


if __name__ == "__main__":
    main()
