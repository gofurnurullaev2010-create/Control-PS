"""Telegram: kassa jabıwda 3 ta xabar (summary, detal, PDF)."""
from __future__ import annotations
import json
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional
import database as db
from app.services.shift_report import enrich_shift_report, format_shift_details, format_shift_summary, generate_product_pdf
logger = logging.getLogger(__name__)
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
def _api(token: str, method: str, payload: dict[str, Any], timeout: int=15) -> dict[str, Any]:
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))
def _send_message(token: str, chat_id: str, text: str) -> None:
    chunk = text
    while chunk:
        part, chunk = (chunk[:4000], chunk[4000:])
        _api(token, 'sendMessage', {'chat_id': chat_id, 'text': part})
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
    req = urllib.request.Request(url, data=bytes(body), headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if not result.get('ok'):
            raise RuntimeError(str(result))
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
def send_cash_close_notifications(report: dict[str, Any], pdf_path: Optional[Path]=None) -> None:
    """3 ta xabar: summary, detal, PDF. Sinxron (fon oqimida chaqiriladi)."""
    token, _ = get_telegram_config()
    chat_ids = get_telegram_chat_ids()
    if not token or not chat_ids:
        logger.info('Telegram sozlanmagan — xabar yuborilmadi.')
        return
    else:
        snap = enrich_shift_report(report) if not report.get('summary_text') else dict(report)
        if not snap.get('summary_text'):
            snap = enrich_shift_report(snap)
        summary = str(snap.get('summary_text') or format_shift_summary(snap))
        details = str(snap.get('details_text') or format_shift_details(snap))
        path = Path(pdf_path) if pdf_path else generate_product_pdf(snap)
        try:
            _send_message_all(token, chat_ids, summary)
            _send_message_all(token, chat_ids, details)
            _send_document_all(token, chat_ids, path, caption=path.name)
            logger.info('Telegram kassa xabarlari yuborildi (%s)', ', '.join(chat_ids))
        except Exception:
            logger.exception('Telegram yuborishda xatolik')
            raise
def notify_cash_close_async(report: dict[str, Any]) -> None:
    """UI ni bloklamasdan yuborish. PDF asosiy oqimda yaratiladi (Qt)."""
    snap = dict(report or {})
    pdf = None
    try:
        if not snap.get('summary_text'):
            snap = enrich_shift_report(snap)
        pdf = generate_product_pdf(snap)
    except Exception as e:
        logger.warning('PDF yaratilmadi: %s', e)
    def _run() -> None:
        try:
            send_cash_close_notifications(snap, pdf_path=pdf)
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