from __future__ import annotations
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import database as db
class DatabaseCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / 'test_control_ps.db'
        self._patch = patch.object(db, 'DB_PATH', self._db_path)
        self._patch.start()
        db.init_db()
    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()
    def test_station_ids_initialized(self) -> None:
        ids = db.list_station_ids()
        self.assertGreaterEqual(len(ids), 1)
        self.assertTrue(all((isinstance(s, str) for s in ids)))
    def test_revenue_split_empty_day(self) -> None:
        day = db.current_business_date().isoformat()
        split = db.revenue_split_for_day(day)
        self.assertIn('total', split)
        self.assertIn('session_total', split)
        self.assertIn('drink_total', split)
        self.assertGreaterEqual(split['total'], 0.0)
    def test_booking_and_expense_roundtrip(self) -> None:
        bid = db.add_booking('Test', '+998901234567', 'STOL-01', '2026-07-10T12:00:00')
        self.assertGreater(bid, 0)
        bookings = db.list_bookings('Test')
        self.assertEqual(len(bookings), 1)
        eid = db.add_expense('Test xarajat', 5000, 'cash', 'note')
        self.assertGreater(eid, 0)
        expenses = db.list_expenses('Test')
        self.assertEqual(len(expenses), 1)
        total = db.expense_total_for_day()
        self.assertGreaterEqual(total, 5000.0)
    def test_debtor_add_and_list(self) -> None:
        did = db.add_debtor('Ali', '+998901111111', 10000, 'test')
        self.assertGreater(did, 0)
        rows = db.list_debtors('Ali')
        self.assertEqual(len(rows), 1)
        self.assertEqual(float(rows[0]['amount']), 10000.0)
    def test_joystick_time_prorate(self) -> None:
        from datetime import datetime, timedelta
        sid = db.list_station_ids()[0]
        session_id = db.start_session_row(sid, total_seconds=5400, is_vip=True)
        db.add_joystick_charge(sid, 3000, session_id)
        past = (datetime.now() - timedelta(minutes=30)).isoformat(timespec='seconds')
        conn = db._connect()
        conn.execute('UPDATE drink_orders SET order_time = ? WHERE session_id = ? AND item_type = \'joystick\'', (past, session_id))
        conn.commit()
        conn.close()
        total = db.get_station_drink_total(sid, session_id)
        self.assertAlmostEqual(total, 2000.0, delta=1.0)
        finalized = db.finalize_joystick_charges(session_id, datetime.now())
        self.assertAlmostEqual(finalized, 2000.0, delta=1.0)
        total2 = db.get_station_drink_total(sid, session_id)
        self.assertAlmostEqual(total2, finalized, delta=1.0)
    def test_money_writes_are_thousands(self) -> None:
        from app.core.money import round_to_thousand
        db.add_click(134500)
        self.assertEqual(db.click_total_for_cash_period(), 135000.0)
        db.add_expense('Test', 2500, 'cash')
        self.assertEqual(db.expense_total_for_day(), 3000.0)
        did = db.add_debtor('Ali', '', 7499)
        rows = db.list_debtors('Ali')
        self.assertEqual(float(rows[0]['amount']), 7000.0)
        self.assertEqual(round_to_thousand(7499), 7000.0)
        self.assertEqual(did, rows[0]['id'])
    def test_safe_expense_reduces_ceyf_not_kassa(self) -> None:
        before = db.get_safe_balance()
        db.add_to_safe_balance(10000)
        db.add_expense('Test ceyf', 3000, 'safe', 'audit')
        self.assertAlmostEqual(db.get_safe_balance(), before + 7000, delta=0.01)
        start, end = db.cash_period_bounds()
        cash_exp = db.expense_total_between(start, end, wallet='cash')
        safe_exp = db.expense_total_between(start, end, wallet='safe')
        self.assertGreaterEqual(safe_exp, 3000.0)
        self.assertEqual(db.expense_total_between(start, end, wallet='cash'), cash_exp)
    def test_update_expense_name_and_amount_adjusts_ceyf(self) -> None:
        before = db.get_safe_balance()
        db.add_to_safe_balance(20000)
        eid = db.add_expense('Abet', 5000, 'safe', 'osh')
        self.assertAlmostEqual(db.get_safe_balance(), before + 15000, delta=0.01)
        updated = db.update_expense(eid, 'Abet kechki', 8000)
        self.assertEqual(updated['expense_type'], 'Abet kechki')
        self.assertEqual(float(updated['amount']), 8000.0)
        self.assertAlmostEqual(db.get_safe_balance(), before + 12000, delta=0.01)
        cash_id = db.add_expense('Rasul', 4000, 'cash')
        cash_before = db.get_safe_balance()
        db.update_expense(cash_id, 'Rasul 2', 6000)
        self.assertAlmostEqual(db.get_safe_balance(), cash_before, delta=0.01)
        rows = db.list_expenses('Rasul 2')
        self.assertEqual(len(rows), 1)
        self.assertEqual(float(rows[0]['amount']), 6000.0)
    def test_joystick_goes_to_playstation_not_goods(self) -> None:
        from datetime import datetime, timedelta
        sid = db.list_station_ids()[0]
        session_id = db.start_session_row(sid, total_seconds=5400, is_vip=True)
        db.add_joystick_charge(sid, 3000, session_id)
        past = (datetime.now() - timedelta(minutes=30)).isoformat(timespec='seconds')
        conn = db._connect()
        conn.execute('UPDATE drink_orders SET order_time = ? WHERE session_id = ? AND item_type = \'joystick\'', (past, session_id))
        conn.commit()
        conn.close()
        goods, joy = db.split_session_charges(sid, session_id)
        self.assertAlmostEqual(joy, 2000.0, delta=1.0)
        self.assertEqual(goods, 0.0)
        db.set_drink_price('Cola', 0.5, 8000, quantity=10)
        db.add_drink_order(sid, 'Cola', 0.5, 8000, session_id)
        goods2, joy2 = db.split_session_charges(sid, session_id)
        self.assertEqual(goods2, 8000.0)
        self.assertAlmostEqual(joy2, 2000.0, delta=1.0)
        items = db.get_session_orders_grouped(session_id, sid)
        visible = [str(i.get('name') or '') for i in items if str(i.get('item_type') or '') != 'joystick']
        self.assertIn('Cola', visible)
        self.assertTrue(all(n != 'Jostik' for n in visible))
    def test_new_session_does_not_show_walkin_orders(self) -> None:
        sid = db.list_station_ids()[0]
        db.set_drink_price('Fanta', 1.0, 7000, quantity=10)
        db.add_drink_order(sid, 'Fanta', 1.0, 7000, None)
        session_id = db.start_session_row(sid, total_seconds=0, is_vip=True)
        items = db.get_session_orders_grouped(session_id, sid)
        self.assertEqual(items, [])
        goods, joy = db.split_session_charges(sid, session_id)
        self.assertEqual(goods, 0.0)
        self.assertEqual(joy, 0.0)
        walkin = db.get_session_orders_grouped(None, sid)
        self.assertTrue(any(str(i.get('name')) == 'Fanta' for i in walkin))
    def test_receipt_hides_joystick_rows(self) -> None:
        from app.ui.dialogs.customer_display import receipt_display_items
        products, buy = receipt_display_items([{'name': 'Cola', 'item_type': 'drink'}, {'name': 'Jostik', 'item_type': 'joystick'}, {'name': 'X', 'item_type': 'buyurtma'}])
        self.assertEqual([p['name'] for p in products], ['Cola'])
        self.assertEqual([b['name'] for b in buy], ['X'])
    def test_buyurtma_excluded_from_cash_and_goods(self) -> None:
        from datetime import datetime, timedelta
        sid = db.list_station_ids()[0]
        session_id = db.start_session_row(sid, total_seconds=3600, is_vip=True)
        db.add_session_buyurtma(sid, session_id, 12000, 'Pizza')
        goods, joy = db.split_session_charges(sid, session_id)
        self.assertEqual(goods, 0.0)
        self.assertEqual(float(db.get_session_buyurtma_total(sid, session_id)), 12000.0)
        now = datetime.now()
        start = (now - timedelta(hours=1)).isoformat(timespec='seconds')
        db.end_session_row(session_id, 60, 26000)
        conn = db._connect()
        conn.execute('UPDATE sessions SET end_time = ? WHERE id = ?', (now.isoformat(timespec='seconds'), session_id))
        conn.commit()
        conn.close()
        report = db.operator_report_between(start, (now + timedelta(seconds=2)).isoformat(timespec='seconds'))
        self.assertEqual(float(report.get('buyurtma_total') or 0), 12000.0)
        self.assertAlmostEqual(float(report.get('total') or 0), 26000.0, delta=1.0)
        self.assertAlmostEqual(float(report['total']), float(report['session_total']) + float(report['drink_total']) + float(report['market_total']) + float(report['joystick_total']), delta=0.01)
        split = db.revenue_split_for_day(db.current_business_date().isoformat())
        self.assertGreaterEqual(float(split.get('total') or 0), 26000.0)
        rows = db.sessions_breakdown_for_day(db.current_business_date().isoformat())
        mine = next(r for r in rows if int(r.get('id') or 0) == session_id)
        self.assertAlmostEqual(float(mine.get('session_revenue') or 0), 26000.0, delta=1.0)
        self.assertAlmostEqual(float(mine.get('buyurtma_revenue') or 0), 12000.0, delta=1.0)
    def test_cancel_buyurtma_keeps_closed_session_revenue(self) -> None:
        sid = db.list_station_ids()[0]
        session_id = db.start_session_row(sid, total_seconds=3600, is_vip=True)
        oid = db.add_session_buyurtma(sid, session_id, 12000, 'Pizza')
        db.end_session_row(session_id, 60, 26000)
        self.assertTrue(db.cancel_order_and_return_stock(oid))
        row = db.get_session_by_id(session_id)
        self.assertAlmostEqual(float(row['revenue'] or 0), 26000.0, delta=0.01)
        self.assertEqual(float(db.get_session_buyurtma_total(sid, session_id)), 0.0)
    def test_vidaa_standby_state_detects_fake_sleep(self) -> None:
        from app.tv.vidaa_platform import _state_is_standby
        self.assertTrue(_state_is_standby({'statetype': 'fake_sleep_0'}))
        self.assertTrue(_state_is_standby({'statetype': 'fake_sleep'}))
        self.assertTrue(_state_is_standby({'statetype': 'livetv', 'fake_sleep': 1}))
        self.assertFalse(_state_is_standby({'statetype': 'livetv'}))
        self.assertFalse(_state_is_standby(None))
        self.assertFalse(_state_is_standby({}))
    def test_vidaa_token_repair_sets_expiry(self) -> None:
        import json
        from app.tv.vidaa_platform import _repair_token_expiry
        path = Path(self._tmpdir.name) / 'vidaa_tokens.json'
        path.write_text(json.dumps({'dev1': {'access_token': 'a', 'refresh_token': 'r', 'client_id': 'c'}}), encoding='utf-8')
        _repair_token_expiry(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        tok = data['dev1']
        self.assertIn('access_token_expires_at', tok)
        self.assertIn('refresh_token_expires_at', tok)
        self.assertLess(float(tok['access_token_expires_at']), time.time())
    def test_round_to_thousand(self) -> None:
        from app.core.money import round_to_thousand
        self.assertEqual(round_to_thousand(12783), 13000)
        self.assertEqual(round_to_thousand(27421), 27000)
        self.assertEqual(round_to_thousand(500), 1000)
        self.assertEqual(round_to_thousand(499), 0)
        self.assertEqual(round_to_thousand(1500), 2000)
        self.assertEqual(round_to_thousand(1499), 1000)
class ServiceLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / 'test_services.db'
        self._patch = patch.object(db, 'DB_PATH', self._db_path)
        self._patch.start()
        db.init_db()
        from app.core.container import build_container
        self.container = build_container()
    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()
    def test_container_builds(self) -> None:
        self.assertGreater(len(self.container.stations.list_station_ids()), 0)
    def test_finance_balance_summary(self) -> None:
        bal = self.container.finance.balance_summary()
        self.assertIn('total', bal)
        self.assertIn('safe', bal)
        self.assertIn('cash', bal)
    def test_inventory_products_list(self) -> None:
        products = self.container.inventory.all_products_for_display()
        self.assertIsInstance(products, list)
if __name__ == '__main__':
    unittest.main()