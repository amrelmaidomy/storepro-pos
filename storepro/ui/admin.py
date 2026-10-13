from tkinter import filedialog,messagebox
from .forms import Label,Page,Field,Table,Dialog,button
from ..settings import DEFAULTS
from ..backup import Backup


class UsersPage(Page):
    def __init__(self,parent,app):
        super().__init__(parent,app,'المستخدمون والصلاحيات')
        button(self.toolbar,'إضافة',lambda:self.edit()); button(self.toolbar,'تعديل المحدد',lambda:self.edit(self.table.selected()))
        self.table=Table(self,['id','username','role','active']); self.table.pack(fill='both',expand=True,padx=10,pady=10); self.refresh()
    def refresh(self):
        self.app.auth.require(self.app.actor,'manage')
        self.table.load(self.app.db.rows('select id,username,role,active from users order by id'))
    def edit(self,user=None):
        u=user or {}
        def save(v):
            self.app.auth.save_user(self.app.actor,u.get('id'),v['username'],v['password'],'Admin' if v['role']=='مدير' else 'Cashier',v['active']=='نشط'); self.refresh()
        Dialog(self,'بيانات المستخدم',{'username':('اسم المستخدم',u.get('username','')),'password':('كلمة مرور جديدة (فارغة لإبقائها)','','',True),'role':('الصلاحية','مدير' if u.get('role')=='Admin' else 'كاشير',['مدير','كاشير']),'active':('الحالة','نشط' if u.get('active',1) else 'معطل',['نشط','معطل'])},save)


class SettingsPage(Page):
    def __init__(self,parent,app):
        super().__init__(parent,app,'الإعدادات والنسخ الاحتياطي')
        button(self.toolbar,'حفظ الإعدادات',self.save); button(self.toolbar,'نسخ احتياطي',self.backup); button(self.toolbar,'استعادة نسخة',self.restore)
        notice=app.settings.get('migration_notice')
        if notice: Label(self,text=notice,wraplength=900,text_color='#b34b00',font=('Tahoma',13)).pack(fill='x',padx=10,pady=10)
        labels={'store_name':'اسم المحل','currency':'رمز العملة','tax_rate':'الضريبة الافتراضية %','receipt_width':'عرض الإيصال مم','backup_keep':'عدد النسخ التلقائية','auto_backup':'نسخ عند إغلاق الوردية (1 نعم / 0 لا)'}
        self.fields={k:Field(self,labels[k],app.settings.get(k),['58','80'] if k=='receipt_width' else None) for k in DEFAULTS}
        Field(self,'مجلد البيانات',str(app.data_dir)).widget.configure(state='disabled')
    def save(self): self.app.settings.save(self.app.actor,{k:f.get() for k,f in self.fields.items()}); self.notify('تم حفظ الإعدادات')
    def backup(self):
        self.app.auth.require(self.app.actor,'manage')
        path=filedialog.asksaveasfilename(defaultextension='.db',filetypes=[('StorePro backup','*.db')])
        if path: Backup(self.app.db).export(self.app.actor,path); self.notify('تم حفظ النسخة الاحتياطية')
    def restore(self):
        path=filedialog.askopenfilename(filetypes=[('StorePro backup','*.db')])
        if path and messagebox.askyesno('استعادة','سيتم أخذ نسخة أمان ثم استبدال البيانات الحالية وتسجيل الخروج. هل تريد الاستعادة؟'):
            Backup(self.app.db).restore(self.app.actor,path); self.app.logout()
