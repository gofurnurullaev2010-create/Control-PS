from __future__ import annotations
# -*- coding: utf-8 -*-
"""Hisense VIDAA OS TV boshqaruvi (LAN/MQTT 36669 + Wake-on-LAN).

VIDAA webOS emas: IPK o'rnatilmaydi. Birinchi marta PIN pairing qilinadi,
keyin tokenlar exe yonidagi vidaa_tokens.json faylida saqlanadi.
"""

import logging
import socket
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

VIDAA_BRANDS = frozenset({"vidaa", "hisense", "hisense_vidaa", "toshiba", "toshiba_vidaa", "tos"})
VIDAA_PORT = 36669
VIDAA_UPNP_PORT = 38400
TOKEN_FILE = "vidaa_tokens.json"
ACCESS_TOKEN_DAYS = 7
REFRESH_TOKEN_DAYS = 30


def app_dir() -> Path:
    """Token/sozlama papkasi: exe yonida, koddan ishlatilsa loyiha ildizi."""
    try:
        from app.core.runtime import app_dir as runtime_app_dir

        return runtime_app_dir()
    except Exception:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]


def is_vidaa_brand(brand: str) -> bool:
    return (brand or "").strip().lower() in VIDAA_BRANDS


def normalize_mac(mac: str) -> str:
    raw = (mac or "").strip().upper().replace("-", "").replace(":", "")
    if len(raw) == 12 and all(c in "0123456789ABCDEF" for c in raw):
        return ":".join(raw[i : i + 2] for i in range(0, 12, 2))
    dotted = (mac or "").strip().upper().replace("-", ":")
    parts = dotted.split(":")
    if len(parts) == 6 and all(len(p) == 2 for p in parts):
        return ":".join(parts)
    return dotted


def _normalize_mqtt_brand(brand: str) -> str:
    value = (brand or "").strip().lower()
    mapping = {
        "": "his",
        "vidaa": "his",
        "hisense": "his",
        "hisense_vidaa": "his",
        "toshiba": "tos",
        "toshiba_vidaa": "tos",
        "tos": "tos",
        "his": "his",
    }
    return mapping.get(value, value[:3] if len(value) > 3 else value or "his")


def _detect_vidaa_info(host: str) -> dict[str, str]:
    """VIDAA UPnP descriptoridan MQTT brand va TV UUID/MAC ni olish."""
    host = (host or "").split(":", 1)[0].strip()
    if not host:
        return {}
    url = f"http://{host}:{VIDAA_UPNP_PORT}/MediaServer/rendererdevicedesc.xml"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=3.0) as response:
            xml_content = response.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_content)
        raw: dict[str, str] = {}
        for elem in root.iter():
            if elem.text and "=" in elem.text:
                for line in elem.text.splitlines():
                    key, sep, value = line.partition("=")
                    if sep:
                        raw[key.strip()] = value.strip()
        mac = raw.get("mac") or raw.get("macEthernet") or raw.get("macWifi") or ""
        brand = raw.get("brand") or ""
        return {"mac": normalize_mac(mac), "brand": brand.strip().lower()}
    except Exception as e:
        logger.debug("VIDAA info aniqlanmadi %s: %s", host, e)
        return {}


