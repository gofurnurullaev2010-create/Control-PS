"""Smena hisoboti: matn formatlari + tovar PDF."""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
import database as db
logger = logging.getLogger(__name__)
def _money(v: float) -> str:
    return f'{float(v or 0):,.0f}'.replace(',', ' ')
def _fmt_dt(iso: str) -> str:
    text = str(iso or '').strip()
    if not text:
        return '—'
    else:
        try:
            if 'T' in text:
                return datetime.fromisoformat(text).strftime('%d.%m.%Y %H:%M:%S')
            else:
                return text
        except ValueError:
            if 'T' in text:
                d, t = text.split('T', 1)
                return f"{d.replace('-', '.')} {t[:8]}"
            else:
                return text
def enrich_shift_report(report: dict[str, Any]) -> dict[str, Any]:
    """Kassa jabıw oldidan to\'liq smena snapshot."""
    out = dict(report or {})
    start = str(out.get('period_start') or '')
    end = str(out.get('period_end') or datetime.now().isoformat(timespec='seconds'))
    session_total = float(out.get('session_total') or 0)
    drink_total = float(out.get('drink_total') or 0)
    market_total = float(out.get('market_total') or 0)
    joystick_total = float(out.get('joystick_total') or 0)
    buyurtma_total = float(out.get('buyurtma_total') or 0)
    goods_total = drink_total + market_total
    total = float(out.get('total') or session_total + drink_total + market_total + joystick_total)
    expense_total = float(out.get('expense_total') or 0)
    debt_total = float(out.get('debt_total') or 0)
    debt_paid = float(out.get('debt_paid_total') or 0)
    closing = float(out.get('closing_amount') or 0)
    try:
        click_total = float(out.get('click_total'))
    except (TypeError, ValueError):
        click_total = None
    if click_total is None:
        try:
            click_total = float(db.click_total_between(start, end))
        except Exception:
            click_total = 0.0
    click_total = float(click_total or 0)
    closing_with_click = closing + click_total
    expenses = db.list_expenses_between(start, end)
    debtors = db.list_debtors_between(start, end)
    debt_payments = db.list_debt_payments_between(start, end)
    products = db.product_stock_report_between(start, end)
    goods_profit = float(sum((float(p.get('profit') or 0) for p in products)))
    client_count = int(db.count_closed_sessions_between(start, end))
    avg_payment = total / client_count if client_count > 0 else 0.0
    cash_expenses = [x for x in expenses if str(x.get('wallet') or 'cash').strip().lower() not in ['safe', 'ceyf', 'сейф']]
    expense_total = float(sum((float(x.get('amount') or 0) for x in cash_expenses)))
    expense_safe_total = float(sum((float(x.get('amount') or 0) for x in expenses if str(x.get('wallet') or '').strip().lower() in ['safe', 'ceyf', 'сейф'])))
    debt_total = float(sum((float(x.get('amount') or 0) for x in debtors)))
    debt_paid = float(sum((float(x.get('amount') or 0) for x in debt_payments)))
    expected, cash_diff = db.compute_cash_diff(total, expense_total, debt_total, debt_paid, closing_with_click)
    net_profit = session_total + joystick_total + goods_profit - expense_total - expense_safe_total
    out.update({'session_total': session_total, 'drink_total': drink_total, 'market_total': market_total, 'joystick_total': joystick_total, 'buyurtma_total': buyurtma_total, 'goods_total': goods_total, 'total': total, 'expense_total': expense_total, 'expense_safe_total': expense_safe_total, 'debt_total': debt_total, 'debt_paid_total': debt_paid, 'click_total': click_total, 'closing_with_click': closing_with_click, 'expected_amount': expected, 'cash_diff': cash_diff, 'expenses': expenses, 'debtors': debtors, 'debt_payments': debt_payments, 'products': products, 'client_count': client_count, 'avg_payment': avg_payment, 'goods_profit': goods_profit, 'net_profit': net_profit})
    out['summary_text'] = format_shift_summary(out)
    out['details_text'] = format_shift_details(out)
    return out
