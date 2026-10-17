"""Product browsing and an always-visible invoice for fast offline selling."""
from uuid import uuid4
import customtkinter as ctk
from . import theme as t
from .forms import Label,Button,Field,Dialog,guarded,rtl
from ..auth import Auth
from ..catalog import Catalog
from ..parties import Parties
from ..sales import Sales
from ..shifts import Shifts
from ..money import amount,formatted,parse_money,parse_quantity,integer,quantity_text


class CartPage(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color=t.BG,corner_radius=0)
        self.app=app; self.catalog=Catalog(app.db); self._search_job=None; self._layout_job=None
        self._columns=0; self.category=None; self.limit=60; self.product_cards={}; self.payment_dialog=None
        self.draft=app.sale_draft
        self.cart=self.draft.setdefault('cart',{})
        self.request_id=self.draft.setdefault('request_id',str(uuid4()))
        self.last_invoice=self.draft.get('last_invoice')
        self.currency=app.settings.get('currency')
        for pid,item in self.cart.items():
            current=app.db.rows('select * from products where id=?',(pid,))
            if current:
                item.update(name=current[0]['name'],price=current[0]['price'],unit=current[0]['unit'])
        self.grid_columnconfigure(0,weight=0,minsize=342)
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,fg_color='transparent'); header.grid(row=0,column=0,columnspan=2,sticky='ew',padx=22,pady=(20,14))
        titles=ctk.CTkFrame(header,fg_color='transparent'); titles.pack(side='right')
        Label(titles,text='نقطة البيع',font=('Tahoma',25,'bold')).pack(anchor='e')
        Label(titles,text='اختار المنتج، جهّز الفاتورة، وخلّص البيع.',text_color=t.MUTED,font=('Tahoma',12)).pack(anchor='e',pady=(3,0))
        self.shift_badge=Button(header,text='',height=34,width=155,fg_color=t.TINT,text_color=t.PRIMARY,hover_color='#D2ECE9',command=guarded(self.shift_action))
        self.shift_badge.pack(side='left',padx=(0,10))
        self.invoice_panel=ctk.CTkFrame(self,fg_color=t.SURFACE,corner_radius=18,border_width=1,border_color=t.BORDER,width=342)
        self.invoice_panel.grid(row=1,column=0,sticky='nsew',padx=(18,8),pady=(0,12))
        self.invoice_panel.grid_columnconfigure(0,weight=1); self.invoice_panel.grid_rowconfigure(2,weight=1)
        titlebar=ctk.CTkFrame(self.invoice_panel,fg_color='transparent'); titlebar.grid(row=0,column=0,sticky='ew',padx=18,pady=(18,4))
        Label(titlebar,text='الفاتورة الحالية',font=('Tahoma',18,'bold')).pack(side='right')
        self.count_label=Label(titlebar,text='0 أصناف',text_color=t.MUTED,font=('Tahoma',11)); self.count_label.pack(side='left')
        hint=ctk.CTkFrame(self.invoice_panel,fg_color='transparent'); hint.grid(row=1,column=0,sticky='ew',padx=18,pady=(0,8))
        Label(hint,text='عدّل الكمية بـ + و − أو اكتبها واضغط Enter',font=('Tahoma',10),text_color=t.MUTED).pack(anchor='e')
        self.cart_area=ctk.CTkScrollableFrame(self.invoice_panel,fg_color='transparent',corner_radius=0)
        self.cart_area.grid(row=2,column=0,sticky='nsew',padx=10,pady=4)
        self.cart_area.grid_columnconfigure(0,weight=1)
        self.summary=ctk.CTkFrame(self.invoice_panel,fg_color='transparent')
        self.summary.grid(row=3,column=0,sticky='ew',padx=18,pady=(10,16))
        self.details_toggle=Button(self.summary,text='تفاصيل إضافية  +',height=30,fg_color='transparent',text_color=t.MUTED,hover_color=t.BG,anchor='e',command=self.toggle_details)
        self.details_toggle.pack(fill='x')
        self.details=ctk.CTkFrame(self.summary,fg_color=t.BG,corner_radius=10)
        self.details_open=False
        self.party_map={'بدون عميل':None}
        self.party_map.update({f"{p['id']} — {p['name']}":p['id'] for p in Parties(app.db).list('customer') if p['active']})
        self.party=Field(self.details,'العميل',self.draft.get('party','بدون عميل'),list(self.party_map))
        self.discount=Field(self.details,'الخصم',self.draft.get('discount','0'))
        self.tax=Field(self.details,'ضريبة %',self.draft.get('tax',app.settings.get('tax_rate')))
        for field in (self.party,self.discount,self.tax):
            # Compact form fits the fixed-width invoice; values retain their logical Arabic text.
            for child in field.frame.winfo_children():
                if isinstance(child,Label): child.configure(width=65,font=('Tahoma',11))
            field.widget.configure(width=140,height=30,font=('Tahoma',12))
        self.discount.widget.bind('<KeyRelease>',lambda e:self.schedule_totals())
        self.tax.widget.bind('<KeyRelease>',lambda e:self.schedule_totals())
        self.subtotal_label=Label(self.summary,text='',font=('Tahoma',12),text_color=t.MUTED,anchor='e'); self.subtotal_label.pack(fill='x',pady=(12,0))
        self.adjustments_label=Label(self.summary,text='',font=('Tahoma',11),text_color=t.MUTED,anchor='e'); self.adjustments_label.pack(fill='x')
        totalrow=ctk.CTkFrame(self.summary,fg_color='transparent'); totalrow.pack(fill='x',pady=(10,12))
        Label(totalrow,text='الإجمالي',font=('Tahoma',16,'bold')).pack(side='right')
        self.total_label=Label(totalrow,text='0.00',font=('Tahoma',28,'bold'),text_color=t.PRIMARY); self.total_label.pack(side='left')
        self.pay_button=Button(self.summary,text='الدفع  ←',height=48,font=('Tahoma',17,'bold'),command=guarded(self.open_payment))
        self.pay_button.pack(fill='x')
        self.invoice_actions=ctk.CTkFrame(self.summary,fg_color='transparent'); self.invoice_actions.pack(fill='x',pady=(8,0))
        Button(self.invoice_actions,text='تفريغ الفاتورة',height=28,width=115,fg_color='transparent',text_color=t.MUTED,hover_color=t.BG,command=guarded(self.confirm_clear)).pack(side='right')
        self.print_button=Button(self.invoice_actions,text='آخر إيصال',height=28,width=105,fg_color='transparent',text_color=t.PRIMARY,hover_color=t.TINT,command=guarded(self.print_last))
        self.print_button.pack(side='left')
        self.product_area=ctk.CTkFrame(self,fg_color='transparent')
        self.product_area.grid(row=1,column=1,sticky='nsew',padx=(8,22),pady=(0,12))
        self.product_area.grid_columnconfigure(0,weight=1); self.product_area.grid_rowconfigure(3,weight=1)
        searchbox=ctk.CTkFrame(self.product_area,fg_color=t.SURFACE,corner_radius=13,border_width=1,border_color=t.BORDER)
        searchbox.grid(row=0,column=0,sticky='ew',pady=(0,12))
        self.query=Field(searchbox,'بحث سريع','')
        for child in self.query.frame.winfo_children():
            if isinstance(child,Label): child.configure(width=72,font=('Tahoma',12),text_color=t.MUTED)
        self.query.frame.pack_configure(padx=12,pady=8)
        self.query.widget.configure(height=38,border_width=0,placeholder_text=rtl('ابحث باسم المنتج أو امسح الباركود…'),font=('Tahoma',14))
        self.query.widget.bind('<KeyRelease>',self.queue_search)
        self.query.widget.bind('<Return>',guarded(lambda e:self.search(True)))
        self.category_bar=ctk.CTkScrollableFrame(self.product_area,orientation='horizontal',height=42,fg_color='transparent',scrollbar_button_color=t.BORDER)
        self.category_bar.grid(row=1,column=0,sticky='ew',pady=(0,8))
        info=ctk.CTkFrame(self.product_area,fg_color='transparent'); info.grid(row=2,column=0,sticky='ew',pady=(0,8))
        self.result_label=Label(info,text='',font=('Tahoma',12),text_color=t.MUTED); self.result_label.pack(side='right')
        Button(info,text='تحديث',width=62,height=26,fg_color='transparent',text_color=t.PRIMARY,hover_color=t.TINT,command=guarded(self.reload_catalog)).pack(side='left')
        self.products=ctk.CTkScrollableFrame(self.product_area,fg_color='transparent',corner_radius=0)
        self.products.grid(row=3,column=0,sticky='nsew')
        self.more_button=Button(self.product_area,text='عرض المزيد',height=30,command=guarded(self.show_more))
        self.toast_label=Label(self,text='',font=('Tahoma',12),height=25,anchor='e',text_color=t.PRIMARY)
        self.toast_label.grid(row=2,column=0,columnspan=2,sticky='ew',padx=22,pady=(0,8))
        self.products.bind('<Configure>',self.queue_layout)
        self._totals_job=None
        self.reload_catalog(); self.refresh()
        self.bind_id=app.bind('<F9>',guarded(lambda e:self.open_payment()))
        self.query.widget.focus_set()

    def reload_catalog(self):
        self.app.auth.require(self.app.actor,'sell')
        self.catalog_rows=self.catalog.search()
        categories=sorted({p['category'] or 'غير مصنف' for p in self.catalog_rows})
        for w in self.category_bar.winfo_children(): w.destroy()
        self.category_buttons={}
        for index,(name,category) in enumerate([('الكل',None)]+[(x,x) for x in categories]):
            b=Button(self.category_bar,text=name,width=max(64,len(name)*8+24),height=32,corner_radius=16,font=('Tahoma',12),command=guarded(lambda c=category:self.select_category(c)))
            b.grid(row=0,column=len(categories)-index,padx=4,pady=2)
            self.category_buttons[category]=b
        if self.category not in categories: self.category=None
        self.search()

    def select_category(self,category):
        self.category=category; self.limit=60; self.search()

    def queue_search(self,event=None):
        if event and event.keysym in ('Return','KP_Enter'): return
        if self._search_job: self.after_cancel(self._search_job)
        self._search_job=self.after(180,guarded(self.search))

    def queue_layout(self,event=None):
        if self._layout_job: self.after_cancel(self._layout_job)
        self._layout_job=self.after(70,self.layout_products)

    def layout_products(self):
        self._layout_job=None
        required=sum(b.winfo_reqwidth()+8 for b in self.category_buttons.values())
        if required<=self.category_bar._parent_canvas.winfo_width(): self.category_bar._scrollbar.grid_remove()
        else: self.category_bar._scrollbar.grid()
        columns=max(1,min(4,int(self.products.winfo_width()//(190*self._get_widget_scaling()))))
        if columns!=self._columns:
            self._columns=columns; self.render_products()

    def search(self,auto=False):
        self.app.auth.require(self.app.actor,'sell')
        if self._search_job:
            self.after_cancel(self._search_job); self._search_job=None
        rows=self.catalog.search(self.query.get())
        if auto:
            exact=[p for p in rows if p['barcode']==self.query.get()]
            if not exact: exact=[p for p in rows if str(p['id'])==self.query.get()]
            if exact or len(rows)==1:
                self.quick_add((exact or rows)[0]['id'])
                self.query.set(''); rows=self.catalog.search()
        self.filtered_rows=[p for p in rows if self.category is None or (p['category'] or 'غير مصنف')==self.category]
        self.render_products()
        for category,b in self.category_buttons.items():
            b.configure(fg_color=t.PRIMARY if category==self.category else t.SURFACE,text_color='white' if category==self.category else t.MUTED,hover_color=t.HOVER if category==self.category else t.TINT)

    def render_products(self):
        for w in self.products.winfo_children(): w.destroy()
        self.product_cards={}
        columns=self._columns or 2
        for col in range(4): self.products.grid_columnconfigure(col,weight=1 if col<columns else 0,uniform='cards' if col<columns else '')
        visible=self.filtered_rows[:self.limit]
        if not visible:
            panel=ctk.CTkFrame(self.products,fg_color=t.SURFACE,corner_radius=16)
            panel.grid(row=0,column=0,columnspan=columns,sticky='ew',padx=5,pady=20)
            Label(panel,text='ابدأ بإضافة منتجاتك' if not self.catalog_rows else 'مفيش منتجات مطابقة',font=('Tahoma',18,'bold')).pack(padx=20,pady=(28,8))
            Label(panel,text='أضف المنتجات والمخزون من صفحة المنتجات.' if not self.catalog_rows else 'جرّب اسمًا تاني أو اختار تصنيف الكل.',font=('Tahoma',12),text_color=t.MUTED).pack(padx=16,pady=(0,24))
            if not self.catalog_rows and self.app.db.rows('select role from users where id=?',(self.app.actor,))[0]['role']=='Admin':
                Button(panel,text='إضافة منتج',command=guarded(lambda:self.app.show('products'))).pack(pady=(0,20))
        colors=[('#E7F3EF','#27735F'),('#EEF0FA','#6765A9'),('#FFF2DF','#AD7E36'),('#E6F2F8','#3B7893')]
        for index,p in enumerate(visible):
            card=ctk.CTkFrame(self.products,width=170,fg_color=t.SURFACE,corner_radius=15,border_width=1,border_color=t.BORDER)
            card.grid(row=index//columns,column=columns-1-index%columns,sticky='nsew',padx=5,pady=6)
            self.product_cards[p['id']]=card
            shade,ink=colors[index%len(colors)]
            top=ctk.CTkFrame(card,fg_color=shade,width=1,height=68,corner_radius=11); top.pack(fill='x',padx=10,pady=(10,6)); top.pack_propagate(False)
            Label(top,text=p['name'][:1],font=('Tahoma',30,'bold'),text_color=ink).pack(expand=True)
            Label(card,text=p['name'],font=('Tahoma',14,'bold'),anchor='e',wraplength=145,height=38).pack(fill='x',padx=12)
            Label(card,text=p['category'] or 'غير مصنف',font=('Tahoma',10),anchor='e',text_color=t.MUTED).pack(fill='x',padx=12)
            Label(card,text=f"{formatted(p['price'])} {self.currency}",font=('Tahoma',17,'bold'),text_color=t.PRIMARY,anchor='e').pack(fill='x',padx=12,pady=(4,0))
            available=f"متاح {quantity_text(p['stock'])} {p['unit']}" if p['stock'] else 'نفدت الكمية'
            Label(card,text=available,font=('Tahoma',10),text_color=t.MUTED if p['stock'] else t.DANGER,anchor='e').pack(fill='x',padx=12)
            action=guarded(lambda pid=p['id']:self.quick_add(pid))
            Button(card,text='أضف للفاتورة  +',height=30,font=('Tahoma',11),fg_color=t.TINT,text_color=t.PRIMARY,hover_color='#D2ECE9',state='normal' if p['stock']>0 else 'disabled',command=action).pack(fill='x',padx=10,pady=(6,10))
            targets=[card,top]+[w for w in card.winfo_children() if isinstance(w,Label)]+[w for w in top.winfo_children() if isinstance(w,Label)]
            for target in targets: target.bind('<Button-1>',lambda e,callback=action:callback())
        self.result_label.configure(text=f'المنتجات · {len(self.filtered_rows)}')
        if len(self.filtered_rows)>self.limit: self.more_button.grid(row=4,column=0,sticky='ew',pady=8)
        else: self.more_button.grid_remove()

    def show_more(self):
        self.limit+=60; self.render_products()

    def quick_add(self,pid):
        rows=self.app.db.rows('select stock,active from products where id=?',(pid,))
        if not rows or not rows[0]['active']: raise ValueError('المنتج غير متاح')
        remaining=rows[0]['stock']-self.cart.get(pid,{}).get('qty',0)
        if remaining<=0: raise ValueError('كل الكمية المتاحة موجودة في الفاتورة')
        self.add_product(pid,min(1000,remaining))

    def add_product(self,pid,qty,price=None):
        self.app.auth.require(self.app.actor,'sell'); integer(qty,1)
        found=self.app.db.rows('select * from products where id=? and active=1',(pid,))
        if not found: raise ValueError('المنتج غير متاح')
        p=found[0]; total=self.cart.get(pid,{}).get('qty',0)+qty
        if total>p['stock']: raise ValueError('الكمية المطلوبة أكبر من المخزون المتاح')
        self.cart[pid]=dict(product_id=pid,name=p['name'],qty=total,price=p['price'],unit=p['unit'])
        self.refresh(); self.toast(f"تمت إضافة {quantity_text(qty)} {p['unit']} · {p['name']}")

    def set_quantity(self,pid,text):
        self.app.auth.require(self.app.actor,'sell'); qty=parse_quantity(text)
        p=self.app.db.rows('select stock,active from products where id=?',(pid,))
        if not p or not p[0]['active'] or qty>p[0]['stock']: raise ValueError('الكمية أكبر من المخزون أو المنتج غير متاح')
        self.cart[pid]['qty']=qty; self.refresh()

    def change_quantity(self,pid,delta):
        qty=self.cart[pid]['qty']+delta
        if qty<=0: self.remove_product(pid)
        else: self.set_quantity(pid,quantity_text(qty))

    def remove_product(self,pid):
        self.cart.pop(pid,None); self.refresh()

    def totals(self):
        subtotal=sum(amount(i['price'],i['qty']) for i in self.cart.values())
        discount=parse_money(self.discount.get()); rate=parse_money(self.tax.get())
        if discount>subtotal or rate>10000: raise ValueError('الخصم أو الضريبة غير صحيح')
        return subtotal-discount+((subtotal-discount)*rate+5000)//10000

    def refresh(self):
        for w in self.cart_area.winfo_children(): w.destroy()
        self.count_label.configure(text=f'{len(self.cart)} أصناف')
        if not self.cart:
            self.empty_cart=ctk.CTkFrame(self.cart_area,fg_color='transparent')
            self.empty_cart.grid(row=0,column=0,sticky='ew',pady=35)
            Label(self.empty_cart,text='＋',font=('Tahoma',45),text_color='#BCCFD5').pack(pady=(10,12))
            Label(self.empty_cart,text='فاتورتك لسه فاضية',font=('Tahoma',16,'bold')).pack(pady=5)
            Label(self.empty_cart,text='اضغط على أي منتج لإضافته هنا\nأو امسح الباركود لبيع أسرع.',font=('Tahoma',12),text_color=t.MUTED,justify='center').pack(pady=8)
        for index,(pid,item) in enumerate(self.cart.items()):
            row=ctk.CTkFrame(self.cart_area,fg_color=t.BG,corner_radius=12)
            row.grid(row=index,column=0,sticky='ew',pady=4,padx=2)
            Label(row,text=item['name'],font=('Tahoma',13,'bold'),anchor='e',wraplength=210).pack(fill='x',padx=12,pady=(10,2))
            Label(row,text=f"{formatted(item['price'])} {self.currency} / {item.get('unit','وحدة')}",font=('Tahoma',10),text_color=t.MUTED,anchor='e').pack(fill='x',padx=12)
            controls=ctk.CTkFrame(row,fg_color='transparent'); controls.pack(fill='x',padx=10,pady=(7,10))
            Button(controls,text='+',width=28,height=28,fg_color=t.SURFACE,text_color=t.PRIMARY,hover_color=t.TINT,command=guarded(lambda p=pid:self.change_quantity(p,1000))).pack(side='right')
            entry=ctk.CTkEntry(controls,width=54,height=28,justify='center',font=('Tahoma',12),border_width=0)
            entry.insert(0,quantity_text(item['qty'])); entry.pack(side='right',padx=3)
            entry.bind('<Return>',guarded(lambda e,p=pid,w=entry:self.set_quantity(p,w.get())))
            Button(controls,text='−',width=28,height=28,fg_color=t.SURFACE,text_color=t.PRIMARY,hover_color=t.TINT,command=guarded(lambda p=pid:self.change_quantity(p,-1000))).pack(side='right')
            Button(controls,text='×',width=26,height=28,fg_color='transparent',text_color=t.MUTED,hover_color='#FCEBEB',command=guarded(lambda p=pid:self.remove_product(p))).pack(side='left')
            Label(controls,text=formatted(amount(item['price'],item['qty'])),font=('Tahoma',15,'bold')).pack(side='left',padx=4)
        self.update_totals(); self.save_draft(); self.refresh_shift()
        self.print_button.configure(state='normal' if self.last_invoice else 'disabled')

    def update_totals(self):
        try:
            total=self.totals(); subtotal=sum(amount(i['price'],i['qty']) for i in self.cart.values())
            self.total_label.configure(text=formatted(total),text_color=t.PRIMARY)
            self.subtotal_label.configure(text=f'قيمة المنتجات  {formatted(subtotal)} {self.currency}')
            self.adjustments_label.configure(text=f"خصم {self.discount.get()} · ضريبة {self.tax.get()}%" if parse_money(self.discount.get()) or parse_money(self.tax.get()) else 'السعر النهائي · '+self.currency)
            self.pay_button.configure(state='normal' if self.cart else 'disabled')
        except ValueError as e:
            self.total_label.configure(text='—',text_color=t.DANGER); self.adjustments_label.configure(text=str(e)); self.pay_button.configure(state='disabled')
        self.save_draft()

    def schedule_totals(self):
        if self._totals_job: self.after_cancel(self._totals_job)
        self._totals_job=self.after(100,self.update_totals)

    def toggle_details(self):
        self.details_open=not self.details_open
        if self.details_open:
            self.details.pack(fill='x',before=self.subtotal_label,pady=(4,0))
            self.details_toggle.configure(text=rtl('تفاصيل إضافية  −'))
        else:
            self.details.pack_forget(); self.details_toggle.configure(text=rtl('تفاصيل إضافية  +'))

    def refresh_shift(self):
        shift=Shifts(self.app.db).current()
        self.shift_badge.configure(text=rtl(f"وردية #{shift['id']} · مفتوحة" if shift else 'افتح وردية وابدأ البيع'))

    def shift_action(self):
        self.app.show('finance')

    def open_payment(self):
        self.app.auth.require(self.app.actor,'sell')
        if not self.cart: raise ValueError('أضف منتجًا للفاتورة أولًا')
        self.totals()
        if self.payment_dialog and self.payment_dialog.winfo_exists():
            self.payment_dialog.focus_force(); return self.payment_dialog
        from .payment import PaymentDialog
        self.payment_dialog=PaymentDialog(self)
        return self.payment_dialog

    def complete(self,payments):
        sid=Sales(self.app.db).checkout(self.app.actor,list(self.cart.values()),parse_money(self.discount.get()),parse_money(self.tax.get()),payments,self.party_map.get(self.party.get()),self.request_id)
        self.last_invoice=sid; self.clear(); self.reload_catalog(); self.toast(f'تم البيع بنجاح · فاتورة #{sid}')
        return sid

    def clear(self):
        self.cart.clear(); self.request_id=str(uuid4()); self.discount.set('0'); self.party.set('بدون عميل'); self.refresh()

    def confirm_clear(self):
        from tkinter import messagebox
        if self.cart and messagebox.askyesno('تفريغ الفاتورة','تمسح كل الأصناف من الفاتورة الحالية؟'): self.clear()

    def print_last(self):
        if self.last_invoice: self.app.receipt(self.last_invoice)

    def save_draft(self):
        self.draft.update(cart=self.cart,request_id=self.request_id,discount=self.discount.get(),tax=self.tax.get(),party=self.party.get(),last_invoice=self.last_invoice)

    def toast(self,text): self.toast_label.configure(text=text)

    def destroy(self):
        if self.app.actor: self.save_draft()
        for job in (self._search_job,self._layout_job,self._totals_job):
            if job:
                try: self.after_cancel(job)
                except Exception: pass
        if self.payment_dialog and self.payment_dialog.winfo_exists(): self.payment_dialog.destroy()
        self.app.unbind('<F9>',self.bind_id)
        super().destroy()