def port_open(host: str, timeout: float = 1.0) -> bool:
    host = (host or "").split(":", 1)[0].strip()
    if not host:
        return False
    try:
        with socket.create_connection((host, VIDAA_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def wait_until_online(host: str, timeout_s: float = 12.0) -> bool:
    deadline = time.time() + max(1.0, timeout_s)
    while time.time() < deadline:
        if port_open(host, timeout=0.5):
            return True
        time.sleep(0.5)
    return port_open(host, timeout=0.5)


def _directed_broadcast(host: str) -> str:
    parts = (host or "").split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return ".".join(parts[:3] + ["255"])
    return "255.255.255.255"


def wake(mac: str, host: str = "") -> bool:
    mac = normalize_mac(mac)
    if not mac:
        return False
    broadcasts = []
    directed = _directed_broadcast(host)
    for item in (directed, "255.255.255.255"):
        if item and item not in broadcasts:
            broadcasts.append(item)
    try:
        import wakeonlan

        for broadcast in broadcasts:
            for port in (9, 7):
                for _ in range(3):
                    wakeonlan.send_magic_packet(
                        mac,
                        ip_address=broadcast,
                        port=port,
                    )
                    time.sleep(0.08)
        logger.info("VIDAA Wake-on-LAN yuborildi: %s -> %s", mac, broadcasts)
        return True
    except Exception as e:
        logger.warning("VIDAA Wake-on-LAN xato: %s", e)
        return False


def token_file_path() -> Path:
    """vidaa_tokens.json — avval exe/loyiha ildizi, eski joydan ko'chiriladi."""
    primary = app_dir() / TOKEN_FILE
    if primary.is_file():
        return primary
    legacy = Path(__file__).resolve().parent / TOKEN_FILE
    if legacy.is_file() and legacy.resolve() != primary.resolve():
        try:
            primary.parent.mkdir(parents=True, exist_ok=True)
            primary.write_bytes(legacy.read_bytes())
            logger.info("VIDAA tokenlar ko'chirildi: %s -> %s", legacy, primary)
        except Exception as e:
            logger.warning("VIDAA token ko'chirish xato: %s", e)
            return legacy
    return primary


def _repair_token_expiry(path: Path) -> None:
    """Eski token faylida muddat maydoni bo'lmasa — yangilash/refresh yoqiladi.

    Hisense access token ~7 kun, refresh ~30 kun. Muddat yo'q bo'lsa kutubxona
    tokenni o'lik deb hisoblab, 1 haftadan keyin TV ni tashlab qo'yardi.
    """
    if not path.is_file():
        return
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    now = time.time()
    changed = False
    for tok in data.values():
        if not isinstance(tok, dict):
            continue
        if tok.get("access_token") and not tok.get("access_token_expires_at"):
            if tok.get("refresh_token"):
                tok["access_token_expires_at"] = now - 60
            else:
                base = float(tok.get("access_token_time") or now)
                tok["access_token_expires_at"] = base + ACCESS_TOKEN_DAYS * 86400
            changed = True
        if tok.get("refresh_token") and not tok.get("refresh_token_expires_at"):
            base = float(tok.get("refresh_token_time") or tok.get("access_token_time") or now)
            tok["refresh_token_expires_at"] = base + REFRESH_TOKEN_DAYS * 86400
            changed = True
    if not changed:
        return
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        logger.info("VIDAA token muddatlari tiklandi: %s", path)
    except Exception as e:
        logger.warning("VIDAA token tiklash xato: %s", e)


def _token_storage():
    from vidaa.config import TokenStorage

    path = token_file_path()
    _repair_token_expiry(path)
    return TokenStorage(path)


def _client(host: str, mac: str = "", brand: str = ""):
    try:
        from vidaa import VidaaTV
    except ImportError as e:
        logger.error(
            "VIDAA kutubxona topilmadi (vidaa-control). START/STOP ishlamaydi: %s",
            e,
        )
        raise

    host = (host or "").split(":", 1)[0].strip()
    info = _detect_vidaa_info(host)
    device_mac = normalize_mac(mac) or normalize_mac(info.get("mac") or "")
    user_brand = (brand or "").strip()
    mqtt_brand = _normalize_mqtt_brand(user_brand or info.get("brand") or "")
    return VidaaTV(
        host=host,
        mac_address=device_mac,
        use_dynamic_auth=True,
        brand=mqtt_brand,
        enable_persistence=True,
        storage=_token_storage(),
    )


def _connect_ready(tv, timeout: float = 12.0) -> bool:
    """MQTT ulanish + muddati yaqin tokenni oldindan yangilash."""
    try:
        ok = bool(tv.connect(timeout=timeout, auto_auth=True, auto_refresh=True))
    except Exception as e:
        logger.warning("VIDAA connect xato %s: %s", getattr(tv, "host", ""), e)
        return False
    if not ok:
        logger.warning(
            "VIDAA MQTT ulanmadi %s. Token eskirgan bo'lishi mumkin — "
            "TV sozlamalarida «VIDAA PIN pairing» ni qayta qiling.",
            getattr(tv, "host", ""),
        )
        return False
    try:
        storage = getattr(tv, "_storage", None)
        if storage is not None:
            status = storage.get_token_status(
                device_id=getattr(tv, "mac_address", None) or None,
                host=getattr(tv, "host", None),
                port=getattr(tv, "port", VIDAA_PORT),
            )
            left = int(status.get("access_expires_in") or 0)
            if status.get("refresh_valid") and 0 <= left < 2 * 86400:
                if tv.refresh_token(timeout=timeout):
                    logger.info("VIDAA token yangilandi: %s (qoldi %s soat)", tv.host, left // 3600)
    except Exception as e:
        logger.debug("VIDAA proactive refresh: %s", e)
    return True


def _ensure_connected(tv, timeout: float = 10.0) -> bool:
    if getattr(tv, "_connected", False):
        return True
    return _connect_ready(tv, timeout=timeout)


def _install_pin_listener(tv) -> "threading.Event":
    """PIN so'rovini MQTT dan ushlash (Toshiba bo'sh \"\" javob yuboradi)."""
    import json
    import threading

    done = threading.Event()
    client = getattr(tv, "_client", None)
    if client is None:
        return done

    prev_handler = client.on_message

    def _on_message(mqtt_client, userdata, msg):
        topic = getattr(msg, "topic", "") or ""
        raw = ""
        try:
            raw = msg.payload.decode("utf-8", errors="ignore")
        except Exception:
            pass

        auth_topic_hit = (
            topic.endswith("/ui_service/data/authentication")
            or topic.endswith("/ui_service/data/authenticationcode")
        )
        auth_broadcast = False
        if "broadcast/ui_service/state" in topic and raw:
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    auth_broadcast = payload.get("statetype") in (
                        "authentication",
                        "authenticationcode",
                    )
            except Exception:
                pass

        if auth_topic_hit or auth_broadcast:
            stripped = raw.strip().strip('"')
            if auth_broadcast or not stripped or stripped in ("null", "{}", '""'):
                tv._auth_required = True  # noqa: SLF001
                done.set()
                if tv.on_auth_required:
                    try:
                        tv.on_auth_required()
                    except Exception:
                        pass

        if prev_handler:
            prev_handler(mqtt_client, userdata, msg)

    client.on_message = _on_message
    tv._pin_listener_prev = prev_handler  # noqa: SLF001
    return done


def _restore_pin_listener(tv) -> None:
    client = getattr(tv, "_client", None)
    prev = getattr(tv, "_pin_listener_prev", None)
    if client is not None and prev is not None:
        try:
            client.on_message = prev
        except Exception:
            pass


def _go_home_for_pin(tv) -> None:
    """Live TV ustida PIN ko'pincha chiqmaydi — avval Home/launcher."""
    try:
        if not getattr(tv, "_connected", False):
            return
        tv.send_key("KEY_HOME")
        deadline = time.time() + 5.0
        while time.time() < deadline:
            state = getattr(tv, "_state", None) or {}
            if state.get("statetype") == "remote_launcher":
                return
            time.sleep(0.35)
        tv.send_key("KEY_HOME")
        time.sleep(1.2)
    except Exception as e:
        logger.debug("VIDAA Home yuborilmadi: %s", e)


def _wait_pin_dialog(tv, timeout: float = 12.0) -> bool:
    if tv.needs_authentication():
        return True
    pin_event = _install_pin_listener(tv)
    try:
        return pin_event.wait(timeout=max(1.0, timeout)) or tv.needs_authentication()
    finally:
        _restore_pin_listener(tv)


def _trigger_pin(tv) -> bool:
    """PIN oynasini ochish: listener → Home → vidaa_app_connect."""
    from vidaa.topics import TOPIC_VIDAA_CONNECT, get_topic

    if tv.needs_authentication():
        return True

    pin_event = _install_pin_listener(tv)
    try:
        _go_home_for_pin(tv)
        if not getattr(tv, "_connected", False):
            if not tv.connect(auto_auth=False, timeout=12):
                return False

        topic = get_topic(TOPIC_VIDAA_CONNECT, tv.client_id)
        payload = {
            "app_version": 2,
            "connect_result": 0,
            "device_type": "Mobile App",
        }

        for attempt in range(4):
            if not getattr(tv, "_connected", False):
                tv.connect(auto_auth=False, timeout=10)
            try:
                tv._publish(topic, payload)  # noqa: SLF001
            except Exception as e:
                logger.debug("vidaa_app_connect publish: %s", e)
            try:
                tv.start_pairing()
            except Exception as e:
                logger.debug("start_pairing urinish %s: %s", attempt + 1, e)

            if pin_event.wait(timeout=15.0) or tv.needs_authentication():
                return True
            time.sleep(1.0)

        return tv.needs_authentication()
    finally:
        pass  # listener pair() authenticate tugaguncha faol qoladi


def pair(host: str, mac: str, pin_provider: Optional[Callable[[], str]] = None, brand: str = "") -> bool:
    """TV ekranida PIN chiqarib, pin_provider bergan PIN bilan pairing qiladi."""
    try:
        tv = _client(host, mac, brand)
    except ImportError:
        return False
    try:
        if not tv.connect(auto_auth=False, timeout=15):
            logger.warning("VIDAA pairing connect xato: %s", host)
            return False
        if not _trigger_pin(tv):
            logger.warning(
                "VIDAA PIN oynasi ochilmadi: %s (TV Home ekranidami? Remote control yoqilganmi?)",
                host,
            )
            return False
        pin = (pin_provider() if pin_provider else "").strip()
        if not pin:
            logger.warning("VIDAA PIN kiritilmadi: %s", host)
            return False
        if not getattr(tv, "_connected", False):
            tv.connect(auto_auth=False, timeout=10)
        return bool(tv.authenticate(pin, timeout=20))
    except Exception as e:
        logger.warning("VIDAA pairing xato %s: %s", host, e)
        return False
    finally:
        _restore_pin_listener(tv)
        try:
            tv.disconnect()
        except Exception:
            pass


def _run(host: str, mac: str, fn: Callable, brand: str = "") -> bool:
    try:
        tv = _client(host, mac, brand)
    except ImportError:
        return False
    try:
        if not _connect_ready(tv, timeout=12.0):
            return False
        return bool(fn(tv))
    except Exception as e:
        logger.warning("VIDAA buyruq xato %s: %s", host, e)
        return False
    finally:
        try:
            tv.disconnect()
        except Exception:
            pass


def _safe_wake_if_fake_sleep(host: str, mac: str, brand: str = "") -> bool:
    def _wake(tv) -> bool:
        state = tv.get_state(timeout=3.0)
        if state and state.get("statetype") == "fake_sleep_0":
            return bool(tv.send_key("KEY_POWER"))
        return True

    return _run(host, mac, _wake, brand)


def power_on(host: str, mac: str, *, wait_s: float = 45.0, brand: str = "") -> bool:
    host = (host or "").split(":", 1)[0].strip()
    if not mac:
        logger.warning("VIDAA START: MAC yo'q — Wake-on-LAN ishlamaydi (%s)", host)
    if mac:
        wake(mac, host)
    if not wait_until_online(host, timeout_s=wait_s):
        logger.warning("VIDAA START: TV online bo'lmadi: %s", host)
        return False
    _safe_wake_if_fake_sleep(host, mac, brand)
    return True


def power_off(host: str, mac: str = "", brand: str = "") -> bool:
    host = (host or "").split(":", 1)[0].strip()
    if not port_open(host, timeout=1.2):
        return True

    def _off(tv) -> bool:
        if tv.power_off():
            return True
        if not port_open(host, timeout=0.8):
            return True
        ok = bool(tv.send_key("KEY_POWER"))
        if ok and port_open(host, timeout=1.5):
            try:
                tv.power_off()
            except Exception:
                pass
        return ok

    return _run(host, mac, _off, brand)


def _source_candidates(tv, hdmi_input: int) -> list[dict[str, str]]:
    hdmi_input = max(1, min(4, int(hdmi_input or 1)))
    candidates: list[dict[str, str]] = [
        {"sourceid": str(2 + hdmi_input), "sourcename": f"HDMI{hdmi_input}"},
    ]

    def add(sourceid, sourcename) -> None:
        sid = str(sourceid or "").strip()
        sname = str(sourcename or "").strip().replace(" ", "")
        if not sid:
            return
        item = {"sourceid": sid}
        if sname:
            item["sourcename"] = sname
        if item not in candidates:
            candidates.insert(0, item)

    try:
        raw_sources = tv.get_sources(timeout=6.0) or []
        if isinstance(raw_sources, dict):
            sources = raw_sources.get("source_list") or raw_sources.get("sources") or []
        else:
            sources = raw_sources
        for src in sources:
            if not isinstance(src, dict):
                continue
            text = " ".join(str(v) for v in src.values()).lower()
            compact = text.replace(" ", "").replace("_", "").replace("-", "")
            if "hdmi" not in compact:
                continue
            sourceid = src.get("sourceid") or src.get("sourceId") or src.get("id")
            sourcename = src.get("sourcename") or src.get("displayname") or src.get("name")
            signal = str(src.get("is_signal", src.get("signal", ""))).lower() in ("1", "true", "yes", "on")
            if f"hdmi{hdmi_input}" in compact:
                add(sourceid, sourcename or f"HDMI{hdmi_input}")
            elif signal:
                add(sourceid, sourcename)
    except Exception as e:
        logger.debug("VIDAA source list xato: %s", e)
    return candidates


def set_source(host: str, mac: str, hdmi_input: int, brand: str = "") -> bool:
    hdmi_input = max(1, min(4, int(hdmi_input or 1)))

    def _set(tv) -> bool:
        ok = False
        candidates = _source_candidates(tv, hdmi_input)
        from vidaa.topics import TOPIC_SET_SOURCE, get_topic

        topic = get_topic(TOPIC_SET_SOURCE, tv.client_id)
        for delay in (2.0, 4.0, 7.0, 10.0):
            time.sleep(delay)
            for payload in candidates:
                ok = bool(tv._publish(topic, payload)) or ok
                ok = bool(tv._publish(topic, {"sourceid": payload["sourceid"]})) or ok
        return ok

    return _run(host, mac, _set, brand)


def set_volume(host: str, mac: str, level: int, brand: str = "") -> bool:
    level = max(0, min(100, int(level)))
    if not port_open(host, timeout=1.0):
        return False
    return _run(host, mac, lambda tv: tv.set_volume(level, check_state=False), brand)


def send_key(host: str, mac: str, key: str, brand: str = "") -> bool:
    return _run(host, mac, lambda tv: tv.send_key(key), brand)
