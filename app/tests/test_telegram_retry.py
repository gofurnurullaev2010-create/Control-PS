from unittest import TestCase
from unittest.mock import patch
import io
import urllib.error

from app.services.telegram_notify import retry_after_seconds, send_cash_close_notifications


class TelegramRetryTests(TestCase):
    def test_retry_after_header(self):
        headers = {'Retry-After': '7'}
        err = urllib.error.HTTPError('https://api.telegram.org', 429, 'Too Many', headers, None)
        self.assertGreaterEqual(retry_after_seconds(err), 7.0)

    def test_timeout_backoff(self):
        self.assertGreaterEqual(retry_after_seconds(TimeoutError('timed out')), 1.0)

    def test_generic_backoff(self):
        self.assertGreaterEqual(retry_after_seconds(RuntimeError('fail')), 1.0)

    def test_retry_after_json_body(self):
        body = io.BytesIO(b'{"ok":false,"error_code":429,"parameters":{"retry_after":11}}')
        err = urllib.error.HTTPError('https://api.telegram.org', 429, 'Too Many', {}, body)
        self.assertGreaterEqual(retry_after_seconds(err), 11.0)


class TelegramCashClosePartsTests(TestCase):
    def test_details_still_sent_if_summary_fails(self):
        calls = []

        def fake_send(_token, cid, text):
            calls.append(text[:20])
            if text.startswith('SUM'):
                raise RuntimeError('summary fail')

        with patch('app.services.telegram_notify.get_telegram_config', return_value=('tok', '1')), \
             patch('app.services.telegram_notify.get_telegram_chat_ids', return_value=['1']), \
             patch('app.services.telegram_notify._send_message', side_effect=fake_send), \
             patch('app.services.telegram_notify.time.sleep', return_value=None):
            send_cash_close_notifications(
                {'summary_text': 'SUM smena', 'details_text': 'DET smena'},
                texts_only=True,
            )
        self.assertTrue(any(c.startswith('DET') for c in calls))
