import pytest
from pipeline import aqi

def test_pm25_to_aqi_2024_anchors():
    assert aqi.pm25_to_aqi(0.0) == 0
    assert aqi.pm25_to_aqi(9.0) == 50      # updated 2024 Good/Moderate boundary
    assert aqi.pm25_to_aqi(35.4) == 100
    assert aqi.pm25_to_aqi(55.4) == 150
    assert aqi.pm25_to_aqi(125.4) == 200

def test_pm25_to_aqi_midrange():
    # 20 ug/m3 -> Moderate band, between 51 and 100
    v = aqi.pm25_to_aqi(20.0)
    assert 51 <= v <= 100

def test_barkjohn_reduces_and_uses_humidity():
    # Barkjohn 2021: 0.52*PA - 0.086*RH + 5.75  (PA<=343)
    corrected = aqi.barkjohn_correct(100.0, 50.0)
    assert corrected == pytest.approx(0.52 * 100 - 0.086 * 50 + 5.75, abs=0.01)
    assert corrected < 100.0

def test_barkjohn_non_negative():
    assert aqi.barkjohn_correct(0.0, 90.0) >= 0.0
