import pytest
from pipeline import wbgt

def test_stull_wet_bulb_reference():
    # Stull (2011) reference: 20C / 50% RH -> ~13.7C wet bulb
    assert wbgt.stull_wet_bulb_c(20.0, 50.0) == pytest.approx(13.7, abs=0.3)

def test_wbgt_hot_dry_reference():
    # 89F, 33% RH, 9.6 mph, 462 W/m^2 -> expect ~76-78F  (spec anchor)
    val = wbgt.wbgt_f(89.0, 33.0, 9.6, 462.0)
    assert 76.0 <= val <= 78.0

def test_wbgt_humid_case_higher_than_dry():
    # Humid: 85F, 80% RH, low wind, moderate sun -> WBGT should be high (>80F)
    val = wbgt.wbgt_f(85.0, 80.0, 3.0, 400.0)
    assert val > 80.0

def test_black_globe_above_air_in_sun():
    tg = wbgt.black_globe_f(89.0, 9.6, 462.0)
    assert tg > 89.0  # sun-loaded globe hotter than air

def test_black_globe_equals_air_no_sun():
    tg = wbgt.black_globe_f(70.0, 5.0, 0.0)
    assert tg == pytest.approx(70.0, abs=0.5)
