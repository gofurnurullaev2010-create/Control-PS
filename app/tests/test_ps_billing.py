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
if __name__ == '__main__':
    test_vip_overnight_never_seven_thousand()
    test_timed_pays_played_not_booked()
    test_sanitize_typo_rate()
    test_live_overtime_grows_past_booked()
    test_playstation_amount_locked()
    print('ps_billing OK')