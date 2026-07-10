"""
Acceso a filas de mediciones v2 (`.values()`), compartido por los cálculos por categoría.
"""


def _row_get(row, key, default=0):
    """Equivalente v2 de `Measurement.data.get(key, default)` sobre filas dict de
    `.values()`: en las tablas tipadas una columna NULL ⇔ clave ausente en el antiguo
    jsonb, así que NULL debe producir el mismo valor por defecto."""
    value = row[key]
    return default if value is None else value