def format_shift_summary(report: dict[str, Any]) -> str:
    """2-rasm: KASSA SMENASI JAWILDI."""
    r = report
    name = str(r.get('operator_name') or '—')
    open_t = _fmt_dt(str(r.get('period_start') or ''))
    close_t = _fmt_dt(str(r.get('period_end') or r.get('saved_time') or ''))
    ps = float(r.get('session_total') or 0) + float(r.get('joystick_total') or 0)
    goods = float(r.get('goods_total') or 0)
    goods_profit = float(r.get('goods_profit') or 0)
    clients = int(r.get('client_count') or 0)
    avg = float(r.get('avg_payment') or 0)
    expense = float(r.get('expense_total') or 0)
    debt = float(r.get('debt_total') or 0)
    paid = float(r.get('debt_paid_total') or 0)
    total = float(r.get('total') or 0)
    net = float(r.get('net_profit') or 0)
    closing = float(r.get('closing_amount') or 0)
    click = float(r.get('click_total') or 0)
    closing_with_click = float(r.get('closing_with_click') or closing + click)
    expected = float(r.get('expected_amount') or 0)
    diff = float(r.get('cash_diff') or 0)
    ceyf = float(r.get('expense_safe_total') or 0)
    lines = [
        '📊 KASSA SMENASI JAWILDI!',
        '',
        f'👤 Kassir: {name}',
        f'⏰ Ashiliw waqti: {open_t}',
        f'🏁 Jabiliw waqti: {close_t}',
        '',
        '🎮',
        f"┣ 💰 Tu'sim: {_money(ps)} swm",
        f"┗ 📈 O'rtasha to'lem: {_money(avg)} swm",
        '',
        '📦',
        f"┣ 📩 Tu'sim: {_money(goods)} swm",
        f'┗ 💎 Sap payda: {_money(goods_profit)} swm',
        '',
        '💎',
        f'┣ 👥 Klientler sani: {clients}',
        f'┣ 💸 Qarejetler: {_money(expense)} swm',
        f'┣ 🔐 Ceyf qarejet: {_money(ceyf)} swm',
        f'┣ 📝 Qarizdarlar: {_money(debt)} swm',
        f"┣ ♻️ Qarzin to'legenler: {_money(paid)} swm",
        f"┣ 📊 Uliwmaliq tu'sim: {_money(total)} swm",
        f'┗ 💹 Sap payda: {_money(net)} swm',
        '',
        "🏁 KASSA JABILG'ANDAG'I SUMMA:",
        f"Jawilg'andag'i summa:{int(closing)}",
        f'click:{int(click)}',
        f"Jawilg'andag'i summa:(Jawilg'andag'i summa+click)={int(closing_with_click)}",
        '',
        '🧮 Kutilgen kassa esabi:',
        "(Tu'simler + Qarzin to'legenler) - (Qa'rejet + Qarizdar)",
        f'({_money(total)} + {_money(paid)}) - ({_money(expense)} + {_money(debt)}) = {_money(expected)}',
        '',
        f'⚠️ Kassa parqi:{_money(diff)}',
    ]
    return '\n'.join(lines)
def format_shift_details(report: dict[str, Any]) -> str:
    """3-rasm: SMENA DETALLARI."""
    expenses = list(report.get('expenses') or [])
    debtors = list(report.get('debtors') or [])
    payments = list(report.get('debt_payments') or [])
    cash_expenses = [x for x in expenses if str(x.get('wallet') or 'cash').strip().lower() not in ['safe', 'ceyf', 'сейф']]
    safe_expenses = [x for x in expenses if str(x.get('wallet') or '').strip().lower() in ['safe', 'ceyf', 'сейф']]
    exp_sum = float(report.get('expense_total') or sum((float(x.get('amount') or 0) for x in cash_expenses)))
    safe_sum = float(report.get('expense_safe_total') or sum((float(x.get('amount') or 0) for x in safe_expenses)))
    debt_sum = float(report.get('debt_total') or sum((float(x.get('amount') or 0) for x in debtors)))
    paid_sum = float(report.get('debt_paid_total') or sum((float(x.get('amount') or 0) for x in payments)))
    lines = ['SMENA DETALLARI', '']
    lines.append(f'💸 Qarejetler (kassa): ({_money(exp_sum)} swm)')
    if cash_expenses:
        for i, e in enumerate(cash_expenses, 1):
            label = str(e.get('expense_type') or e.get('note') or '—').strip() or '—'
            lines.append(f"{i}. {label} - {_money(float(e.get('amount') or 0))} swm")
    else:
        lines.append('—')
    lines.append('')
    lines.append(f'🔐 Qarejetler (Ceyf): ({_money(safe_sum)} swm)')
    if safe_expenses:
        for i, e in enumerate(safe_expenses, 1):
            label = str(e.get('expense_type') or e.get('note') or '—').strip() or '—'
            lines.append(f"{i}. {label} - {_money(float(e.get('amount') or 0))} swm")
    else:
        lines.append('—')
    lines.append('')
    lines.append(f'📝 Qarizdarlar: ({_money(debt_sum)} swm)')
    if debtors:
        for i, d in enumerate(debtors, 1):
            lines.append(f"{i}. {str(d.get('client_name') or '—')} - {_money(float(d.get('amount') or 0))} swm")
    else:
        lines.append('—')
    lines.append('')
    lines.append(f'♻️ Qarzin to\'legenler: ({_money(paid_sum)} swm)')
    if payments:
        for i, d in enumerate(payments, 1):
            lines.append(f"{i}. {str(d.get('client_name') or '—')} - {_money(float(d.get('amount') or 0))} swm")
    else:
        lines.append('—')
    return '\n'.join(lines)
