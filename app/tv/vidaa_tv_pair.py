from __future__ import annotations
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hisense / Toshiba VIDAA TV ni Control PS bilan bir martalik PIN pairing qilish."""

import sys

import vidaa_platform


def main() -> int:
    print("============================================")
    print("  Hisense / Toshiba VIDAA — Control PS pairing")
    print("============================================")
    print("TV yoqilgan va tarmoqda bo'lishi kerak.")
    print("Port 36669 ochiq bo'lishi kerak.")
    print()
    print("Muhim:")
    print("  - Live TV (kanal) emas, Home/launcher ekrani kerak.")
    print("  - Skript o'zi Home ga o'tkazishga harakat qiladi.")
    print("  - PIN ~60 soniya ichida kiritilishi kerak.")
    print()

    host = input("TV IP (masalan 192.168.100.140): ").strip()
    if not host:
        print("IP kiritilmadi.")
        return 1

    mac = input("TV MAC (AA:BB:CC:DD:EE:FF): ").strip()
    if not mac:
        print("MAC kiritilmadi. Wake-on-LAN uchun MAC majburiy.")
        return 1

    brand = input("Brand (hisense/toshiba/tos, Enter=auto): ").strip().lower()

    if not vidaa_platform.port_open(host, timeout=3.0):
        print(f"XATO: {host}:36669 portiga ulanib bo'lmadi.")
        print("TV yoqilganmi, LAN/WiFi bir tarmoqdami, Remote/Mobile control yoqilganmi?")
        return 1

    info = vidaa_platform._detect_vidaa_info(host)
    if info:
        print(
            f"UPnP: brand={info.get('brand') or '?'}, mac={info.get('mac') or '?'}"
        )

    print()
    print("Home ga o'tiladi va PIN so'rovi yuboriladi...")
    print("TV ekranida 4 xonali PIN chiqishi kerak.")
    print("(Agar chiqmasa: TV ni Home ga qo'ying, qayta ishga tushiring.)")
    print()

    pin_shown = {"ok": False}

    def _pin_provider() -> str:
        pin_shown["ok"] = True
        print("PIN oynasi ochildi (TV tasdiqladi).")
        return input("TV ekranidagi 4 xonali PIN: ").strip()

    if vidaa_platform.pair(host, mac, _pin_provider, brand):
        print()
        print("TAYYOR: VIDAA pairing saqlandi (vidaa_tokens.json).")
        print("Endi Control PS da brand=toshiba/tos qilib START/STOP ishlatishingiz mumkin.")
        return 0

    print()
    if not pin_shown["ok"]:
        print("XATO: TV PIN oynasini ochmadi.")
        print("Tekshiring:")
        print("  1) TV Home (launcher) ekranida bo'lsin — kanal/Live TV emas")
        print("  2) Sozlamalar → Tarmoq → Mobil ilova / Remote control → YOQILGAN")
        print("     (Toshiba: Settings → Network → Mobile App Connection)")
        print("  3) TV ni o'chirib-yoqing, keyin qayta pairing qiling")
        print("  4) Toshiba uchun brand: tos yoki toshiba")
        print("  5) Boshqa telefondan TV Remote ilova ulangan bo'lsa — o'chirib qo'ying")
    else:
        print("XATO: pairing yakunlanmadi. PIN noto'g'ri yoki vaqti o'tgan bo'lishi mumkin.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
