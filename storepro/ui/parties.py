import customtkinter as ctk
from .forms import Page,Table,Dialog,button
from ..parties import Parties
from ..money import parse_money,formatted


class PartiesPage(Page):
    def __init__(self,parent,app,kind):
        super().__init__(parent,app,'العملاء والآجل' if kind=='customer' else 'الموردون والمستحقات')
        self.kind=kind; self.service=Parties(app.db)
        button(self.toolbar,'إضافة',lambda:self.edit()); button(self.toolbar,'تعديل',lambda:self.edit(self.table.selected()))
        button(self.toolbar,'تحصيل / سداد',self.pay); button(self.toolbar,'كشف الحساب',self.ledger); button(self.toolbar,'تحديث',self.refresh)
        self.table=Table(self,['id','name','phone','address','balance_text','active']); self.table.pack(fill='both',expand=True,padx=10,pady=10)
        self.refresh()
    def refresh(self):
        self.app.auth.require(self.app.actor,'manage')
        self.table.load([dict(p,balance_text=formatted(p['balance'])) for p in self.service.list(self.kind)])
    def edit(self,p=None):
        p=p or {}
        def save(v):
            self.service.save(self.app.actor,self.kind,dict(v,id=p.get('id'),active=v['active']=='نشط')); self.refresh()
        fields={'name':('الاسم',p.get('name','')),'phone':('الهاتف',p.get('phone','')),'address':('العنوان',p.get('address','')),'active':('الحالة','نشط' if p.get('active',1) else 'معطل',['نشط','معطل'])}
        Dialog(self,'بيانات الحساب',fields,save)
    def pay(self):
        p=self.table.selected()
        def save(v):
            self.service.pay(self.app.actor,self.kind,p['id'],parse_money(v['amount']),'cash' if v['method']=='نقدي' else 'card'); self.refresh()
        Dialog(self,'سداد '+p['name'],{'amount':('المبلغ',formatted(max(0,p['balance']))),'method':('الطريقة','نقدي',['نقدي','بطاقة'])},save)
    def ledger(self):
        p=self.table.selected(); w=ctk.CTkToplevel(self); w.title('كشف '+p['name']); w.geometry('900x500')
        table=Table(w,['id','date','kind','amount_text','reference']); table.pack(fill='both',expand=True)
        rows=self.app.db.rows('select * from party_moves where party_id=? order by id desc',(p['id'],))
        table.load([dict(r,amount_text=formatted(r['amount'])) for r in rows])
