"""Marca institucional y presentación de los informes SIVE.

Reúne la identidad visual (paleta, logos MTE + SIVE), el encabezado/pie con paginación para
reportlab, el cálculo del resumen ejecutivo y builders de tablas reutilizables por los
generadores PDF de `indicators/tasks.py`. Los logos y el cálculo del resumen NO dependen de
reportlab (para no acoplar el camino de Excel/CSV); las funciones de flowables/canvas importan
reportlab de forma perezosa.
"""

import os
import logging

from django.conf import settings

from indicators.services.date_ranges import get_colombia_now

logger = logging.getLogger(__name__)

# --- Paleta institucional (hex sin '#') ---
PRIMARY = "1E40AF"   # azul institucional (cabeceras destacadas, líneas)
DARK = "1F2937"      # gris oscuro (cabecera de tablas de datos)
ACCENT = "059669"    # verde MTE (títulos de banda)
ZEBRA = "F9FAFB"     # gris muy claro (filas alternas)
GRID = "CBD5E1"      # gris borde
LIGHT = "F1F5F9"     # gris claro (columna etiqueta de fichas)
TOTALS = "E2E8F0"    # gris fila de totales

# --- Logos (PNG raster; reportlab/openpyxl NO renderizan SVG) ---
REPORT_ASSETS_DIR = os.path.join(settings.BASE_DIR, "indicators", "report_assets")
LOGO_MTE = os.path.join(REPORT_ASSETS_DIR, "mte-logo.png")
LOGO_SIVE = os.path.join(REPORT_ASSETS_DIR, "sive-logo.png")


def resolve_logo(path):
    """Devuelve la ruta del logo si existe en disco, o None (para degradar con gracia)."""
    try:
        return path if path and os.path.exists(path) else None
    except OSError:
        return None


# --- Semántica de columnas: etiqueta legible, unidad y agregación para el resumen ---
# agg: 'sum' | 'mean' | 'max' | 'min'
COLUMN_META = {
    # Medidores eléctricos
    "imported_energy_kwh": ("Energía importada", "kWh", "sum"),
    "exported_energy_kwh": ("Energía exportada", "kWh", "sum"),
    "net_energy_consumption_kwh": ("Consumo neto", "kWh", "sum"),
    "peak_demand_kw": ("Demanda pico", "kW", "max"),
    "avg_demand_kw": ("Demanda promedio", "kW", "mean"),
    "load_factor_pct": ("Factor de carga", "%", "mean"),
    "avg_power_factor": ("Factor de potencia", "", "mean"),
    "max_voltage_thd_pct": ("THD tensión (máx)", "%", "max"),
    "max_current_thd_pct": ("THD corriente (máx)", "%", "max"),
    # Inversores
    "total_generated_energy_kwh": ("Energía generada", "kWh", "sum"),
    "energy_ac_daily_kwh": ("Energía AC", "kWh", "sum"),
    "dc_ac_efficiency_pct": ("Eficiencia DC/AC", "%", "mean"),
    "performance_ratio_pct": ("Performance ratio", "%", "mean"),
    "avg_irradiance_wm2": ("Irradiancia promedio", "W/m²", "mean"),
    "avg_temperature_c": ("Temperatura promedio", "°C", "mean"),
    "avg_power_factor_pct": ("Factor de potencia", "%", "mean"),
    "avg_frequency_hz": ("Frecuencia promedio", "Hz", "mean"),
    "frequency_stability_pct": ("Estabilidad de frecuencia", "%", "mean"),
    "anomaly_score": ("Score de anomalía", "", "mean"),
    "max_power_w": ("Potencia máxima", "W", "max"),
    "min_power_w": ("Potencia mínima", "W", "min"),
    # Estaciones meteorológicas
    "daily_irradiance_kwh_m2": ("Irradiancia acumulada", "kWh/m²", "sum"),
    "daily_hsp_hours": ("Horas solares pico", "HSP", "mean"),
    "avg_wind_speed_kmh": ("Velocidad del viento", "km/h", "mean"),
    "daily_precipitation_cm": ("Precipitación", "cm", "sum"),
    "theoretical_pv_power_w": ("Potencia FV teórica", "W", "mean"),
    "avg_humidity_pct": ("Humedad relativa", "%", "mean"),
}

