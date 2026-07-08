"""
Tests de la sincronización de metadatos SCADA (app scada_proxy).

Cubren las correcciones:
- El sync mapea correctamente los dicts anidados 'category'/'institution'
  (['id']) a las claves foráneas locales (antes se leía 'category_id' /
  'institution_id', que la API NO devuelve, dejando dispositivos sin relaciones).
- La paginación del listado de dispositivos: si la API pagina, se recorren TODAS
  las páginas y NO se desactivan por error los dispositivos ausentes de la 1ª.
- No se desactivan dispositivos cuando la respuesta viene incompleta/vacía.
- Se omiten elementos incompletos (sin 'id'/'name') sin romper el sync.

Se usa unittest.mock para simular ScadaConnectorClient; no hay tráfico HTTP real.

Ejecutar en el contenedor:
  docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_scada_sync
"""
import os
from unittest.mock import MagicMock, patch

# Asegurar que el import a nivel de módulo de scada_proxy.tasks (que instancia
# ScadaConnectorClient) no falle si SCADA_BASE_URL no está en el entorno de test.
# Los tests inyectan un cliente simulado, así que este valor nunca se usa de verdad.
os.environ.setdefault("SCADA_BASE_URL", "http://scada.test")

from django.test import TestCase

from scada_proxy import tasks
from scada_proxy.models import Device, DeviceCategory, Institution


def _make_client(categories, institutions, device_pages):
    """
    Construye un mock de ScadaConnectorClient.

    - categories / institutions: listas de dicts que se devolverán como 'data'.
    - device_pages: lista de respuestas (dicts con 'data' y opcional 'total') que
      get_devices devolverá en orden en cada llamada, para simular paginación.
    """
    client = MagicMock()
    client.get_token.return_value = "fake-token"
    client.get_device_categories.return_value = {
        "data": categories, "total": len(categories),
    }
    client.get_institutions.return_value = {
        "data": institutions, "total": len(institutions),
    }
    client.get_devices.side_effect = list(device_pages)
    return client


class SyncScadaMetadataMappingTests(TestCase):
    """Verifica el mapeo correcto de las relaciones anidadas category/institution."""

    def test_maps_nested_category_and_institution_to_fks(self):
        categories = [{"id": "cat-1", "name": "inverter", "description": "Inversores"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}]
        devices = [{
            "id": "dev-1",
            "name": "Inversor SFV",
            "status": "online",
            # La API SCADA anida category/institution como dicts con ['id'].
            "category": {"id": "cat-1", "name": "inverter"},
            "institution": {"id": "inst-1", "name": "Udenar"},
        }]
        client = _make_client(categories, institutions, [{"data": devices, "total": 1}])

        summary = tasks.sync_scada_metadata_core(client=client)

        self.assertEqual(DeviceCategory.objects.count(), 1)
        self.assertEqual(Institution.objects.count(), 1)

        device = Device.objects.get(scada_id="dev-1")
        self.assertIsNotNone(device.category, "La categoría debe quedar mapeada")
        self.assertEqual(device.category.scada_id, "cat-1")
        self.assertIsNotNone(device.institution, "La institución debe quedar mapeada")
        self.assertEqual(device.institution.scada_id, "inst-1")
        self.assertTrue(device.is_active)

        self.assertEqual(summary["devices_created"], 1)
        self.assertEqual(summary["devices_with_issues"], 0)

    def test_device_without_category_is_counted_as_issue_but_synced(self):
        categories = [{"id": "cat-1", "name": "inverter"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}]
        devices = [{
            "id": "dev-2",
            "name": "Dispositivo sin categoría",
            # Sin 'category'; con institución válida.
            "institution": {"id": "inst-1", "name": "Udenar"},
        }]
        client = _make_client(categories, institutions, [{"data": devices, "total": 1}])

        summary = tasks.sync_scada_metadata_core(client=client)

        device = Device.objects.get(scada_id="dev-2")
        self.assertIsNone(device.category)
        self.assertIsNotNone(device.institution)
        self.assertEqual(summary["devices_with_issues"], 1)

    def test_incomplete_elements_are_skipped(self):
        # Categoría sin 'name', institución sin 'id' y dispositivo sin 'id':
        # deben omitirse sin lanzar excepción.
        categories = [{"id": "cat-1", "name": "inverter"}, {"id": "cat-x"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}, {"name": "SinId"}]
        devices = [
            {"id": "dev-1", "name": "OK", "category": {"id": "cat-1"},
             "institution": {"id": "inst-1"}},
            {"name": "Sin id, se omite"},
        ]
        client = _make_client(categories, institutions, [{"data": devices, "total": 2}])

        summary = tasks.sync_scada_metadata_core(client=client)

        self.assertEqual(DeviceCategory.objects.count(), 1)
        self.assertEqual(Institution.objects.count(), 1)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(summary["categories"], 1)
        self.assertEqual(summary["institutions"], 1)


