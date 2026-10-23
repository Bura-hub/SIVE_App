"""
Tests de la reconciliación de mediciones con el connector.

Las RPi envían colas atrasadas días después y la ingesta horaria (últimas 3 h)
no las recogía. reconcile_measurements compara por dispositivo y día de Bogotá
el conteo local con meta.total del connector y re-descarga solo lo distinto;
enqueue_recalc_for_reconciled recalcula solo lo tocado.

Se simula ScadaConnectorClient con un connector en memoria; no hay HTTP real.

Ejecutar en el contenedor:
  docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_reconcile_measurements
"""
import os
from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

os.environ.setdefault("SCADA_BASE_URL", "http://scada.test")

from django.core.management import call_command
from django.test import TestCase

from scada_proxy import tasks
from scada_proxy.models import (
    Device, DeviceCategory, Institution, InverterMeasurement, MeterMeasurement,
)

TZ = tasks.COLOMBIA_TZ


def _at(day, hour, minute=0):
    return TZ.localize(datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute))


class FakeConnector:
    """Connector en memoria. `store[scada_id]` = lista de (datetime, data).

    `phantom[(scada_id, day)]` suma filas a meta.total que nunca se entregan,
    para simular una diferencia persistente. `fail_days` hace fallar la
    llamada de ese (scada_id, day)."""

    def __init__(self):
        self.store = {}
        self.phantom = {}
        self.fail_days = set()
        self.calls = []

    def get_token(self):
        return "fake-token"

    def get_measurements(self, token, device_id, from_date=None, to_date=None,
                         order_by="date desc", limit=None, offset=None):
        self.calls.append({"device": device_id, "from": from_date, "to": to_date,
                           "limit": limit, "offset": offset})
        f = datetime.fromisoformat(from_date)
        t = datetime.fromisoformat(to_date)
        day = f.astimezone(TZ).date()
        if (device_id, day) in self.fail_days:
            raise RuntimeError("connector caído")
        rows = sorted((r for r in self.store.get(device_id, []) if f <= r[0] <= t),
                      key=lambda r: r[0])
        total = len(rows) + self.phantom.get((device_id, day), 0)
        start = offset or 0
        page = rows[start:start + (limit or len(rows))]
        return {
            "data": [{"date": dt.isoformat(), "data": data} for dt, data in page],
            "meta": {"total": total},
        }

    def downloads(self):
        """Llamadas de descarga (no las de conteo con limit=1)."""
        return [c for c in self.calls if c["limit"] != 1]


class ReconcileBase(TestCase):
    def setUp(self):
        inst = Institution.objects.create(scada_id="inst-1", name="UCC")
        self.cat_inv = DeviceCategory.objects.create(scada_id="cat-inv", name="inverter")
        self.cat_meter = DeviceCategory.objects.create(scada_id="cat-m", name="electricMeter")
        self.inverter = Device.objects.create(
            scada_id="inv-1", name="Inversor UCC", category=self.cat_inv,
            institution=inst, is_active=True)
        self.meter = Device.objects.create(
            scada_id="m-1", name="Medidor UCC", category=self.cat_meter,
            institution=inst, is_active=True)
        self.connector = FakeConnector()
        self.day = date(2026, 9, 30)

    def _remote(self, device, day, hours):
        self.connector.store.setdefault(device.scada_id, []).extend(
            (_at(day, h), {"acPower": float(h)}) for h in hours)

    def _local(self, device, day, hours, model):
        for h in hours:
            model.objects.create(device=device, date=_at(day, h))