# Columnas no numéricas / de eje que nunca entran al resumen.
_NON_NUMERIC = {"name", "device__name", "date", "wind_direction_distribution",
                "wind_speed_distribution", "predominant_wind_direction"}


def _to_float(value):
    """Parsea un valor de celda (posiblemente ya formateado como '98.20%' o '1,234.5') a
    float; devuelve None si no es numérico."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace("%", "").replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _column_meta(col):
    """(etiqueta, unidad, agg) para una columna: del mapa conocido o por heurística de nombre."""
    if col in COLUMN_META:
        return COLUMN_META[col]
    low = col.lower()
    unit = ("%" if "pct" in low or "factor" in low or "ratio" in low or "efficiency" in low
            else "kWh" if "kwh" in low
            else "kW" if low.endswith("_kw") or "_kw_" in low
            else "W/m²" if "wm2" in low
            else "Hz" if "hz" in low
            else "°C" if low.endswith("_c") or "temperature" in low
            else "km/h" if "kmh" in low
            else "W" if low.endswith("_w")
            else "")
    agg = ("sum" if "energy" in low or "kwh" in low
           else "max" if low.startswith("max") or "peak" in low
           else "min" if low.startswith("min")
           else "mean")
    label = col.replace("_", " ").replace(" pct", "").replace(" kwh", "").strip().capitalize()
    return (label, unit, agg)


def pretty_header(col):
    """Cabecera legible para una columna: 'Etiqueta (unidad)' (o la etiqueta sola)."""
    label, unit, _ = _column_meta(col)
    return f"{label} ({unit})" if unit else label


def to_number(value):
    """Parsea una celda a float (quitando '%'/comas) o None si no es numérica. Público
    para que el Excel escriba números sumables en vez de texto."""
    return _to_float(value)


def compute_summary(report_data):
    """Resumen ejecutivo a partir de report_data (lista de dicts con celdas ya formateadas).

    Recupera el float crudo por celda (parseando '%'/comas) y agrega cada columna numérica
    según su semántica (suma de energía, promedio de %, máx/mín de picos). Devuelve una lista
    ORDENADA de dicts {label, unit, value, agg} lista para pintar, más 'record_count'.
    """
    if not report_data:
        return {"record_count": 0, "metrics": []}

    columns = [c for c in report_data[0].keys() if c not in _NON_NUMERIC]
    acc = {c: [] for c in columns}
    for row in report_data:
        for c in columns:
            v = _to_float(row.get(c))
            if v is not None:
                acc[c].append(v)

    metrics = []
    for c in columns:
        vals = acc[c]
        if not vals:
            continue
        label, unit, agg = _column_meta(c)
        if agg == "sum":
            value = sum(vals)
        elif agg == "max":
            value = max(vals)
        elif agg == "min":
            value = min(vals)
        else:
            value = sum(vals) / len(vals)
        metrics.append({"label": label, "unit": unit, "value": value, "agg": agg})

    return {"record_count": len(report_data), "metrics": metrics}


def fmt_value(value, unit=""):
    """Formatea un número con separador de miles y 2 decimales, más la unidad."""
    try:
        s = f"{value:,.2f}"
    except (TypeError, ValueError):
        s = str(value)
    return f"{s} {unit}".strip()


def period_label(context):
    """Texto de rango del reporte para el pie de página."""
    if not context:
        return ""
    start = context.get("start_date", "")
    end = context.get("end_date", "")
    tr = context.get("time_range", "")
    base = f"{start} a {end}".strip(" a ")
    return f"{base} ({tr})" if tr else base


def make_header_footer(context):
    """Devuelve (on_first_page, on_later_pages) para SimpleDocTemplate.build.

    Primera página: banda con logos MTE (izq.) y SIVE (der.). Todas las páginas: pie con
    'SIVE — Universidad de Nariño', rango del reporte (centro) y 'Página N' (der.), sobre una
    línea. Todo protegido con try/except: si falta un logo o algo falla, el PDF se genera igual.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    page_w, page_h = A4
    rango = period_label(context)
    mte = resolve_logo(LOGO_MTE)
    sive = resolve_logo(LOGO_SIVE)

    def _band(canvas):
        # Banda de logos en la parte superior (solo 1ª página).
        try:
            if mte:
                canvas.drawImage(mte, 2 * cm, page_h - 2.4 * cm, width=4.4 * cm, height=2.0 * cm,
                                 preserveAspectRatio=True, mask="auto", anchor="sw")
            if sive:
                canvas.drawImage(sive, page_w - 6.4 * cm, page_h - 2.4 * cm, width=4.4 * cm, height=2.0 * cm,
                                 preserveAspectRatio=True, mask="auto", anchor="se")
            canvas.setStrokeColor(colors.HexColor("#" + PRIMARY))
            canvas.setLineWidth(1.2)
            canvas.line(2 * cm, page_h - 2.7 * cm, page_w - 2 * cm, page_h - 2.7 * cm)
        except Exception as exc:  # noqa: BLE001 - degradar sin romper el PDF
            logger.warning(f"No se pudo dibujar la banda de logos: {exc}")

    def _footer(canvas, doc):
        try:
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#" + GRID))
            canvas.setLineWidth(0.5)
            canvas.line(2 * cm, 1.3 * cm, page_w - 2 * cm, 1.3 * cm)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#" + PRIMARY))
            canvas.drawString(2 * cm, 1 * cm, "SIVE — Universidad de Nariño")
            if rango:
                canvas.setFillColor(colors.HexColor("#" + DARK))
                canvas.drawCentredString(page_w / 2, 1 * cm, rango)
            canvas.setFillColor(colors.HexColor("#" + DARK))
            canvas.drawRightString(page_w - 2 * cm, 1 * cm, f"Página {doc.page}")
            canvas.restoreState()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"No se pudo dibujar el pie de página: {exc}")

    def on_first_page(canvas, doc):
        _band(canvas)
        _footer(canvas, doc)

    def on_later_pages(canvas, doc):
        _footer(canvas, doc)

    return on_first_page, on_later_pages


