from datetime import date, timedelta
from django.test import TestCase
from indicators.services.date_ranges import (
    resolve_indicators_hourly_range,
    INDICATORS_HOURLY_MAX_RANGE_DAYS,
    INDICATORS_HOURLY_DEFAULT_RANGE_DAYS,
)


class HourlyRangeLimitsTest(TestCase):
    def test_limit_is_31_days(self):
        self.assertEqual(INDICATORS_HOURLY_MAX_RANGE_DAYS, 31)

    def test_default_is_14_days(self):
        self.assertEqual(INDICATORS_HOURLY_DEFAULT_RANGE_DAYS, 14)

    def test_31_day_range_is_accepted(self):
        end = date(2026, 7, 31)
        start = end - timedelta(days=30)  # 31 días inclusive
        s, e, err = resolve_indicators_hourly_range(None, start.isoformat(), end.isoformat())
        self.assertIsNone(err)
        self.assertEqual((s, e), (start, end))

    def test_32_day_range_is_rejected(self):
        end = date(2026, 7, 31)
        start = end - timedelta(days=31)  # 32 días inclusive
        s, e, err = resolve_indicators_hourly_range(None, start.isoformat(), end.isoformat())
        self.assertIsNotNone(err)

    def test_default_start_is_14_days_back(self):
        s, e, err = resolve_indicators_hourly_range(None, None, "2026-07-31")
        self.assertIsNone(err)
        self.assertEqual(s, date(2026, 7, 31) - timedelta(days=INDICATORS_HOURLY_DEFAULT_RANGE_DAYS - 1))
