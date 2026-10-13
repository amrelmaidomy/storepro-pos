import logging
from pathlib import Path
import customtkinter as ctk
from .forms import Page,Field,Dialog,button,guarded
from .pos import CartPage
from .inventory import ProductsPage
from .parties import PartiesPage
from .finance import FinancePage,HistoryPage
from .reports import ReportsPage
from .admin import UsersPage,SettingsPage
from ..db import Database
from ..auth import Auth
from ..settings import Settings
from ..exports import render_receipt,preview_receipt


class App(ctk.CTk):
    def __init__(self,data_dir):
        super().__init__(); self.title('StorePro — إدارة المحل'); self.geometry('1360x900'); self.minsize(1060,780)
        self.data_dir=Path(data_dir); self.data_dir.mkdir(parents=True,exist_ok=True)
        self.db=Database(self.data_dir/'storepro.db'); self.auth=Auth(self.db); self.settings=Settings(self.db)
        self.actor=None; self.page=None; self.body=None; self.shell=None
        self.report_callback_exception=self.callback_error
        self.logout()
    def callback_error(self,typ,value,tb):
        logging.error('UI callback error',exc_info=(typ,value,tb))
        from tkinter import messagebox
        messagebox.showerror('خطأ','تعذر تنفيذ العملية. راجع سجل الأخطاء.')
    def reset(self):
        if self.page: self.page.destroy(); self.page=None
        if self.shell: self.shell.destroy()
        self.shell=ctk.CTkFrame(self); self.shell.pack(fill='both',expand=True)
    def logout(self):
        self.actor=None; self.reset()
        panel=ctk.CTkFrame(self.shell,width=480); panel.pack(expand=True,padx=40,pady=50)
        first=not self.db.rows('select id from users')
        ctk.CTkLabel(panel,text='إنشاء المدير — أول تشغيل' if first else 'تسجيل الدخول',font=('Tahoma',26,'bold')).pack(pady=25,padx=25)
        username=Field(panel,'اسم المستخدم'); password=Field(panel,'كلمة المرور',secret=True)
        error=ctk.CTkLabel(panel,text='',text_color='#ff7474',font=('Tahoma',13)); error.pack(pady=10)
        def submit():
            try:
                if first: self.auth.setup_admin(username.get(),password.get())
                self.sign_in(username.get(),password.get())
            except (ValueError,PermissionError) as e: error.configure(text=str(e))
        bar=ctk.CTkFrame(panel); bar.pack(fill='x',pady=15)
        button(bar,'إنشاء والدخول' if first else 'دخول',submit)
        password.widget.bind('<Return>',lambda e:submit()); username.widget.focus_set()
    def sign_in(self,username,password):
        actor=self.auth.login(username,password)
        self.actor=actor
        user=self.db.rows('select must_reset from users where id=?',(actor,))[0]
        self.reset()
        if user['must_reset']:
            panel=ctk.CTkFrame(self.shell); panel.pack(expand=True)
            ctk.CTkLabel(panel,text='غيّر كلمة المرور القديمة قبل الاستخدام',font=('Tahoma',20)).pack(pady=15)
            new=Field(panel,'كلمة مرور جديدة',secret=True)
            def change(): self.auth.change_password(actor,password,new.get()); self.build_shell()
            button(panel,'تغيير ومتابعة',change)
        else: self.build_shell()
    def build_shell(self):
        self.reset()
        side=ctk.CTkScrollableFrame(self.shell,width=190); side.pack(side='right',fill='y',padx=5,pady=5)
        self.body=ctk.CTkFrame(self.shell); self.body.pack(side='left',fill='both',expand=True)
        ctk.CTkLabel(side,text=self.settings.get('store_name'),font=('Tahoma',20,'bold')).pack(pady=15)
        items=[('نقطة البيع','pos'),('المنتجات','products'),('العملاء','customer'),('الموردون','supplier'),('فاتورة شراء','purchase_cart'),('سجل المشتريات','purchases'),('سجل المبيعات','sales'),('الوردية والخزنة','finance'),('التقارير','reports'),('المستخدمون','users'),('الإعدادات والنسخ','settings')]
        admin=self.db.rows('select role from users where id=?',(self.actor,))[0]['role']=='Admin'
        for label,key in items:
            if not admin and key not in ('pos','sales','finance'): continue
            b=ctk.CTkButton(side,text=label,font=('Tahoma',14),command=guarded(lambda k=key:self.show(k))); b.pack(fill='x',pady=5)
        ctk.CTkButton(side,text='تغيير كلمة المرور',command=guarded(self.password_dialog),font=('Tahoma',14)).pack(fill='x',pady=12)
        ctk.CTkButton(side,text='تسجيل خروج',command=self.logout,font=('Tahoma',14)).pack(fill='x',pady=5)
        self.show('pos')
    def password_dialog(self):
        def save(v): self.auth.change_password(self.actor,v['old'],v['new'])
        Dialog(self,'تغيير كلمة المرور',{'old':('الحالية','','',True),'new':('الجديدة','','',True)},save)
    def show(self,key):
        self.auth.require(self.actor,'view' if key in ('pos','sales','finance') else 'manage')
        if self.page: self.page.destroy()
        factories={'pos':lambda:CartPage(self.body,self),'purchase_cart':lambda:CartPage(self.body,self,True),'products':lambda:ProductsPage(self.body,self),'customer':lambda:PartiesPage(self.body,self,'customer'),'supplier':lambda:PartiesPage(self.body,self,'supplier'),'sales':lambda:HistoryPage(self.body,self),'purchases':lambda:HistoryPage(self.body,self,True),'finance':lambda:FinancePage(self.body,self),'reports':lambda:ReportsPage(self.body,self),'users':lambda:UsersPage(self.body,self),'settings':lambda:SettingsPage(self.body,self)}
        if key not in factories: raise ValueError('الصفحة غير موجودة')
        self.page=factories[key](); self.page.pack(fill='both',expand=True)
    def receipt(self,sid):
        from ..sales import Sales
        self.auth.require(self.actor,'view')
        sale=Sales(self.db).detail(sid)
        path=render_receipt(sale,self.data_dir/'receipts'/f'{sale["number"]}.html',int(self.settings.get('receipt_width')),self.settings.get('store_name'),self.settings.get('currency'))
        preview_receipt(path)
        return path
    def run(self): self.mainloop()