class ReconcileMeasurementsTests(ReconcileBase):

    def test_equal_counts_do_not_refetch(self):
        self._remote(self.inverter, self.day, range(5))
        self._local(self.inverter, self.day, range(5), InverterMeasurement)

        with patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            results = tasks.reconcile_measurements(
                self.day, self.day, devices=[self.inverter.id], client=self.connector)

        self.assertEqual(results, [(self.inverter, self.day, 5, 5, 5)])
        self.assertEqual(self.connector.downloads(), [])
        self.assertFalse(results[0].refetched)
        self.assertFalse(results[0].mismatch)
        enqueue.assert_not_called()

    def test_different_count_refetches_and_matches(self):
        # SIVE tiene 2 de las 6 lecturas: las otras 4 llegaron tarde al connector.
        self._remote(self.inverter, self.day, range(6))
        self._local(self.inverter, self.day, range(2), InverterMeasurement)
        # Lectura de las 00:00 del día siguiente: no debe contar para este día.
        self._remote(self.inverter, self.day + timedelta(days=1), [0])

        with patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            results = tasks.reconcile_measurements(
                self.day, self.day, devices=[self.inverter.id], client=self.connector)

        self.assertEqual(results, [(self.inverter, self.day, 2, 6, 6)])
        self.assertTrue(results[0].refetched)
        self.assertTrue(results[0].changed)
        self.assertFalse(results[0].mismatch)
        self.assertEqual(InverterMeasurement.objects.filter(device=self.inverter).count(), 6)
        self.assertTrue(self.connector.downloads())
        # El 'to' enviado al connector es el fin del día menos 1 s.
        self.assertTrue(all(c["to"].startswith("2026-09-30T23:59:59") for c in self.connector.calls))
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.args[0], results)

    def test_persistent_difference_is_logged_and_continues(self):
        # Inversor: el connector anuncia 2 filas más de las que entrega.
        self._remote(self.inverter, self.day, range(3))
        self.connector.phantom[(self.inverter.scada_id, self.day)] = 2
        # Inversor, día siguiente: el connector falla.
        next_day = self.day + timedelta(days=1)
        self.connector.fail_days.add((self.inverter.scada_id, next_day))
        # Medidor: diferencia normal, se debe reconciliar igual.
        self._remote(self.meter, self.day, range(4))

        with patch.object(tasks, "_notify") as notify, \
                patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue, \
                self.assertLogs("scada_proxy.tasks", level="ERROR") as logs:
            results = tasks.reconcile_measurements(
                self.day, next_day, client=self.connector)

        by_key = {(r.device.scada_id, r.day): r for r in results}
        self.assertEqual(len(results), 4)
        persistent = by_key[("inv-1", self.day)]
        self.assertEqual(tuple(persistent)[2:], (0, 5, 3))
        self.assertTrue(persistent.mismatch)
        failed = by_key[("inv-1", next_day)]
        self.assertIsNone(failed.remote)
        self.assertTrue(failed.mismatch)
        meter = by_key[("m-1", self.day)]
        self.assertEqual(tuple(meter)[2:], (0, 4, 4))
        self.assertFalse(meter.mismatch)
        self.assertEqual(MeterMeasurement.objects.filter(device=self.meter).count(), 4)

        joined = "\n".join(logs.output)
        self.assertIn("diferencia persistente en 'Inversor UCC'", joined)
        self.assertIn("no se pudo reconciliar 'Inversor UCC'", joined)
        self.assertEqual(notify.call_count, 2)  # diferencias persistentes + errores
        # Se recalcula lo que ganó filas (inversor 30-sep y medidor 30-sep).
        changed = enqueue.call_args.args[0]
        self.assertEqual({(r.device.scada_id, r.day) for r in changed},
                         {("inv-1", self.day), ("m-1", self.day)})

    def test_forced_day_recalculates_even_with_equal_counts(self):
        # Ayer ya está completo en SIVE (la ingesta horaria trajo lo último),
        # pero su diario se calculó a las 23:10: hay que recalcularlo igual.
        yesterday, today = self.day, self.day + timedelta(days=1)
        self._remote(self.inverter, yesterday, range(4))
        self._local(self.inverter, yesterday, range(4), InverterMeasurement)

        with patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            results = tasks.reconcile_measurements(
                yesterday, today, devices=[self.inverter.id, self.meter.id],
                client=self.connector, force_recalc_days=[yesterday])

        self.assertEqual(self.connector.downloads(), [])
        self.assertFalse(any(r.changed for r in results))
        recalc = enqueue.call_args.args[0]
        # Todos los dispositivos revisados en ayer; hoy (sin cambios) no.
        self.assertEqual({(r.device.scada_id, r.day) for r in recalc},
                         {("inv-1", yesterday), ("m-1", yesterday)})

    def test_without_force_equal_counts_enqueue_nothing(self):
        self._remote(self.inverter, self.day, range(2))
        self._local(self.inverter, self.day, range(2), InverterMeasurement)
        with patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            tasks.reconcile_measurements(self.day, self.day, devices=[self.inverter.id],
                                         client=self.connector)
        enqueue.assert_not_called()

    def test_no_recalc_flag(self):
        self._remote(self.inverter, self.day, range(3))
        with patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            tasks.reconcile_measurements(self.day, self.day, recalc=False, client=self.connector)
        enqueue.assert_not_called()

    def test_deadline_stops_and_reports(self):
        self._remote(self.inverter, self.day, range(3))
        with patch.object(tasks, "_notify") as notify, \
                self.assertLogs("scada_proxy.tasks", level="ERROR") as logs:
            results = tasks.reconcile_measurements(
                self.day, self.day, recalc=False, client=self.connector, deadline=0)
        self.assertEqual(results, [])
        self.assertIn("INCOMPLETA", "\n".join(logs.output))
        notify.assert_called_once()


