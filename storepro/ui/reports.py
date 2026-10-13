from datetime import date
from tkinter import filedialog
import customtkinter as ctk
from .forms import Page,Field,Table,button
from ..reports import Reports
from ..exports import export_rows
from ..money import formatted

TYPES={'المبيعات':'sales','حسب المنتج (قبل المرتجعات)':'by_product','حسب الكاشير (قبل المرتجعات)':'by_user','المرتجعات':'returns','المشتريات':'purchases','المنتجات':'products','نقص المخزون':'low_stock','حركة المخزون':'stock','الخزنة':'cash','الورديات':'shifts','الأرصدة':'balances','كشف الحسابات':'ledger','سجل التعديلات':'audit'}


class ReportsPage(Page):
    def __init__(self,parent,app):
        super().__init__(parent,app,'التقارير والتصدير')
        self.service=Reports(app.db); self.rows=[]; self.table=None
        self.start=Field(self.toolbar,'من YYYY-MM-DD',date.today().replace(day=1).isoformat())
        self.end=Field(self.toolbar,'إلى YYYY-MM-DD',date.today().isoformat())
        self.kind=Field(self.toolbar,'التقرير',choices=list(TYPES))
        button(self.toolbar,'عرض',self.refresh); button(self.toolbar,'تصدير CSV / Excel / PDF',self.export)
        self.summary=ctk.CTkLabel(self,text='',font=('Tahoma',15)); self.summary.pack(fill='x',padx=10,pady=5)
        ctk.CTkLabel(self,text='ملفات التصدير الخام: مبالغ بوحدة القروش وكميات بألف جزء. الصافي والأرباح أدناه يحتسبان المرتجعات حسب تاريخها.',font=('Tahoma',12)).pack()
        self.refresh()
    def refresh(self):
        report=self.service.summary(self.start.get(),self.end.get())
        self.summary.configure(text=f"بيع: {formatted(report['sales'])} | مرتجعات: {formatted(report['refunds'])} | صافي بدون ضريبة: {formatted(report['net_sales'])} | ضريبة: {formatted(report['tax'])} | ربح معلوم التكلفة: {formatted(report['profit'])} | فواتير قديمة تكلفة مجهولة: {report['historical_unknown_cost']}")
        self.rows=self.service.table(TYPES[self.kind.get()],self.start.get(),self.end.get())
        if self.table: self.table.destroy()
        columns=list(self.rows[0]) if self.rows else ['لا توجد بيانات']
        self.table=Table(self,columns); self.table.pack(fill='both',expand=True,padx=10,pady=10); self.table.load(self.rows)
    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.xlsx',filetypes=[('Excel','*.xlsx'),('CSV','*.csv'),('PDF','*.pdf')])
        if path: export_rows(self.rows,path); self.notify('تم تصدير التقرير')