def _pdf_escape(text: str) -> str:
    return str(text).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
def generate_product_pdf(report: dict[str, Any], dest: Optional[Path]=None) -> Path:
    """Tovar_Otchyot_DD.MM.YYYY.pdf — namunadagi jadval + smena yakuni."""
    products = list(report.get('products') or [])
    day = str(report.get('business_day') or datetime.now().date().isoformat())
    try:
        day_label = datetime.fromisoformat(day).strftime('%d.%m.%Y')
    except ValueError:
        day_label = day.replace('-', '.')
    if dest is None:
        out_dir = Path(db.DB_PATH).resolve().parent / 'reports'
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f'Tovar_Otchyot_{day_label}.pdf'
    else:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _generate_product_pdf_qt(report, products, day_label, dest)
    except Exception as e:
        logger.warning('Qt PDF: %s — oddiy PDF', e)
        return _generate_product_pdf_simple(report, products, day_label, dest)
def _html(value: Any) -> str:
    return str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def _generate_product_pdf_qt(report: dict[str, Any], products: List[dict[str, Any]], day_label: str, dest: Path) -> Path:
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
    from PyQt6.QtPrintSupport import QPrinter
    from PyQt6.QtWidgets import QApplication
    if QApplication.instance() is None:
        raise RuntimeError('QApplication yo\'q')
    else:
        rows_html = []
        tot_was = tot_left = tot_sold = 0
        tot_sum = 0.0
        for i, p in enumerate(products, 1):
            was = int(p.get('was') or 0)
            left = int(p.get('left') or 0)
            sold = int(p.get('sold') or 0)
            sm = float(p.get('sum') or 0)
            tot_was += was
            tot_left += left
            tot_sold += sold
            tot_sum += sm
            rows_html.append(f"<tr><td>{i}</td><td>{_html(p.get('name'))}</td><td align=\'right\'>{_money(float(p.get('price') or 0))}</td><td align=\'right\'>{was}</td><td align=\'right\'>{left}</td><td align=\'right\'>{sold}</td><td align=\'right\'>{_money(sm)}</td></tr>")
        ps = float(report.get('session_total') or 0) + float(report.get('joystick_total') or 0)
        html = f"\n    <html><head><meta charset=\"utf-8\"/></head>\n    <body style=\"font-family: Segoe UI, Arial; font-size: 10pt;\">\n    <h2>ОТЧЁТ ПО ТОВАРАМ &nbsp; {day_label}</h2>\n    <table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" border=\"1\"\n           style=\"border-collapse:collapse; font-size:9pt;\">\n      <tr style=\"background:#F3F4F6; font-weight:bold;\">\n        <td>№</td><td>Продукт</td><td>Цена</td><td>Было</td>\n        <td>Осталось</td><td>Продано</td><td>Сумма</td>\n      </tr>\n      {''.join(rows_html)}\n      <tr style=\"font-weight:bold;\">\n        <td colspan=\"3\">ИТОГО</td>\n        <td align=\"right\">{tot_was}</td><td align=\"right\">{tot_left}</td>\n        <td align=\"right\">{tot_sold}</td><td align=\"right\">{_money(tot_sum)}</td>\n      </tr>\n    </table>\n    <h3>ИТОГОВЫЙ ОТЧЁТ СМЕНЫ</h3>\n    <table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" style=\"font-size:10pt;\">\n      <tr><td>PlayStation (выручка)</td><td align=\"right\">{_money(ps)} сум</td></tr>\n      <tr><td>Товары (выручка)</td><td align=\"right\">{_money(float(report.get('goods_total') or 0))} сум</td></tr>\n      <tr><td>Товары (прибыль)</td><td align=\"right\">{_money(float(report.get('goods_profit') or 0))} сум</td></tr>\n      <tr><td>Общая выручка</td><td align=\"right\">{_money(float(report.get('total') or 0))} сум</td></tr>\n      <tr><td>Расходы</td><td align=\"right\">{_money(float(report.get('expense_total') or 0))} сум</td></tr>\n      <tr><td>Долги (выдано)</td><td align=\"right\">{_money(float(report.get('debt_total') or 0))} сум</td></tr>\n      <tr><td>Долги (погашено)</td><td align=\"right\">{_money(float(report.get('debt_paid_total') or 0))} сум</td></tr>\n      <tr><td>Касса при закрытии</td><td align=\"right\">{_money(float(report.get('closing_amount') or 0))} сум</td></tr>\n      <tr style=\"font-weight:bold;\"><td>ЧИСТАЯ ПРИБЫЛЬ</td>\n          <td align=\"right\">{_money(float(report.get('net_profit') or 0))} сум</td></tr>\n    </table>\n    </body></html>\n    "
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(dest))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        doc = QTextDocument()
        doc.setHtml(html)
        doc.print(printer)
        return dest