class EnqueueRecalcTests(ReconcileBase):

    def _result(self, device, day, before=0, after=10):
        return tasks.ReconcileResult(device, day, before, after, after)

    def test_recalc_only_touched_days_and_months(self):
        changed = [
            self._result(self.inverter, date(2026, 9, 29)),
            self._result(self.inverter, date(2026, 9, 30)),
            self._result(self.inverter, date(2026, 10, 2)),
            self._result(self.meter, date(2026, 9, 30)),
        ]
        fake_chain = MagicMock()
        with patch.object(tasks, "get_colombia_now", return_value=_at(date(2026, 10, 10), 12, 30)), \
                patch("celery.chain", fake_chain):
            sigs = tasks.enqueue_recalc_for_reconciled(changed)

        fake_chain.assert_called_once()
        fake_chain.return_value.apply_async.assert_called_once()
        self.assertIn("link_error", fake_chain.return_value.apply_async.call_args.kwargs)

        def short(sig):
            return sig.task.rsplit(".", 1)[-1]

        daily = [(short(s), s.kwargs["start_date_str"], s.kwargs["end_date_str"], s.kwargs["device_id"])
                 for s in sigs if s.kwargs.get("time_range") == "daily"]
        self.assertEqual(sorted(daily), sorted([
            ("calculate_inverter_data", "2026-09-29", "2026-09-30", "inv-1"),
            ("calculate_inverter_data", "2026-10-02", "2026-10-02", "inv-1"),
            ("calculate_electrical_data", "2026-09-30", "2026-09-30", "m-1"),
        ]))
        monthly = [(short(s), s.kwargs["start_date_str"], s.kwargs["end_date_str"], s.kwargs["device_id"])
                   for s in sigs if s.kwargs.get("time_range") == "monthly"]
        self.assertEqual(sorted(monthly), sorted([
            ("calculate_inverter_data", "2026-09-01", "2026-09-30", "inv-1"),
            ("calculate_inverter_data", "2026-10-01", "2026-10-10", "inv-1"),
            ("calculate_electrical_data", "2026-09-01", "2026-09-30", "m-1"),
        ]))
        charts = [s.args for s in sigs if short(s) == "calculate_and_save_daily_data"]
        self.assertEqual(sorted(charts), [("2026-09-29", "2026-09-30"), ("2026-10-02", "2026-10-02")])
        rollups = [(s.kwargs["start_hour_str"][:16], s.kwargs["end_hour_str"][:16], s.kwargs["device_id"])
                   for s in sigs if short(s) == "calculate_hourly_rollup"]
        self.assertEqual(sorted(rollups), sorted([
            ("2026-09-29T00:00", "2026-09-30T23:00", "inv-1"),
            ("2026-10-02T00:00", "2026-10-02T23:00", "inv-1"),
            ("2026-09-30T00:00", "2026-09-30T23:00", "m-1"),
        ]))
        kpi = [s for s in sigs if short(s) == "calculate_monthly_consumption_kpi"]
        self.assertEqual(len(kpi), 1)
        self.assertIs(sigs[-1], kpi[0])

    def test_today_rollup_stops_at_last_closed_hour(self):
        today = date(2026, 10, 10)
        fake_chain = MagicMock()
        with patch.object(tasks, "get_colombia_now", return_value=_at(today, 9, 40)), \
                patch("celery.chain", fake_chain):
            sigs = tasks.enqueue_recalc_for_reconciled([self._result(self.inverter, today)])
        rollup = [s for s in sigs if s.task.endswith("calculate_hourly_rollup")][0]
        self.assertTrue(rollup.kwargs["end_hour_str"].startswith("2026-10-10T08:00"))

    def test_nothing_changed_enqueues_nothing(self):
        fake_chain = MagicMock()
        with patch("celery.chain", fake_chain):
            self.assertEqual(tasks.enqueue_recalc_for_reconciled([]), [])
        fake_chain.assert_not_called()