class SyncScadaMetadataPaginationTests(TestCase):
    """Verifica que la paginación no desactive dispositivos por error."""

    def setUp(self):
        # Estado previo: 3 dispositivos activos ya sincronizados.
        self.category = DeviceCategory.objects.create(scada_id="cat-1", name="inverter")
        self.institution = Institution.objects.create(scada_id="inst-1", name="Udenar")
        for scada_id in ("dev-1", "dev-2", "dev-3"):
            Device.objects.create(
                scada_id=scada_id, name=f"Disp {scada_id}",
                category=self.category, institution=self.institution, is_active=True,
            )

    @patch.object(tasks, "DEVICES_PAGE_SIZE", 2)
    def test_paginated_list_does_not_deactivate_devices(self):
        categories = [{"id": "cat-1", "name": "inverter"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}]

        def dev(scada_id):
            return {
                "id": scada_id, "name": f"Disp {scada_id}",
                "category": {"id": "cat-1"}, "institution": {"id": "inst-1"},
            }

        # La API devuelve los 3 dispositivos en 2 páginas (tamaño de página = 2).
        # Con el tamaño de página parcheado a 2, la 1ª página llena obliga a pedir
        # la 2ª. Si NO se paginara, dev-3 quedaría fuera y se desactivaría.
        page1 = {"data": [dev("dev-1"), dev("dev-2")], "total": 3}
        page2 = {"data": [dev("dev-3")], "total": 3}
        client = _make_client(categories, institutions, [page1, page2])

        summary = tasks.sync_scada_metadata_core(client=client)

        # get_devices se llamó dos veces (una por página).
        self.assertEqual(client.get_devices.call_count, 2)
        # Ningún dispositivo se desactivó.
        self.assertEqual(Device.objects.filter(is_active=False).count(), 0)
        self.assertEqual(summary["devices_deactivated"], 0)
        self.assertTrue(summary["complete"])

    def test_empty_response_does_not_deactivate_devices(self):
        # Respuesta vacía (posible fallo transitorio): no debe desactivar nada.
        categories = [{"id": "cat-1", "name": "inverter"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}]
        client = _make_client(categories, institutions, [{"data": [], "total": 0}])

        summary = tasks.sync_scada_metadata_core(client=client)

        self.assertEqual(Device.objects.filter(is_active=False).count(), 0)
        self.assertEqual(summary["devices_deactivated"], 0)
        self.assertFalse(summary["complete"])

    def test_missing_device_is_deactivated_when_list_complete(self):
        # Si la lista viene completa y falta un dispositivo, sí se desactiva.
        categories = [{"id": "cat-1", "name": "inverter"}]
        institutions = [{"id": "inst-1", "name": "Udenar"}]
        remaining = [
            {"id": "dev-1", "name": "Disp dev-1", "category": {"id": "cat-1"},
             "institution": {"id": "inst-1"}},
            {"id": "dev-2", "name": "Disp dev-2", "category": {"id": "cat-1"},
             "institution": {"id": "inst-1"}},
        ]
        client = _make_client(categories, institutions, [{"data": remaining, "total": 2}])

        summary = tasks.sync_scada_metadata_core(client=client)

        # dev-3 ya no está en SCADA y la lista vino completa -> se desactiva.
        self.assertFalse(Device.objects.get(scada_id="dev-3").is_active)
        self.assertTrue(Device.objects.get(scada_id="dev-1").is_active)
        self.assertEqual(summary["devices_deactivated"], 1)
        self.assertTrue(summary["complete"])
