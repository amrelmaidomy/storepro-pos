"""Focused checkout: choose a method, check change, confirm once."""
import logging
import customtkinter as ctk
from . import theme as t
from .forms import Label,Button,Field,guarded,rtl
from ..money import formatted,parse_money
from ..shifts import Shifts


class PaymentDialog(ctk.CTkToplevel):
    def __init__(self,page):
        super().__init__(page)
        self.page=page; self.app=page.app; self.sale_id=None; self._job=None; self._grab_job=None
        self.total=page.totals(); self.change_amount=0; self.needs_shift=Shifts(self.app.db).current() is None
        self.title('إتمام الدفع')
        self.app.update_idletasks()
        x=max(0,self.app.winfo_rootx()+(self.app.winfo_width()-540)//2)
        y=max(0,self.app.winfo_rooty()+(self.app.winfo_height()-700)//2)
        self.geometry(f'540x700+{x}+{y}'); self.minsize(500,620)
        self.configure(fg_color=t.SURFACE); self.transient(self.app)
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        body=ctk.CTkScrollableFrame(self,fg_color=t.SURFACE); body.pack(fill='both',expand=True,padx=20,pady=(16,4))
        Label(body,text='إتمام البيع',font=('Tahoma',22,'bold')).pack(anchor='e',pady=(0,3))
        Label(body,text='اختار طريقة الدفع وراجع الباقي.',font=('Tahoma',12),text_color=t.MUTED).pack(anchor='e')
        totalbox=ctk.CTkFrame(body,fg_color=t.TINT,corner_radius=16); totalbox.pack(fill='x',pady=16)
        Label(totalbox,text='المطلوب دفعه',font=('Tahoma',12),text_color=t.PRIMARY).pack(pady=(12,0))
        Label(totalbox,text=f'{formatted(self.total)} {page.currency}',font=('Tahoma',32,'bold'),text_color=t.PRIMARY).pack(pady=(0,12))
        self.method_bar=ctk.CTkFrame(body,fg_color='transparent'); self.method_bar.pack(fill='x',pady=(0,12))
        admin=self.app.db.rows('select role from users where id=?',(self.app.actor,))[0]['role']=='Admin'
        self.is_admin=admin; self.method_buttons={}
        for index,method in enumerate(['نقدي','بطاقة','مختلط']+(['آجل'] if admin else [])):
            b=Button(self.method_bar,text=method,height=38,width=96,font=('Tahoma',13),command=lambda m=method:self.choose_method(m))
            b.pack(side='right',expand=True,fill='x',padx=3); self.method_buttons[method]=b
        self.fields_panel=ctk.CTkFrame(body,fg_color='transparent'); self.fields_panel.pack(fill='x')
        self.cash=Field(self.fields_panel,'النقد المستلم','0')
        self.card=Field(self.fields_panel,'المدفوع بالبطاقة','0')
        self.credit=Field(self.fields_panel,'المبلغ الآجل','0')
        self.customer=Field(body,'العميل',page.party.get(),list(page.party_map))
        self.change_label=Label(body,text='',font=('Tahoma',19,'bold'),text_color=t.PRIMARY); self.change_label.pack(anchor='e',pady=(14,3))
        self.error=Label(body,text='',font=('Tahoma',11),text_color=t.DANGER,wraplength=450); self.error.pack(fill='x')
        self.shift_panel=ctk.CTkFrame(body,fg_color='#FFF5E5',corner_radius=12)
        Label(self.shift_panel,text='ابدأ الوردية قبل إتمام أول عملية بيع',text_color='#966B22',font=('Tahoma',12)).pack(padx=10,pady=8)
        self.opening=Field(self.shift_panel,'رصيد افتتاحي','0')
        Button(self.shift_panel,text='فتح وردية',height=32,command=guarded(lambda:self.open_shift(self.opening.get()))).pack(pady=(5,10))
        if self.needs_shift: self.shift_panel.pack(fill='x',pady=8)
        self.print_var=ctk.IntVar(value=0)
        ctk.CTkCheckBox(body,text=rtl('فتح الإيصال للطباعة بعد البيع'),variable=self.print_var,font=('Tahoma',12),text_color=t.MUTED,checkbox_width=18,checkbox_height=18,fg_color=t.PRIMARY).pack(anchor='e',pady=12)
        footer=ctk.CTkFrame(self,fg_color=t.SURFACE); footer.pack(fill='x',padx=22,pady=(8,20))
        self.confirm_button=Button(footer,text='تأكيد البيع',height=46,font=('Tahoma',16,'bold'),command=guarded(self.submit))
        self.confirm_button.pack(side='right',fill='x',expand=True,padx=(6,0))
        Button(footer,text='رجوع للفاتورة',height=46,width=135,fg_color=t.BG,text_color=t.MUTED,hover_color=t.BORDER,command=self.destroy).pack(side='left')
        for field in (self.cash,self.card,self.credit): field.widget.bind('<KeyRelease>',lambda e:self.schedule())
        self.choose_method('نقدي')
        self.bind('<Escape>',lambda e:self.destroy())
        self._grab_job=self.after(80,self.activate)

    def activate(self):
        self._grab_job=None
        if self.winfo_exists():
            self.grab_set(); self.focus_force()
            field=self.card if self.method=='بطاقة' else self.credit if self.method=='آجل' else self.cash
            field.widget.focus_set(); field.widget.select_range(0,'end')

    def choose_method(self,method):
        if method not in self.method_buttons: raise ValueError('طريقة الدفع غير متاحة')
        self.method=method
        for f in (self.cash,self.card,self.credit): f.set('0'); f.frame.pack_forget()
        self.customer.frame.pack_forget()
        if method=='نقدي':
            self.cash.frame.pack(fill='x',pady=3); self.cash.set(formatted(self.total))
        elif method=='بطاقة':
            self.card.frame.pack(fill='x',pady=3); self.card.set(formatted(self.total))
        elif method=='آجل':
            self.credit.frame.pack(fill='x',pady=3); self.credit.set(formatted(self.total))
            self.customer.frame.pack(fill='x',after=self.fields_panel,pady=3)
        else:
            for field in (self.cash,self.card)+((self.credit,) if self.is_admin else ()): field.frame.pack(fill='x',pady=3)
            if self.is_admin: self.customer.frame.pack(fill='x',after=self.fields_panel,pady=3)
        for key,b in self.method_buttons.items(): b.configure(fg_color=t.PRIMARY if key==method else t.BG,text_color='white' if key==method else t.MUTED,hover_color=t.HOVER if key==method else t.TINT)
        self.recalculate()

    def schedule(self):
        if self._job: self.after_cancel(self._job)
        self._job=self.after(100,self.recalculate)

    def recalculate(self):
        self._job=None
        try:
            cash=parse_money(self.cash.get()); card=parse_money(self.card.get()); credit=parse_money(self.credit.get())
            difference=cash+card+credit-self.total
            if card+credit>self.total: raise ValueError('البطاقة والآجل أكبر من قيمة الفاتورة')
            self.change_amount=max(0,difference)
            self.change_label.configure(text=f'الباقي للعميل  {formatted(self.change_amount)} {self.page.currency}')
            self.error.configure(text=f'متبقي للدفع: {formatted(-difference)}' if difference<0 else '')
            self.confirm_button.configure(state='normal' if difference>=0 and not self.needs_shift else 'disabled')
            return difference>=0
        except ValueError as e:
            self.change_amount=0; self.error.configure(text=str(e)); self.confirm_button.configure(state='disabled')
            return False

    def open_shift(self,opening):
        Shifts(self.app.db).open(self.app.actor,parse_money(opening))
        self.needs_shift=False; self.shift_panel.pack_forget(); self.page.refresh_shift(); self.recalculate()

    def submit(self):
        if self.sale_id is not None: return self.sale_id
        if self.needs_shift: raise ValueError('افتح الوردية أولًا')
        if not self.recalculate(): raise ValueError('راجع مبالغ الدفع')
        payments=dict(cash=parse_money(self.cash.get()),card=parse_money(self.card.get()),credit=parse_money(self.credit.get()))
        self.confirm_button.configure(state='disabled')
        try:
            if payments['credit']: self.page.party.set(self.customer.get())
            self.sale_id=self.page.complete(payments)
        except Exception:
            self.confirm_button.configure(state='normal')
            raise
        sid=self.sale_id; print_requested=self.print_var.get()
        self.destroy()
        if print_requested:
            try: self.app.receipt(sid)
            except Exception:
                logging.exception('Sale saved but receipt could not be opened')
                self.page.toast(f'تم حفظ فاتورة #{sid}؛ افتح الإيصال من سجل المبيعات.')
        return sid

    def destroy(self):
        for job in (self._job,self._grab_job):
            if job:
                try: self.after_cancel(job)
                except Exception: pass
        try: self.grab_release()
        except Exception: pass
        super().destroy()