class ReconcileTaskAndScheduleTests(ReconcileBase):

    def test_task_window_and_alias(self):
        now = _at(date(2026, 10, 10), 1, 30)
        with patch.object(tasks, "get_colombia_now", return_value=now), \
                patch.object(tasks, "reconcile_measurements", return_value=[]) as rec:
            tasks.reconcile_recent_measurements.run(days=35)
            self.assertEqual(rec.call_args.args[:2], (date(2026, 9, 5), date(2026, 10, 10)))
            self.assertEqual(list(rec.call_args.kwargs["force_recalc_days"]), [])
            tasks.reconcile_recent_measurements.run(days=2, force_recalc_days=1)
            self.assertEqual(rec.call_args.args[:2], (date(2026, 10, 8), date(2026, 10, 10)))
            self.assertEqual(list(rec.call_args.kwargs["force_recalc_days"]), [date(2026, 10, 9)])
            tasks.refetch_and_verify_yesterday.run()
            self.assertEqual(rec.call_args.args[:2], (date(2026, 10, 9), date(2026, 10, 10)))

    def test_beat_schedule_disables_old_entry_in_db(self):
        """El DatabaseScheduler sincroniza settings → BD por nombre: la entrada
        vieja existente en producción queda desactivada sola."""
        from django.conf import settings
        from django_celery_beat.models import CrontabSchedule, PeriodicTask
        from django_celery_beat.schedulers import ModelEntry
        from core.celery import app

        cron = CrontabSchedule.objects.create(minute="30", hour="1")
        PeriodicTask.objects.create(
            name="refetch-verify-yesterday-daily", crontab=cron, enabled=True,
            task="scada_proxy.tasks.refetch_and_verify_yesterday")

        schedule = settings.CELERY_BEAT_SCHEDULE
        for name in ("refetch-verify-yesterday-daily", "reconcile-measurements-daily",
                     "reconcile-measurements-6h", "reconcile-measurements-midnight"):
            ModelEntry.from_entry(name, app=app, **schedule[name])

        self.assertFalse(PeriodicTask.objects.get(name="refetch-verify-yesterday-daily").enabled)
        daily = PeriodicTask.objects.get(name="reconcile-measurements-daily")
        self.assertTrue(daily.enabled)
        self.assertEqual(daily.task, "scada_proxy.tasks.reconcile_recent_measurements")
        self.assertEqual(daily.kwargs, '{"days": 35}')
        six = PeriodicTask.objects.get(name="reconcile-measurements-6h")
        self.assertEqual(six.kwargs, '{"days": 2}')
        self.assertEqual((six.crontab.hour, six.crontab.minute), ("6,12,18", "40"))
        midnight = PeriodicTask.objects.get(name="reconcile-measurements-midnight")
        self.assertEqual(midnight.kwargs, '{"days": 2, "force_recalc_days": 1}')
        self.assertEqual((midnight.crontab.hour, midnight.crontab.minute), ("0", "40"))


class ReconcileCommandTests(ReconcileBase):

    def test_command_summary(self):
        self._remote(self.inverter, self.day, range(3))
        out = StringIO()
        with patch.object(tasks, "scada_client", self.connector), \
                patch.object(tasks, "enqueue_recalc_for_reconciled") as enqueue:
            call_command("reconcile_measurements", "--from", "2026-09-30", "--to", "2026-09-30",
                         "--devices", str(self.inverter.id), "--no-recalc", stdout=out)
        text = out.getvalue()
        self.assertIn("Inversor UCC: 1 días, 1 re-descargados, +3 filas, 0 con diferencia", text)
        self.assertIn("Recálculo omitido", text)
        enqueue.assert_not_called()
