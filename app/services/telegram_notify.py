"""Telegram: kassa jabıwda 3 ta xabar (summary, detal, PDF)."""
from __future__ import annotations
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional
import database as db
from app.services.shift_report import enrich_shift_report, format_shift_details, format_shift_summary, generate_product_pdf
logger = logging.getLogger(__name__)

_SEND_ATTEMPTS = 4
_BETWEEN_MESSAGES_S = 0.25

def _parse_chat_ids(raw: str) -> list[str]:
    """Bitta yoki bir nechta Chat ID — vergul / bo\'shliq / yangi qator."""
    text = (raw or '').strip()
    if not text:
        return []
    else:
        parts = re.split('[,;\\s]+', text)
        out = []
        seen = set()
        for p in parts:
            cid = p.strip()
            if not cid or cid in seen:
                continue
            else:
                seen.add(cid)
                out.append(cid)
        return out
def get_telegram_config() -> tuple[str, str]:
    """Orqaga moslik: (token, chat_ids_str). Bir nechta ID vergul bilan."""
    token = (db._setting_get('telegram_bot_token', '') or '').strip()
    chat = (db._setting_get('telegram_chat_id', '') or '').strip()
    return (token, chat)
def get_telegram_chat_ids() -> list[str]:
    _, chat = get_telegram_config()
    return _parse_chat_ids(chat)
def set_telegram_config(token: str, chat_id: str) -> None:
    ids = _parse_chat_ids(chat_id)
    db._setting_set('telegram_bot_token', (token or '').strip())
    db._setting_set('telegram_chat_id', ', '.join(ids))
def _friendly_telegram_error(exc: Exception) -> str:
    text = str(exc or '')
    low = text.lower()
    if '10051' in text or 'network is unreachable' in low or 'отключенной сети' in low:
        return (
            'Internet yo\'q — Telegramga chiqib bo\'lmayapti (WinError 10051).\n'
            'Bu PC da internet (Wi‑Fi/kabel) yoqing. TV tarmog\'i yetarli emas: '
            'api.telegram.org ochiq bo\'lishi kerak.\n'
            'VPN/firewall Telegramni bloklamasin, keyin «Test xabar» ni qayta bosing.'
        )
    if '10060' in text or 'timed out' in low or 'timeout' in low:
        return 'Telegram javob bermadi (timeout). Internet sekin yoki api.telegram.org bloklangan.'
    if '10061' in text or 'connection refused' in low:
        return 'Telegram ulanishni rad etdi. Firewall yoki antivirusni tekshiring.'
    if '11001' in text or 'getaddrinfo' in low or 'nameresolution' in low.replace(' ', ''):
        return 'DNS Telegram manzilini topa olmadi. Internet/DNS ni tekshiring.'
    return text
