"""
Acceso a filas de mediciones v2 (`.values()`), compartido por los cálculos por categoría.
"""


def _row_get(row, key, default=None):
    """Valor de la columna `key` de una fila dict de `.values()`.

    Una columna NULL es un dato que **no se midió** y se devuelve como None (C9, corrección de
    octubre de 2026). Antes se devolvía 0, que entraba a promedios y desbalances como si fuera una
    medición (p. ej. una fase en NULL daba un desbalance del 100 %). Los cálculos descartan los
    None: una muestra con alguna fase NULL no entra al desbalance, y un NULL no cuenta en una media.
    `default` solo existe para quien necesite explícitamente otro valor; nunca debe ser 0 para una
    magnitud medida."""
    value = row[key]
    return default if value is None else value
