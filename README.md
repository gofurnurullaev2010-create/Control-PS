# Control PS — Eagle Playstation

PlayStation klubi uchun kassa va boshqaruv dasturi (Windows, Python 3.11 + PyQt6).

## Imkoniyatlar

- Stollar boshqaruvi: seans boshlash/to'xtatish, taymer, jostik hisobi, bronlash
- BAR / Market: ichimlik va mahsulot sotish, ombor qoldig'i
- Kassa: smena yakuni, qarizdarlar, qa'rejetler, CLICK to'lovlari, kassa parqi
- Hisobotlar: kunlik hisobot, operator xisoboti, PDF tovar otchyoti
- Telegram bot: kassa jabılg'anda yakun, detallar va PDF avtomatik yuboriladi
- TV boshqaruvi: Samsung (Tizen), LG (webOS), Hisense/Toshiba (VIDAA), Android TV (ADB)
- QR ZAKAZ: stoldan telefon orqali chaqiruv

## Talablar

- Windows 10/11 (64-bit)
- Python 3.11 (aynan shu versiya — `.exe` shu bilan yig'iladi)

> **Muhim:** `PyQt6` va `PyQt6-Qt6` versiyalari `requirements.txt` da qat'iy belgilangan (6.11.0).
> Boshqa versiya bilan yig'ilsa QtMultimedia'ning ffmpeg kutubxonalari tushmay qoladi va
> zakaz ovozlari ishlamaydi.

## O'rnatish

```bat
py -3.11 -m pip install -r requirements.txt
```

## Ishga tushirish (dasturchi rejimi)

```bat
py -3.11 main.py
```

yoki `ControlPS_ishga_dev.bat` faylini ishga tushiring.

## `.exe` yig'ish

```bat
py -3.11 build_exe.py
```

Natija `dist\ControlPS_v<raqam>.exe` sifatida saqlanadi. Versiya raqami
`dist` papkasidagi oxirgi build asosida avtomat oshadi.

## Loyiha tuzilishi

```
main.py              — kirish nuqtasi
app/
  auth/              — litsenziya, parol, HWID
  core/              — yo'llar, runtime yordamchilari
  db/database.py     — SQLite bilan ishlash, barcha hisob-kitoblar
  services/          — Telegram, smena hisoboti, QR zakaz, Google zakaz
  tv/                — TV boshqaruvi (Tizen / webOS / VIDAA / ADB)
  ui/                — oynalar, panellar, dialoglar, vidjetlar
build_exe.py         — PyInstaller bilan yig'ish skripti
```

Ildizdagi `database.py`, `tv_handler.py` kabi fayllar — eski nomlar bilan
moslik uchun qo'yilgan yo'naltiruvchi modullar.

## Ma'lumotlar bazasi

`control_ps.db` (SQLite) dastur yonida saqlanadi. Unda mijoz va moliyaviy
ma'lumotlar, shuningdek Telegram bot tokeni bo'lgani uchun bu fayl GitHubga
**yuklanmaydi** (`.gitignore` da).

## Telegram botni ulash

1. Telegramda **@BotFather** ga `/newbot` yuboring va token oling
2. Dasturda **Admin → TELEGRAM** bo'limini oching
3. Tokenni va Chat ID(lar)ni kiriting (bir nechtasi vergul bilan)
4. **Saqlash** → **Test xabar** bosib tekshiring

Har bir akkount avval botga `/start` yozishi kerak, aks holda xabar yetib bormaydi.
