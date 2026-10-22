"""
Los comandos de gestión toman «hoy» en la fecha de Colombia (timezone.localdate()), no en la UTC: desde las 19:00 de
Bogotá la fecha UTC ya es la del día siguiente.

Se ejecuta con: python manage.py test tests.test_comandos_fecha_local
"""

from datetime import datetime, timezone as dt_timezone
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from scada_proxy.models import Institution, DeviceCategory, Device

NOCHE_BOGOTA = datetime(2026, 10, 22, 3, 0, tzinfo=dt_timezone.utc)  # 21-oct, 22:00 en Bogotá


class ComandosFechaLocalTests(TestCase):

    def test_calculate_electric_indicators_termina_hoy_en_colombia(self):
        inst = Institution.objects.create(scada_id='I1', name='HUDN')
        cat = DeviceCategory.objects.create(scada_id='C1', name='electricMeter')
        Device.objects.create(name='M1', scada_id='M1', category=cat, institution=inst)
        with mock.patch('django.utils.timezone.now', return_value=NOCHE_BOGOTA), \
             mock.patch('indicators.management.commands.calculate_electric_indicators.'
                        'calculate_electric_meter_indicators') as tarea:
            call_command('calculate_electric_indicators', stdout=StringIO())
        fechas = [c.args[1] for c in tarea.delay.call_args_list]
        self.assertEqual(fechas[0], '2026-09-21')
        self.assertEqual(fechas[-1], '2026-10-21')