def retry_after_seconds(exc: Exception) -> float:
    """429 / tarmoq xatosidan keyin kutish (soniya)."""
    if isinstance(exc, urllib.error.HTTPError):
        headers = getattr(exc, 'headers', None)
        ra = ''
        if headers is not None:
            ra = str(headers.get('Retry-After') or headers.get('retry-after') or '').strip()
        if ra.isdigit():
            return min(float(ra) + 0.3, 20.0)
        body_text = ''
        try:
            raw = exc.read()
            if raw:
                body_text = raw.decode('utf-8', 'replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
        except Exception:
            body_text = ''
        if body_text:
            try:
                data = json.loads(body_text)
                pra = (data.get('parameters') or {}).get('retry_after')
                if pra is not None:
                    return min(float(pra) + 0.3, 20.0)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        if int(getattr(exc, 'code', 0) or 0) == 429:
            return 3.0
        if int(getattr(exc, 'code', 0) or 0) in (500, 502, 503, 504):
            return 2.0
    text = str(exc or '').lower()
    if 'retry after' in text:
        m = re.search(r'retry after[^\d]*(\d+)', text)
        if m:
            return min(float(m.group(1)) + 0.3, 20.0)
    if '429' in text or 'too many' in text or 'flood' in text:
        return 3.0
    if '10060' in text or 'timed out' in text or 'timeout' in text:
        return 1.2
    if '10051' in text or '10054' in text or '10053' in text:
        return 1.5
    return 1.0
def _call_with_retry(label: str, fn: Callable[[], Any], attempts: int=_SEND_ATTEMPTS) -> Any:
    last: Optional[Exception] = None
    for i in range(max(1, attempts)):
        try:
            return fn()
        except Exception as e:
            last = e
            wait = retry_after_seconds(e)
            logger.warning('Telegram %s urinish %s/%s: %s (%.1fs)', label, i + 1, attempts, e, wait)
            if i + 1 < attempts:
                time.sleep(wait)
    raise last if last else RuntimeError(label)
def _api(token: str, method: str, payload: dict[str, Any], timeout: int=12) -> dict[str, Any]:
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if not result.get('ok'):
            raise RuntimeError(str(result))
        return result
def _send_message(token: str, chat_id: str, text: str) -> None:
    chunk = text
    while chunk:
        part, chunk = (chunk[:4000], chunk[4000:])
        payload = {
            'chat_id': chat_id,
            'text': part,
            'disable_web_page_preview': True,
        }
        _call_with_retry('sendMessage', lambda p=payload: _api(token, 'sendMessage', p))
def _send_document(token: str, chat_id: str, path: Path, caption: str='') -> None:
    boundary = '----ControlPSBoundary7MA4YWxkTrZu0gW'
    file_bytes = path.read_bytes()
    filename = path.name
    body = bytearray()
    def add_field(name: str, value: str) -> None:
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(f'Content-Disposition: form-data; name=\"{name}\"\r\n\r\n'.encode())
        body.extend(value.encode('utf-8'))
        body.extend(b'\r\n')
    add_field('chat_id', str(chat_id))
    if caption:
        add_field('caption', caption[:1000])
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(f'Content-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\n'.encode())
    body.extend(b'Content-Type: application/pdf\r\n\r\n')
    body.extend(file_bytes)
    body.extend(f'\r\n--{boundary}--\r\n'.encode())
    url = f'https://api.telegram.org/bot{token}/sendDocument'
    raw = bytes(body)
    def _post() -> dict[str, Any]:
        req = urllib.request.Request(url, data=raw, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST')
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if not result.get('ok'):
                raise RuntimeError(str(result))
            return result
    _call_with_retry('sendDocument', _post)
def _send_message_all(token: str, chat_ids: list[str], text: str) -> list[str]:
    """Barcha chatlarga yuborish; muvaffaqiyatsiz ID larni qaytaradi."""
    failed = []
    for cid in chat_ids:
        try:
            _send_message(token, cid, text)
        except Exception as e:
            logger.warning('Telegram sendMessage %s: %s', cid, e)
            failed.append(cid)
    return failed
def _send_document_all(token: str, chat_ids: list[str], path: Path, caption: str='') -> list[str]:
    failed = []
    for cid in chat_ids:
        try:
            _send_document(token, cid, path, caption=caption)
        except Exception as e:
            logger.warning('Telegram sendDocument %s: %s', cid, e)
            failed.append(cid)
    return failed
def send_cash_close_notifications(report: dict[str, Any], pdf_path: Optional[Path]=None, *, texts_only: bool=False) -> None:
    """3 ta xabar: summary, detal, PDF. Har biri alohida — bittasi yiqilsa qolgani ketadi."""
    token, _ = get_telegram_config()
    chat_ids = get_telegram_chat_ids()
    if not token or not chat_ids:
        logger.info('Telegram sozlanmagan — xabar yuborilmadi.')
        return
    snap = enrich_shift_report(report) if not report.get('summary_text') else dict(report)
    if not snap.get('summary_text'):
        snap = enrich_shift_report(snap)
    summary = str(snap.get('summary_text') or format_shift_summary(snap))
    details = str(snap.get('details_text') or format_shift_details(snap))
    path = Path(pdf_path) if pdf_path else None
    if not texts_only and path is None:
        try:
            path = generate_product_pdf(snap)
        except Exception as e:
            logger.warning('PDF yaratilmadi: %s', e)
            path = None
    ok_chats: list[str] = []
    last_err: Optional[Exception] = None
    for cid in chat_ids:
        sent_any = False
        for label, fn in (
            ('summary', lambda: _send_message(token, cid, summary)),
            ('details', lambda: _send_message(token, cid, details)),
        ):
            try:
                fn()
                sent_any = True
                time.sleep(_BETWEEN_MESSAGES_S)
            except Exception as e:
                last_err = e
                logger.warning('Telegram %s %s: %s', label, cid, e)
        if not texts_only:
            try:
                if path is not None and path.is_file():
                    _send_document(token, cid, path, caption=path.name)
                else:
                    _send_message(token, cid, '📄 PDF yaratilmadi — faqat matn hisobot yuborildi.')
                sent_any = True
            except Exception as e:
                last_err = e
                logger.warning('Telegram PDF %s: %s', cid, e)
        if sent_any:
            ok_chats.append(cid)
    if not ok_chats:
        raise last_err or RuntimeError('Telegram: hech qaysi chatga xabar yetmadi')
    logger.info('Telegram kassa xabarlar yuborildi (%s)', ', '.join(ok_chats))


def notify_cash_close_async(report: dict[str, Any]) -> None:
    """UI ni bloklamasdan: avval 2 matn, keyin PDF."""
    snap = dict(report or {})

    def _run() -> None:
        try:
            send_cash_close_notifications(snap)
        except Exception as e:
            logger.warning('Telegram: %s', e)

    threading.Thread(target=_run, daemon=True, name='tg-cash-close').start()
def test_telegram_connection() -> str:
    """Sozlamani tekshirish — \'ok\' yoki xato matni."""
    token, _ = get_telegram_config()
    chat_ids = get_telegram_chat_ids()
    if not token:
        return 'Bot token kiritilmagan.'
    else:
        if not chat_ids:
            return 'Chat ID kiritilmagan.'
        else:
            try:
                me = _api(token, 'getMe', {})
                if not me.get('ok'):
                    return f'Token xato: {me}'
                else:
                    username = (me.get('result') or {}).get('username') or '?'
                    failed = _send_message_all(token, chat_ids, f'✅ Eagle Playstation bot ulandi (@{username})')
                    ok_ids = [c for c in chat_ids if c not in failed]
                    if not ok_ids:
                        return f"Xato — hech qaysi chatga yetmadi: {', '.join(failed)}"
                    else:
                        msg = f"OK — @{username} → {', '.join(ok_ids)}"
                        if failed:
                            msg += f" | yetmadi: {', '.join(failed)} (botga /start yuboring)"
                        return msg
            except urllib.error.HTTPError as e:
                body = b''
                try:
                    body = e.read()[:200]
                except Exception:
                    pass
                return f'HTTP {e.code}: {body!r}'
            except Exception as e:
                return _friendly_telegram_error(e)
def notify_stock_changes_async(changes: list[dict[str, Any]]) -> str:
    """Ombor qoldig\'i qo\'lda o\'zgarganda Telegram xabar (fon).\n\n    changes: [{\"name\": \"Kola 2 L\", \"old\": 30, \"new\": 28}, ...]\n    Qaytaradi: \"queued\" | \"no_change\" | \"not_configured\"\n    """
    rows = [c for c in changes or [] if int(c.get('old') or 0) != int(c.get('new') or 0)]
    if not rows:
        return 'no_change'
    else:
        token, _ = get_telegram_config()
        chat_ids = get_telegram_chat_ids()
        if not token or not chat_ids:
            logger.info('Telegram sozlanmagan — ombor xabari yuborilmadi.')
            return 'not_configured'
        else:
            lines = ['📦 Ombor qoldig\'i o\'zgartirildi:\n']
            for c in rows:
                name = str(c.get('name') or 'Mahsulot').strip()
                old = int(c.get('old') or 0)
                new = int(c.get('new') or 0)
                lines.append(f'• {name}: {old} tadan {new} taga o\'zgartirildi')
            text = '\n'.join(lines)
            def _run() -> None:
                try:
                    _send_message_all(token, chat_ids, text)
                    logger.info('Telegram ombor xabari yuborildi (%s qator)', len(rows))
                except Exception as e:
                    logger.warning('Telegram ombor: %s', e)
            threading.Thread(target=_run, daemon=True, name='tg-stock').start()
            return 'queued'
