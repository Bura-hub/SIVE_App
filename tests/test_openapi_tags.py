"""
Toda etiqueta que usan las vistas en el esquema OpenAPI está declarada en SPECTACULAR_SETTINGS['TAGS'], con su
descripción, para que Swagger y Redoc las agrupen y las expliquen.
"""
from django.conf import settings
from django.test import SimpleTestCase
from drf_spectacular.generators import SchemaGenerator


class EtiquetasOpenAPITests(SimpleTestCase):
    def test_todas_las_etiquetas_usadas_estan_declaradas(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        usadas = {
            tag
            for ruta in schema['paths'].values()
            for operacion in ruta.values()
            if isinstance(operacion, dict)
            for tag in operacion.get('tags', [])
        }
        declaradas = {t['name']: t.get('description') for t in settings.SPECTACULAR_SETTINGS['TAGS']}
        self.assertIn('Disponibilidad de datos', usadas)
        self.assertIn('Indicadores solares', usadas)
        self.assertEqual(usadas - set(declaradas), set())
        for nombre in usadas:
            self.assertTrue(declaradas[nombre], f'La etiqueta «{nombre}» no tiene descripción')
