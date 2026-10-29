import pytest
from datetime import datetime
from backend.services.opening_hours import check_opening_hours

def test_24x7_opening_hours():
    dt_day = datetime(2026, 10, 28, 14, 0)
    dt_night = datetime(2026, 10, 28, 2, 30)

    res_1 = check_opening_hours("24/7", dt_day)
    assert res_1["is_open"] is True
    assert res_1["is_24x7"] is True
    assert res_1["weight"] == 1.0

    res_2 = check_opening_hours("open 24 hours", dt_night)
    assert res_2["is_open"] is True
    assert res_2["is_24x7"] is True

def test_overnight_shift():
    # 18:00 - 03:00
    # Wednesday 23:00 -> Open
    dt_wed_night = datetime(2026, 10, 28, 23, 0) # 2026-10-28 is a Wednesday
    res_open = check_opening_hours("Mo-Su 18:00-03:00", dt_wed_night)
    assert res_open["is_open"] is True

    # Thursday 02:00 -> Open (spans over from Wednesday)
    dt_thu_morning = datetime(2026, 10, 29, 2, 0)
    res_overnight = check_opening_hours("Mo-Su 18:00-03:00", dt_thu_morning)
    assert res_overnight["is_open"] is True

    # Thursday 12:00 -> Closed
    dt_thu_noon = datetime(2026, 10, 29, 12, 0)
    res_closed = check_opening_hours("Mo-Su 18:00-03:00", dt_thu_noon)
    assert res_closed["is_open"] is False
    assert res_closed["weight"] == 0.0

def test_closed_days():
    # Mo-Fr 09:00-18:00
    # Saturday 14:00 -> Closed
    dt_sat = datetime(2026, 10, 31, 14, 0) # Saturday
    res_sat = check_opening_hours("Mo-Fr 09:00-18:00", dt_sat)
    assert res_sat["is_open"] is False

    # Wednesday 11:00 -> Open
    dt_wed = datetime(2026, 10, 28, 11, 0) # Wednesday
    res_wed = check_opening_hours("Mo-Fr 09:00-18:00", dt_wed)
    assert res_wed["is_open"] is True

def test_unknown_and_missing():
    dt = datetime(2026, 10, 28, 2, 0)
    res_none = check_opening_hours(None, dt)
    assert res_none["status"] == "unknown"
    assert res_none["weight"] == 0.3

    res_empty = check_opening_hours("", dt)
    assert res_empty["status"] == "unknown"
    assert res_empty["weight"] == 0.3

    res_gibberish = check_opening_hours("by appointment only", dt)
    assert res_gibberish["status"] == "unknown"
    assert res_gibberish["weight"] == 0.3
