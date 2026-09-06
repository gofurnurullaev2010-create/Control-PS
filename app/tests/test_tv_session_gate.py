"""STOP bir stol — boshqa stolning TVsi ochiq qolsin."""
from app.tv import tv_handler as t


def setup_module():
    t.set_main_app_lock_gate(True)
    with t._active_tv_lock:
        t._active_tv_hosts.clear()


def teardown_module():
    with t._active_tv_lock:
        t._active_tv_hosts.clear()
    with t._pending_lock_guard:
        t._pending_lock_hosts.clear()
    t.set_main_app_lock_gate(False)


def test_stop_table_two_does_not_lock_table_three_same_ip():
    t.set_main_app_lock_gate(True)
    with t._active_tv_lock:
        t._active_tv_hosts.clear()
    ip = '192.168.1.30'
    t.register_tv_session(ip, station_id='STOL-03')
    t.register_tv_session(ip, station_id='STOL-02')
    assert t._should_lock_tv(ip) is False
    t.unregister_tv_session(ip, station_id='STOL-02')
    assert t._should_lock_tv(ip) is False
    assert t.is_lock_pending(ip) is False
    t.unregister_tv_session(ip, station_id='STOL-03')
    assert t._should_lock_tv(ip) is True
    assert t.is_lock_pending(ip) is True


def test_stop_exclusive_tv_locks():
    t.set_main_app_lock_gate(True)
    with t._active_tv_lock:
        t._active_tv_hosts.clear()
    t.register_tv_session('192.168.1.2', station_id='STOL-02')
    t.register_tv_session('192.168.1.3', station_id='STOL-03')
    t.unregister_tv_session('192.168.1.2', station_id='STOL-02')
    assert t._should_lock_tv('192.168.1.2') is True
    assert t._should_lock_tv('192.168.1.3') is False


def test_pending_lock_after_offline_stop():
    t.set_main_app_lock_gate(True)
    with t._pending_lock_guard:
        t._pending_lock_hosts.clear()
    ip = '192.168.1.50'
    t.register_tv_session(ip, station_id='STOL-01')
    assert t.is_lock_pending(ip) is False
    t.unregister_tv_session(ip, station_id='STOL-01')
    assert t._should_lock_tv(ip) is True
    assert t.is_lock_pending(ip) is True
    t.register_tv_session(ip, station_id='STOL-01')
    assert t.is_lock_pending(ip) is False
    t.unregister_tv_session(ip, station_id='STOL-01')
    assert t.is_lock_pending(ip) is True


if __name__ == '__main__':
    setup_module()
    test_stop_table_two_does_not_lock_table_three_same_ip()
    test_stop_exclusive_tv_locks()
    test_pending_lock_after_offline_stop()
    teardown_module()
    print('tv_session_gate OK')