def build_param_table(context):
    """Ficha de parámetros (tabla 2 columnas) como flowable de reportlab."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    ctx = context or {}
    devices = ctx.get("devices") or []
    devices_txt = ", ".join(str(d) for d in devices) if devices else "Todos"
    rows = [
        ["Institución", str(ctx.get("institution_name", "—"))],
        ["Categoría", str(ctx.get("category", "—"))],
        ["Dispositivos", devices_txt],
        ["Rango", f"{ctx.get('start_date', '')} — {ctx.get('end_date', '')}".strip(" —")],
        ["Agregación", str(ctx.get("time_range", "—"))],
        ["Generado", get_colombia_now().strftime("%d/%m/%Y %H:%M") + " (hora Colombia)"],
    ]
    table = Table(rows, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#" + LIGHT)),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#" + DARK)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#" + GRID)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_summary_table(summary):
    """Tabla de KPIs del resumen ejecutivo como flowable de reportlab (o None si no hay)."""
    if not summary or not summary.get("metrics"):
        return None
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    agg_es = {"sum": "Total", "mean": "Promedio", "max": "Máximo", "min": "Mínimo"}
    header = ["Indicador", "Valor", "Agregado"]
    rows = [header]
    for m in summary["metrics"]:
        rows.append([m["label"], fmt_value(m["value"], m["unit"]), agg_es.get(m["agg"], m["agg"])])

    table = Table(rows, colWidths=[8 * cm, 5 * cm, 3 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#" + GRID)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#" + ZEBRA)]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    table.setStyle(TableStyle(style))
    return table
