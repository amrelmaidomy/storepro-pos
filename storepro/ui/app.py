import logging
from pathlib import Path
import customtkinter as ctk
from . import theme as t
from .forms import Label,Button,Page,Field,Dialog,button,guarded,rtl
from .pos import CartPage,PurchasePage
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
        t.configure()
        super().__init__(); self.configure(fg_color=t.BG); self.title('StorePro — إدارة المحل'); self.geometry('1360x900'); self.minsize(1060,780)
        self.data_dir=Path(data_dir); self.data_dir.mkdir(parents=True,exist_ok=True)
        self.db=Database(self.data_dir/'storepro.db'); self.auth=Auth(self.db); self.settings=Settings(self.db)
        self.sale_draft={}
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
        self.shell=ctk.CTkFrame(self,fg_color=t.BG,corner_radius=0); self.shell.pack(fill='both',expand=True)
    def logout(self):
        self.actor=None; self.sale_draft={}; self.reset()
        panel=ctk.CTkFrame(self.shell,width=480,fg_color=t.SURFACE,corner_radius=22); panel.pack(expand=True,padx=40,pady=50)
        Label(panel,text='StorePro',font=('Tahoma',34,'bold'),text_color=t.PRIMARY).pack(pady=(30,0))
        Label(panel,text='كل تفاصيل محلك، في مكان واحد.',font=('Tahoma',13),text_color=t.MUTED).pack(pady=(3,6))
        first=not self.db.rows('select id from users')
        Label(panel,text='إنشاء المدير — أول تشغيل' if first else 'تسجيل الدخول',font=('Tahoma',26,'bold')).pack(pady=25,padx=25)
        username=Field(panel,'اسم المستخدم'); password=Field(panel,'كلمة المرور',secret=True)
        error=Label(panel,text='',text_color='#ff7474',font=('Tahoma',13)); error.pack(pady=10)
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
            Label(panel,text='غيّر كلمة المرور القديمة قبل الاستخدام',font=('Tahoma',20)).pack(pady=15)
            new=Field(panel,'كلمة مرور جديدة',secret=True)
            def change(): self.auth.change_password(actor,password,new.get()); self.build_shell()
            button(panel,'تغيير ومتابعة',change)
        else: self.build_shell()
    def build_shell(self):
        self.reset()
        side=ctk.CTkScrollableFrame(self.shell,width=178,fg_color=t.NAV,corner_radius=0,scrollbar_button_color=t.NAV,scrollbar_button_hover_color='#305767')
        side.pack(side='right',fill='y')
        self.body=ctk.CTkFrame(self.shell,fg_color=t.BG,corner_radius=0); self.body.pack(side='left',fill='both',expand=True)
        Label(side,text='S',font=('Tahoma',28,'bold'),width=48,height=48,fg_color=t.PRIMARY,corner_radius=13,text_color='white').pack(anchor='e',padx=12,pady=(25,8))
        Label(side,text=self.settings.get('store_name'),font=('Tahoma',20,'bold'),text_color='white').pack(anchor='e',padx=12)
        Label(side,text='إدارة أبسط. بيع أسرع.',font=('Tahoma',10),text_color='#93B1BF').pack(anchor='e',padx=12,pady=(3,24))
        self.nav_buttons={}; self.nav_groups={}
        admin=self.db.rows('select role from users where id=?',(self.actor,))[0]['role']=='Admin'
        def nav(parent,label,key):
            b=Button(parent,text=label,font=('Tahoma',13),height=39,anchor='e',fg_color='transparent',text_color='#C1D2DB',hover_color='#1D4354',command=guarded(lambda k=key:self.show(k)))
            b.pack(fill='x',pady=3,padx=4); self.nav_buttons[key]=b
        Label(side,text='العمل اليومي',font=('Tahoma',10),text_color='#7399AA').pack(anchor='e',padx=12,pady=(0,6))
        nav(side,'نقطة البيع','pos'); nav(side,'سجل المبيعات','sales'); nav(side,'الوردية والخزنة','finance')
        if admin:
            nav(side,'المنتجات والمخزون','products')
            for title,items in [('المشتريات',[('فاتورة شراء','purchase_cart'),('سجل المشتريات','purchases'),('الموردون','supplier')]),('إدارة المحل',[('العملاء','customer'),('التقارير','reports'),('المستخدمون','users'),('الإعدادات والنسخ','settings')])]:
                group=ctk.CTkFrame(side,fg_color='transparent')
                toggle=Button(side,text=title+'  +',font=('Tahoma',12),height=36,anchor='e',fg_color='transparent',text_color='#93B1BF',hover_color='#1D4354')
                toggle.pack(fill='x',padx=4,pady=(14,3))
                def expand(g=group,b=toggle,title=title):
                    if g.winfo_manager(): g.pack_forget(); b.configure(text=rtl(title+'  +'))
                    else: g.pack(fill='x',after=b); b.configure(text=rtl(title+'  −'))
                toggle.configure(command=expand)
                for label,key in items: nav(group,label,key); self.nav_groups[key]=(group,toggle,title)
        Label(side,text='━━━━━━━━━━━━',text_color='#294C5D').pack(pady=(24,10))
        user=self.db.rows('select username from users where id=?',(self.actor,))[0]['username']
        Label(side,text=user,font=('Tahoma',12,'bold'),text_color='white').pack(anchor='e',padx=12)
        Label(side,text='مدير المحل' if admin else 'كاشير',font=('Tahoma',10),text_color='#93B1BF').pack(anchor='e',padx=12,pady=(0,10))
        Button(side,text='تغيير كلمة المرور',command=guarded(self.password_dialog),font=('Tahoma',10),fg_color='transparent',text_color='#93B1BF',hover_color='#1D4354').pack(fill='x',pady=3)
        Button(side,text='تسجيل خروج',command=self.logout,font=('Tahoma',11),fg_color='transparent',text_color='#93B1BF',hover_color='#1D4354').pack(fill='x',pady=3)
        self.show('pos')
    def password_dialog(self):
        def save(v): self.auth.change_password(self.actor,v['old'],v['new'])
        Dialog(self,'تغيير كلمة المرور',{'old':('الحالية','','',True),'new':('الجديدة','','',True)},save)
    def show(self,key):
        self.auth.require(self.actor,'view' if key in ('pos','sales','finance') else 'manage')
        if self.page: self.page.destroy()
        factories={'pos':lambda:CartPage(self.body,self),'purchase_cart':lambda:PurchasePage(self.body,self,True),'products':lambda:ProductsPage(self.body,self),'customer':lambda:PartiesPage(self.body,self,'customer'),'supplier':lambda:PartiesPage(self.body,self,'supplier'),'sales':lambda:HistoryPage(self.body,self),'purchases':lambda:HistoryPage(self.body,self,True),'finance':lambda:FinancePage(self.body,self),'reports':lambda:ReportsPage(self.body,self),'users':lambda:UsersPage(self.body,self),'settings':lambda:SettingsPage(self.body,self)}
        if key not in factories: raise ValueError('الصفحة غير موجودة')
        self.page=factories[key](); self.page.pack(fill='both',expand=True)
        for nav_key,b in self.nav_buttons.items():
            b.configure(fg_color='#1A5362' if nav_key==key else 'transparent',text_color='white' if nav_key==key else '#C1D2DB')
        if key in self.nav_groups:
            group,toggle,title=self.nav_groups[key]
            group.pack(fill='x',after=toggle); toggle.configure(text=rtl(title+'  −'))
    def receipt(self,sid):
        from ..sales import Sales
        self.auth.require(self.actor,'view')
        sale=Sales(self.db).detail(sid)
        path=render_receipt(sale,self.data_dir/'receipts'/f'{sale["number"]}.html',int(self.settings.get('receipt_width')),self.settings.get('store_name'),self.settings.get('currency'))
        preview_receipt(path)
        return path
    def run(self): self.mainloop()
