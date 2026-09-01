# Control PS — agent uchun qoidalar

## GitHub bilan sinxronlash

Bu loyiha `https://github.com/gofurnurullaev2010-create/Control-PS` ga ulangan.

Kodga o'zgartirish kiritib, uni tekshirib bo'lgach — **har safar** o'zgarishni
GitHubga yuboring:

```
git add -A
git commit -m "<o'zgarish haqida qisqa izoh>"
git push origin main
```

Yoki tayyor skriptni ishga tushiring: `github_sync.bat`

Git `C:\Program Files\Git\cmd` da, agar `git` topilmasa PATH ga qo'shing.

## Nima commit qilinmaydi

`.gitignore` da ko'rsatilgan fayllar hech qachon commit qilinmasin:
baza (`*.db`), loglar, `license.key`, parol hashlari, `dist/`, `build/`,
`_extract/`, mijoz va operator ma'lumotlari.

Yangi fayl qo'shilganda avval maxfiy ma'lumot yo'qligini tekshiring.

## Dastur haqida

- Python 3.11 + PyQt6 **6.11.0** (versiya qat'iy — `requirements.txt` ga qarang).
  Boshqa Qt versiyasida QtMultimedia ffmpeg kutubxonalari tushmaydi va
  zakaz ovozlari ishlamay qoladi.
- `.exe` yig'ish: `py -3.11 build_exe.py`
- Dastur avval `.exe` dan dekompilyatsiya qilib tiklangan. Shubhali joyni
  tekshirish uchun asl `v197` bayt-kodi bilan solishtiring —
  `_extract/audit_consts.py` shu ish uchun yozilgan.
