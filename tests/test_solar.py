from datetime import datetime, timezone

import pytest

from pipeline import solar


def test_solar_noon_elevation_summer_minneapolis():
    # 2026-06-21 ~18:00 UTC (~13:00 CDT) near solar noon, lat 45N.
    dt = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)
    elev = solar.solar_elevation_deg(dt, 45.0, -93.4)
    # Max elevation at 45N on solstice ~ 68.4 deg; near-noon should be high.
    assert 60.0 < elev < 69.0


def test_solar_night_elevation_negative():
    dt = datetime(2026, 6, 21, 6, 0, tzinfo=timezone.utc)  # ~01:00 CDT
    assert solar.solar_elevation_deg(dt, 45.0, -93.4) < 0


def test_clear_sky_zero_below_horizon():
    assert solar.clear_sky_ghi(-5) == 0.0


def test_clear_sky_positive_high_sun():
    assert solar.clear_sky_ghi(60) > 700.0


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        solar.solar_elevation_deg(datetime(2026, 6, 21, 18, 0), 45.0, -93.4)
