"""PS billing regression — VIP kechasi 7000 chiqmasligi kerak."""
from datetime import datetime
from app.core.money import round_to_thousand
from app.core.ps_billing import billable_seconds, playstation_amount, sanitize_hourly_rate, time_amount
def test_vip_overnight_never_seven_thousand():
    start = datetime(2026, 8, 1, 19, 47, 0)
    end = datetime(2026, 8, 2, 2, 25, 0)
    sec = billable_seconds(is_vip=True, start=start, end=end, booked_seconds=0)
    assert sec == 23880
    assert billable_seconds(is_vip=True, start=start, end=end) == 23880
    amt = time_amount(23000, sec)
    assert round_to_thousand(amt) == 153000
    assert round_to_thousand(amt) != 7000
def test_timed_pays_played_not_booked():
    start = datetime(2026, 8, 2, 10, 0, 0)
    end = datetime(2026, 8, 2, 10, 15, 0)
    sec = billable_seconds(is_vip=False, start=start, end=end, booked_seconds=3600)
    assert sec == 900
    assert round_to_thousand(time_amount(20000, sec)) == 5000
def test_sanitize_typo_rate():
    assert sanitize_hourly_rate(150000, 18000) == 15000
def test_live_overtime_grows_past_booked():
    start = datetime(2026, 8, 2, 10, 0, 0)
    end = datetime(2026, 8, 2, 12, 10, 0)
    from app.core.ps_billing import live_playstation_amount
    live = live_playstation_amount('STOL-01', is_vip=False, start=start, now=end, booked_seconds=7200, locked_rate=18000)
    final = playstation_amount('STOL-01', is_vip=False, start=start, end=end, booked_seconds=7200, locked_rate=18000)
    assert abs(live - final) < 1
    assert live > time_amount(18000, 7200)
def test_playstation_amount_locked():
    start = datetime(2026, 8, 1, 19, 47, 0)
    end = datetime(2026, 8, 2, 2, 25, 0)
    amt = playstation_amount('STOL-11', is_vip=True, start=start, end=end, locked_rate=23000)
    assert abs(amt - 152566.666) < 1
def test_prepaid_amount_crosses_evening_rate():
    """17:00 da 24000, 18:00 gacha 15000, keyin 18000 → 1 soat 30 daqiqa."""
    from app.core.ps_billing import prepaid_seconds_for_amount, slot_walked_amount
    slots = [
        {'start_minute': 0, 'end_minute': 18 * 60, 'hourly_rate': 15000},
        {'start_minute': 18 * 60, 'end_minute': 0, 'hourly_rate': 18000},
    ]
    start = datetime(2026, 9, 8, 17, 0, 0)
    sec = prepaid_seconds_for_amount(24000, start, slots, 15000)
    assert sec == 5400
    assert abs(slot_walked_amount(start, sec, slots, 15000) - 24000) < 0.01
def test_prepaid_amount_single_rate():
    from app.core.ps_billing import prepaid_seconds_for_amount
    slots = [{'start_minute': 0, 'end_minute': 0, 'hourly_rate': 18000}]
    start = datetime(2026, 9, 8, 12, 0, 0)
    assert prepaid_seconds_for_amount(18000, start, slots, 18000) == 3600
    assert prepaid_seconds_for_amount(9000, start, slots, 18000) == 1800
if __name__ == '__main__':
    test_vip_overnight_never_seven_thousand()
    test_timed_pays_played_not_booked()
    test_sanitize_typo_rate()
    test_live_overtime_grows_past_booked()
    test_playstation_amount_locked()
    test_prepaid_amount_crosses_evening_rate()
    test_prepaid_amount_single_rate()
    print('ps_billing OK')