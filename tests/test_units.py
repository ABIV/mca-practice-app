import math
from pipeline import units

def test_c_to_f():
    assert units.c_to_f(0) == 32.0
    assert units.c_to_f(100) == 212.0
    assert round(units.c_to_f(31.7), 1) == 89.1

def test_ms_to_mph():
    assert round(units.ms_to_mph(1), 3) == 2.237

def test_haversine_mi_known_distance():
    # Minneapolis (44.98,-93.27) to St Paul (44.95,-93.09) ~ 8.8 mi
    d = units.haversine_mi(44.98, -93.27, 44.95, -93.09)
    assert 8.0 < d < 10.0
