"""5 ta QR ni bitta PNG varaqqa yig\'ish."""
from __future__ import annotations
import io
from pathlib import Path
from typing import Iterable, Sequence
def make_qr_sheet_png(urls: Sequence[str], labels: Iterable[str] | None=None, out_path: Path | str | None=None) -> bytes:
    """5 ta QR + yozuv — bitta oq fonli PNG."""
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    items = list(urls)
    labs = list(labels) if labels is not None else [f'ЗАКАЗ #{i + 1}' for i in range(len(items))]
    while len(labs) < len(items):
        labs.append(f'#{len(labs) + 1}')
    cell_w, cell_h = (360, 420)
    pad = 24
    cols = min(5, max(1, len(items)))
    rows = (len(items) + cols - 1) // cols
    title_h = 70
    W = pad * 2 + cols * cell_w
    H = pad * 2 + title_h + rows * cell_h
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    try:
        font_title = ImageFont.truetype('arial.ttf', 28)
        font_lab = ImageFont.truetype('arial.ttf', 20)
        font_small = ImageFont.truetype('arial.ttf', 12)
    except Exception:
        font_title = ImageFont.load_default()
        font_lab = font_title
        font_small = font_title
    title = 'Eagle Playstation — QR ЗАКАЗ (1–5)'
    draw.text((pad, 18), title, fill=(15, 23, 42), font=font_title)
    for i, url in enumerate(items):
        r, c = divmod(i, cols)
        x0 = pad + c * cell_w
        y0 = pad + title_h + r * cell_h
        qr = qrcode.QRCode(version=None, box_size=7, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        img = img.resize((280, 280))
        canvas.paste(img, (x0 + 40, y0 + 36))
        lab = labs[i]
        draw.text((x0 + 40, y0 + 8), lab, fill=(15, 23, 42), font=font_lab)
        short = url if len(url) < 42 else url[:39] + '...'
        draw.text((x0 + 20, y0 + 330), short, fill=(100, 100, 100), font=font_small)
    buf = io.BytesIO()
    canvas.save(buf, format='PNG')
    data = buf.getvalue()
    if out_path is not None:
        Path(out_path).write_bytes(data)
    return data