def _generate_product_pdf_simple(report: dict[str, Any], products: List[dict[str, Any]], day_label: str, dest: Path) -> Path:
    lines_txt = []
    lines_txt.append(f'OTCHYOT PO TOVARAM    {day_label}')
    lines_txt.append('No  Produkt                      Cena     Bylo  Qoldiq  Sotildi    Summa')
    lines_txt.append('------------------------------------------------------------------------------')
    tot_was = tot_left = tot_sold = 0
    tot_sum = 0.0
    for i, p in enumerate(products, 1):
        name = str(p.get('name') or '')[:28]
        price = float(p.get('price') or 0)
        was = int(p.get('was') or 0)
        left = int(p.get('left') or 0)
        sold = int(p.get('sold') or 0)
        sm = float(p.get('sum') or 0)
        tot_was += was
        tot_left += left
        tot_sold += sold
        tot_sum += sm
        lines_txt.append(f'{i:<3} {name:<28} {_money(price):>8} {was:>6} {left:>6} {sold:>7} {_money(sm):>9}')
    lines_txt.append('------------------------------------------------------------------------------')
    lines_txt.append(f"ITOGO{'':>32}{tot_was:>6} {tot_left:>6} {tot_sold:>7} {_money(tot_sum):>9}")
    lines_txt.append('')
    lines_txt.append('ITOGIVIY OTCHYOT SMENY')
    lines_txt.append(f"PlayStation (vyruchka)     {_money(float(report.get('session_total') or 0) + float(report.get('joystick_total') or 0))} sum")
    lines_txt.append(f"Tovary (vyruchka)         {_money(float(report.get('goods_total') or 0))} sum")
    lines_txt.append(f"Tovary (pribyl)           {_money(float(report.get('goods_profit') or 0))} sum")
    lines_txt.append(f"Obshaya vyruchka          {_money(float(report.get('total') or 0))} sum")
    lines_txt.append(f"Rashody                   {_money(float(report.get('expense_total') or 0))} sum")
    lines_txt.append(f"Dolgi (vydano)            {_money(float(report.get('debt_total') or 0))} sum")
    lines_txt.append(f"Dolgi (pogasheno)         {_money(float(report.get('debt_paid_total') or 0))} sum")
    lines_txt.append(f"Kassa pri zakrytii        {_money(float(report.get('closing_amount') or 0))} sum")
    lines_txt.append(f"CHISTAYA PRIBYL           {_money(float(report.get('net_profit') or 0))} sum")
    content_lines = []
    y = 800
    for row in lines_txt:
        content_lines.append(f'BT /F1 9 Tf 40 {y} Td ({_pdf_escape(row)}) Tj ET')
        y -= 12
        if y < 40:
            y = 40
    stream = '\n'.join(content_lines).encode('latin-1', errors='replace')
    objects = []
    objects.append(b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n')
    objects.append(b'2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n')
    objects.append(b'3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n')
    objects.append(f'4 0 obj<< /Length {len(stream)} >>stream\n'.encode('ascii') + stream + b'\nendstream\nendobj\n')
    objects.append(b'5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n')
    out = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    out.extend(b'0000000000 65535 f \n')
    for off in offsets[1:]:
        out.extend(f'{off:010d} 00000 n \n'.encode('ascii'))
    out.extend(f'trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode('ascii'))
    dest.write_bytes(bytes(out))
    return dest