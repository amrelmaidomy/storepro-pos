import csv
import html
import os
import sys
import webbrowser
from pathlib import Path
from .money import formatted,quantity_text


def resource(relative):
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/relative


def safe_cell(value):
    text=str(value) if value is not None else ''
    return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text


def export_rows(rows,path):
    path=Path(path); headers=list(rows[0]) if rows else ['لا توجد بيانات']
    if path.suffix.lower()=='.csv':
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f); writer.writerow(headers)
            writer.writerows([[safe_cell(r.get(k)) for k in headers] for r in rows])
    elif path.suffix.lower()=='.xlsx':
        from openpyxl import Workbook
        book=Workbook(); sheet=book.active; sheet.title='StorePro'; sheet.sheet_view.rightToLeft=True
        sheet.append(headers)
        for row in rows: sheet.append([safe_cell(row.get(k)) for k in headers])
        sheet.freeze_panes='A2'; book.save(path)
    elif path.suffix.lower()=='.pdf':
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import arabic_reshaper
        from bidi.algorithm import get_display
        pdfmetrics.registerFont(TTFont('StoreProArabic',str(resource('assets/fonts/DejaVuSans.ttf'))))
        c=canvas.Canvas(str(path)); c.setTitle('StorePro Report'); y=800
        for row in [dict(zip(headers,headers))]+rows:
            for k in headers:
                line=f'{k}: {row.get(k,"")}'
                # Wrap long fields to prevent silent clipping outside the PDF page.
                for chunk in [line[i:i+72] for i in range(0,len(line),72)] or ['']:
                    if y<55: c.showPage(); y=800
                    c.setFont('StoreProArabic',10)
                    c.drawRightString(550,y,get_display(arabic_reshaper.reshape(chunk))); y-=17
            y-=12
        c.save()
    else: raise ValueError('اختر CSV أو XLSX أو PDF')
    return path


def render_receipt(sale,path,width_mm=80,store_name='StorePro',currency='ج.م'):
    if width_mm not in (58,80): raise ValueError('عرض الإيصال 58 أو 80 مم')
    esc=lambda x: html.escape(str(x))
    items=''.join(f'<tr><td>{esc(i["name"])}</td><td>{quantity_text(i["qty"])}</td><td>{formatted(i["price"])}</td><td>{formatted(i["net_total"]+i["tax"])}</td></tr>' for i in sale['items'])
    lines=[('قبل الخصم',sale['subtotal']),('الخصم',sale['discount']),('الضريبة',sale['tax']),('الإجمالي',sale['total']),('النقد المدفوع',sale['cash']),('بطاقة',sale['card']),('آجل',sale['credit']),('الباقي',sale['change_amount'])]
    totals=''.join(f'<p>{label}: {formatted(value)} {esc(currency)}</p>' for label,value in lines)
    page=f'''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>{esc(sale['number'])}</title><style>@page{{size:{width_mm}mm auto;margin:3mm}}body{{width:{width_mm-6}mm;font-family:Tahoma,Arial;font-size:12px}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px dashed #888;padding:4px}}@media print{{button{{display:none}}}}</style><h2>{esc(store_name)}</h2><p>{esc(sale['number'])} — {esc(sale['date'])}</p><table><tr><th>الصنف</th><th>الكمية</th><th>السعر</th><th>القيمة</th></tr>{items}</table>{totals}<button onclick="window.print()">طباعة</button><p>احتفظ بالإيصال للمرتجعات</p></html>'''
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(page,encoding='utf-8')
    return path


def preview_receipt(path):
    webbrowser.open(Path(path).resolve().as_uri())


def print_receipt(path):
    # Browser print dialog supports installed Windows printers and explicit selection.
    preview_receipt(path)
