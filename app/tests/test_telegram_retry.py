from unittest import TestCase
import urllib.error

from app.services.telegram_notify import retry_after_seconds


class TelegramRetryTests(TestCase):
    def test_retry_after_header(self):
        headers = {'Retry-After': '7'}
        err = urllib.error.HTTPError('https://api.telegram.org', 429, 'Too Many', headers, None)
        self.assertGreaterEqual(retry_after_seconds(err), 7.0)

    def test_timeout_backoff(self):
        self.assertGreaterEqual(retry_after_seconds(TimeoutError('timed out')), 2.0)

    def test_generic_backoff(self):
        self.assertGreaterEqual(retry_after_seconds(RuntimeError('fail')), 1.0)
