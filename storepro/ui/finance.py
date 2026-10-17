from tkinter import messagebox
import customtkinter as ctk
from .forms import Label,Button,Page,Field,Table,Dialog,button
from ..sales import Sales
from ..purchases import Purchases
from ..shifts import Shifts
from ..money import parse_money,parse_quantity,parse_quantity_zero,formatted
from ..backup import Backup


class HistoryPage(Page):
    def __init__(self,parent,app,purchase=False):
        super().__init__(parent,app,'سجل المشتريات والمرتجعات' if purchase else 'سجل المبيعات والمرتجعات')
        self.purchase=purchase
        button(self.toolbar,'تفاصيل المحدد',self.detail); button(self.toolbar,'مرتجع من المحدد',self.refund)
        if not purchase: button(self.toolbar,'إعادة طباعة',lambda:app.receipt(self.table.selected()['id']))
        button(self.toolbar,'تحديث',self.refresh)
        self.table=Table(self,['id','number' if not purchase else 'supplier_id','date','total_text','actor']); self.table.pack(fill='both',expand=True,padx=10,pady=10)
        self.refresh()
    def refresh(self):
        self.app.auth.require(self.app.actor,'manage' if self.purchase else 'view')
        table='purchases' if self.purchase else 'sales'
        rows=self.app.db.rows(f'select * from {table} order by id desc')
        self.table.load([dict(r,total_text=formatted(r['total'])) for r in rows])
    def invoice(self):
        self.app.auth.require(self.app.actor,'manage' if self.purchase else 'view')
        service=Purchases(self.app.db) if self.purchase else Sales(self.app.db)
        return service,service.detail(self.table.selected()['id'])
    def detail(self):
        _,invoice=self.invoice(); w=ctk.CTkToplevel(self); w.title('بنود الفاتورة'); w.geometry('950x500')
        table=Table(w,['id','name','qty_text','returned_text','price_text']); table.pack(fill='both',expand=True)
        table.load([dict(i,qty_text=i['qty']/1000,returned_text=i['returned']/1000,price_text=formatted(i['price'])) for i in invoice['items']])
    def refund(self):
        service,invoice=self.invoice()
        fields={str(i['id']):(f"{i['name']} — متاح {(i['qty']-i['returned'])/1000:g}",'0') for i in invoice['items'] if i['qty']>i['returned']}
        if not fields: raise ValueError('لا توجد كميات متاحة للمرتجع')
        fields['method']=('الاسترداد بعد خصم الدين','نقدي',['نقدي','بطاقة'])
        def save(v):
            items=[]
            for key,value in v.items():
                if key=='method': continue
                if parse_quantity_zero(value)==0: continue
                items.append(dict(item_id=int(key),qty=parse_quantity(value)))
            method='cash' if v['method']=='نقدي' else 'card'
            if self.purchase: service.return_items(self.app.actor,invoice['id'],items,method)
            else: service.refund(self.app.actor,invoice['id'],items,method)
            self.refresh()
        Dialog(self,'مرتجع جزئي / كامل',fields,save)


class FinancePage(Page):
    def __init__(self,parent,app):
        super().__init__(parent,app,'الوردية والخزنة')
        self.service=Shifts(app.db)
        button(self.toolbar,'فتح وردية',self.open); button(self.toolbar,'إغلاق وردية',self.close)
        button(self.toolbar,'إيراد / مصروف',self.movement); button(self.toolbar,'تحديث',self.refresh)
        self.status=Label(self,text='',font=('Tahoma',18)); self.status.pack(pady=15)
        self.table=Table(self,['id','date','kind','amount_text','description','reference']); self.table.pack(fill='both',expand=True,padx=10,pady=10)
        self.refresh()
    def refresh(self):
        self.app.auth.require(self.app.actor,'shift')
        shift=self.service.current()
        self.status.configure(text=f"وردية {shift['id']} — النقد المتوقع {formatted(shift['expected'])}" if shift else 'لا توجد وردية مفتوحة')
        self.table.load([dict(r,amount_text=formatted(r['amount'])) for r in self.app.db.rows('select * from cash_moves order by id desc')])
    def open(self):
        def save(v): self.service.open(self.app.actor,parse_money(v['amount'])); self.refresh()
        Dialog(self,'فتح وردية',{'amount':('النقد الافتتاحي','0')},save)
    def close(self):
        def save(v):
            result=self.service.close(self.app.actor,parse_money(v['amount'])); self.refresh()
            if self.app.settings.get('auto_backup')=='1': Backup(self.app.db).automatic(self.app.data_dir/'backups',int(self.app.settings.get('backup_keep')))
            self.notify(f"تم الإغلاق — فرق النقدية {formatted(result['difference'])}")
        Dialog(self,'إغلاق وردية',{'amount':('النقد الفعلي المعدود','0')},save)
    def movement(self):
        def save(v):
            self.service.movement(self.app.actor,'income' if v['kind']=='إيراد' else 'expense',parse_money(v['amount']),v['reason']); self.refresh()
        Dialog(self,'حركة خزنة',{'kind':('النوع','مصروف',['إيراد','مصروف']),'amount':('المبلغ','0'),'reason':('الوصف','')},save)
