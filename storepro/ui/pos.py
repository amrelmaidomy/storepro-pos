from uuid import uuid4
import customtkinter as ctk
from .forms import Page,Field,Table,button,guarded,Dialog
from ..catalog import Catalog
from ..sales import Sales
from ..purchases import Purchases
from ..parties import Parties
from ..money import parse_money,parse_quantity,integer,amount,formatted
from ..exports import render_receipt,preview_receipt


class CartPage(Page):
    def __init__(self,parent,app,purchase=False):
        super().__init__(parent,app,'فاتورة شراء' if purchase else 'نقطة البيع')
        self.purchase=purchase; self.cart={}; self.request_id=str(uuid4()); self.catalog=Catalog(app.db)
        searchbar=ctk.CTkFrame(self); searchbar.pack(fill='x',padx=10)
        self.query=Field(searchbar,'بحث باركود / اسم / رقم')
        buttons=ctk.CTkFrame(searchbar); buttons.pack(fill='x')
        button(buttons,'بحث',self.search)
        self.quantity=Field(searchbar,'الكمية','1')
        self.price=Field(searchbar,'سعر الشراء للوحدة','0') if purchase else None
        button(buttons,'إضافة المحدد للسلة',self.add_selected)
        self.results=Table(self,['id','barcode','name','price','stock']); self.results.pack(fill='x',padx=10,pady=5); self.results.tree.configure(height=3)
        self.results.tree.bind('<Double-1>',guarded(lambda e:self.add_selected()))
        self.query.widget.bind('<Return>',guarded(lambda e:self.search(True)))
        self.table=Table(self,['product_id','name','qty_text','price_text','total_text']); self.table.pack(fill='both',expand=True,padx=10,pady=5)
        edits=ctk.CTkFrame(self); edits.pack(fill='x',padx=10)
        button(edits,'حذف البند',self.remove_selected); button(edits,'تعديل كمية البند',self.edit_quantity); button(edits,'تفريغ السلة',self.clear)
        bottom=ctk.CTkFrame(self); bottom.pack(fill='x',padx=10,pady=5)
        form=ctk.CTkFrame(bottom); form.pack(side='right',fill='both',expand=True)
        kind='supplier' if purchase else 'customer'
        self.party_map={'بدون عميل':None} if not purchase else {}
        self.party_map.update({f"{p['id']} — {p['name']}":p['id'] for p in Parties(app.db).list(kind) if p['active']})
        self.party=Field(form,'المورد' if purchase else 'العميل',choices=list(self.party_map) or ['أضف موردًا أولًا'])
        self.discount=Field(form,'خصم الفاتورة','0') if not purchase else None
        self.tax=Field(form,'ضريبة %',app.settings.get('tax_rate')) if not purchase else None
        pay=ctk.CTkFrame(bottom); pay.pack(side='left',fill='both',expand=True)
        self.cash=Field(pay,'نقدي','0').widget; self.card=Field(pay,'بطاقة','0')
        self.credit=Field(pay,'آجل','0') if not purchase else None
        self.total_label=ctk.CTkLabel(pay,text='الإجمالي: 0.00',font=('Tahoma',20)); self.total_label.pack()
        bar=ctk.CTkFrame(pay); bar.pack(fill='x')
        button(bar,'حساب الإجمالي',self.refresh); button(bar,'نقدي كامل',self.fill_cash)
        button(bar,'حفظ الشراء' if purchase else 'إتمام البيع F9',self.complete_and_notify)
        self.query.widget.focus_set()
        self.bind_id=app.bind('<F9>',guarded(lambda e:self.complete_and_notify()))

    def destroy(self):
        if self.bind_id: self.app.unbind('<F9>',self.bind_id)
        super().destroy()

    def search(self,auto=False):
        rows=self.catalog.search(self.query.get()); self.results.load(rows)
        if auto:
            exact=[r for r in rows if r['barcode']==self.query.get() or str(r['id'])==self.query.get()]
            if exact or len(rows)==1:
                p=(exact or rows)[0]; self.add_product(p['id'],parse_quantity(self.quantity.get()),parse_money(self.price.get()) if self.price else None)
                self.query.set(''); self.query.widget.focus_set()

    def add_selected(self):
        p=self.results.selected()
        self.add_product(p['id'],parse_quantity(self.quantity.get()),parse_money(self.price.get()) if self.price else None)

    def add_product(self,pid,qty,price=None):
        integer(qty,1)
        rows=self.app.db.rows('select * from products where id=? and active=1',(pid,))
        if not rows: raise ValueError('المنتج غير متاح')
        p=rows[0]
        if pid in self.cart:
            self.cart[pid]['qty']+=qty
            if self.purchase: self.cart[pid]['price']=integer(price)
        else: self.cart[pid]=dict(product_id=pid,name=p['name'],qty=qty,price=integer(price) if self.purchase else p['price'])
        self.refresh()

    def totals(self):
        subtotal=sum(amount(i['price'],i['qty']) for i in self.cart.values())
        discount=parse_money(self.discount.get()) if self.discount else 0
        tax=parse_money(self.tax.get()) if self.tax else 0
        if discount>subtotal or tax>10000: raise ValueError('الخصم أو الضريبة غير صحيح')
        return subtotal-discount+((subtotal-discount)*tax+5000)//10000

    def refresh(self):
        self.table.load([dict(i,qty_text=i['qty']/1000,price_text=formatted(i['price']),total_text=formatted(amount(i['price'],i['qty']))) for i in self.cart.values()])
        self.total_label.configure(text='الإجمالي: '+formatted(self.totals())+' '+self.app.settings.get('currency'))

    def fill_cash(self):
        total=self.totals(); self.cash.delete(0,'end'); self.cash.insert(0,formatted(total)); self.card.set('0')
        if self.credit: self.credit.set('0')

    def remove_selected(self):
        del self.cart[self.table.selected()['product_id']]; self.refresh()

    def edit_quantity(self):
        pid=self.table.selected()['product_id']; i=self.cart[pid]
        def save(v):
            i['qty']=parse_quantity(v['qty'])
            if self.purchase: i['price']=parse_money(v['price'])
            self.refresh()
        fields={'qty':('الكمية',str(i['qty']/1000))}
        if self.purchase: fields['price']=('سعر الوحدة',formatted(i['price']))
        Dialog(self,'تعديل البند',fields,save)

    def clear(self):
        self.cart.clear(); self.request_id=str(uuid4())
        if self.discount: self.discount.set('0')
        self.refresh()

    def complete(self):
        payments=dict(cash=parse_money(self.cash.get()),card=parse_money(self.card.get()))
        party=self.party_map.get(self.party.get())
        if self.purchase:
            sid=Purchases(self.app.db).receive(self.app.actor,party,list(self.cart.values()),payments,self.request_id)
        else:
            payments['credit']=parse_money(self.credit.get())
            sid=Sales(self.app.db).checkout(self.app.actor,list(self.cart.values()),parse_money(self.discount.get()),parse_money(self.tax.get()),payments,party,self.request_id)
        self.last_invoice=sid
        self.clear(); self.cash.delete(0,'end'); self.cash.insert(0,'0'); self.card.set('0')
        if self.credit: self.credit.set('0')
        return sid

    def complete_and_notify(self):
        sid=self.complete()
        self.notify(f'تم حفظ الفاتورة رقم {sid}')
        if not self.purchase: self.app.receipt(sid)
