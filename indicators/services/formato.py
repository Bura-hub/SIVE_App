"""Cifras en los textos que se muestran al usuario: coma decimal (es-CO), como el resto de la interfaz."""


def coma(valor, decimales=None):
    """«17,55»; con decimales fijos, «-3,91». Solo para textos: los valores numéricos de la API siguen con punto."""
    texto = f'{valor:.{decimales}f}' if decimales is not None else f'{valor}'
    return texto.replace('.', ',')
