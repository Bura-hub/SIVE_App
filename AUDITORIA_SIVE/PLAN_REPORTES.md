# Plan: reportes más profesionales (backlog, tras el refactor)

> Solicitado por el usuario. Ejecutar DESPUÉS del refactor de vistas finas pendiente.
> Objetivo: que los PDF/Excel exportados se vean adecuados y profesionales, con identidad
> institucional. Sin cambiar el pipeline de generación (Celery) ni los datos.

## Estado actual (medido, `indicators/tasks.py`)
- **PDF** (reportlab, `generate_pdf_file` ~1615+): A4, márgenes 2cm, estilos propios
  (título 20pt, subtítulos, highlight), título "REPORTE DETALLADO: {tipo}", fecha de
  generación, total de registros y **tablas** por dispositivo/indicador.
- **Excel** (openpyxl): con `Font/Alignment/PatternFill`.
- **CSV**: plano.
- **Carencias para "profesional":** sin **logo/marca** (Universidad de Nariño / SIVE), sin
  **encabezado/pie con paginación**, sin **resumen ejecutivo** (totales/KPIs arriba), la
  fecha usa `datetime.now()` del servidor (no hora Colombia), sin portada, tablas mejorables.

## Mejoras propuestas (incremental, verificable regenerando un reporte)
1. **Marca institucional**: logo (SIVE / Universidad de Nariño) + banda de encabezado en la
   1ª página; usar `frontend/src/sive-logo.svg` convertido a PNG o un asset en el backend.
2. **Header/footer con paginación** en todas las páginas: `SimpleDocTemplate.build(
   onFirstPage=, onLaterPages=)` dibujando "SIVE — Universidad de Nariño", nº de página,
   y fecha/rango del reporte en el pie.
3. **Resumen ejecutivo**: primera sección con los totales/promedios clave del período
   (consumo/generación/balance o los indicadores meteo), antes del detalle tabular.
4. **Encabezado de datos claro**: institución, categoría, dispositivos, rango de fechas y
   `time_range`, en un bloque tipo "ficha" (tabla de 2 columnas), no texto suelto.
5. **TZ correcta**: fecha de generación en hora de Colombia (`get_colombia_now()`), no
   `datetime.now()` del servidor.
6. **Tablas**: cabecera con color institucional, filas zebra, alineación numérica a la
   derecha, unidades en la cabecera, totales al pie cuando aplique.
7. **Excel a la par**: hoja con título/logo, cabecera congelada (`freeze_panes`), formato de
   número por columna, ancho automático; CSV se queda simple (es intercambio de datos).
8. **(Opcional) gráficos embebidos** en el PDF (matplotlib ya está en el fallback): una
   mini-gráfica de tendencia por indicador principal.

## Secuencia
1. Refactorizar la generación PDF a un helper con header/footer reutilizable (base).
2. Añadir marca + resumen ejecutivo + ficha de parámetros.
3. Pulir tablas y Excel.
4. (Opcional) gráficos.
Cada paso: regenerar un reporte real y revisar el PDF/Excel resultante.

## Notas
- Requiere el fix de persistencia de media ya hecho (volumen con nombre) para descargar.
- No tocar el contrato del endpoint de descarga ni el modelo GeneratedReport.
