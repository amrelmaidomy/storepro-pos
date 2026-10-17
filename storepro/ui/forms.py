import logging
import re
import arabic_reshaper
from bidi.algorithm import get_display
import sqlite3
import tkinter as tk
from tkinter import ttk,messagebox
import customtkinter as ctk

from . import theme
from ..money import formatted,quantity_text

FONT=('Tahoma',14)


def rtl(value):
    text=str(value)
    return get_display(arabic_reshaper.reshape(text)) if re.search(r'[\u0600-\u06ff]',text) else text


class Label(ctk.CTkLabel):
    def __init__(self,*args,**kwargs):
        if 'text' in kwargs: kwargs['text']=rtl(kwargs['text'])
        super().__init__(*args,**kwargs)
    def configure(self,**kwargs):
        if 'text' in kwargs: kwargs['text']=rtl(kwargs['text'])
        return super().configure(**kwargs)


class Button(ctk.CTkButton):
    def __init__(self,*args,**kwargs):
        if 'text' in kwargs: kwargs['text']=rtl(kwargs['text'])
        super().__init__(*args,**kwargs)


def guarded(callback):
    def run(*args,**kwargs):
        try: return callback(*args,**kwargs)
        except (ValueError,PermissionError,sqlite3.IntegrityError) as e:
            messagebox.showerror('تعذر تنفيذ العملية',str(e))
        except Exception:
            logging.exception('Operation failed')
            messagebox.showerror('خطأ','تعذر تنفيذ العملية. راجع ملف الأخطاء أو أعد المحاولة.')
    return run


def button(parent,text,callback,**kwargs):
    b=Button(parent,text=text,font=FONT,command=guarded(callback),**kwargs)
    b.pack(side='right',padx=4,pady=5)
    return b


class ComboBox(ctk.CTkComboBox):
    def destroy(self):
        # CustomTkinter 5.2.2 unregisters appearance, but not scaling, for its dropdown menu.
        # Remove the callback while the menu still has a valid widget parent.
        ctk.ScalingTracker.remove_widget(self._dropdown_menu._set_scaling,self._dropdown_menu)
        super().destroy()


class Field:
    def __init__(self,parent,label,value='',choices=None,secret=False):
        self.choices={rtl(str(v)):str(v) for v in choices} if choices else {}
        self.frame=ctk.CTkFrame(parent,fg_color='transparent'); self.frame.pack(fill='x',pady=3)
        Label(self.frame,text=label,font=FONT,width=150,anchor='e').pack(side='right',padx=6)
        if choices:
            self.widget=ComboBox(self.frame,values=list(self.choices),font=FONT,state='readonly',width=220)
            self.widget.set(rtl(str(value) if value in choices else str(choices[0])))
        else:
            self.widget=ctk.CTkEntry(self.frame,font=FONT,justify='right',width=220,show='*' if secret else '')
            self.widget.insert(0,str(value))
        self.widget.pack(side='right',fill='x',expand=True)
    def get(self):
        value=self.widget.get().strip()
        return self.choices.get(value,value)
    def set(self,value):
        if isinstance(self.widget,ctk.CTkComboBox): self.widget.set(rtl(str(value)))
        else: self.widget.delete(0,'end'); self.widget.insert(0,str(value))


class Dialog(ctk.CTkToplevel):
    def __init__(self,parent,title,fields,save):
        super().__init__(parent); self.title(title); self.geometry('560x660'); self.transient(parent.winfo_toplevel())
        body=ctk.CTkScrollableFrame(self); body.pack(fill='both',expand=True,padx=10,pady=10)
        self.fields={key:Field(body,*spec) for key,spec in fields.items()}
        toolbar=ctk.CTkFrame(self); toolbar.pack(fill='x',padx=10,pady=8)
        def submit():
            save({key:field.get() for key,field in self.fields.items()})
            self.destroy()
        self.submit=submit
        button(toolbar,'حفظ',submit); button(toolbar,'إلغاء',self.destroy)
        self.after(150,self.grab_set)


LABELS={'id':'رقم','name':'الاسم','barcode':'الباركود','category':'التصنيف','unit':'الوحدة','stock':'المخزون','min_stock':'الحد الأدنى','cost':'التكلفة','price':'السعر','active':'نشط','date':'التاريخ','number':'الفاتورة','total':'الإجمالي','qty':'الكمية','returned':'المرتجع','balance':'الرصيد','phone':'الهاتف','address':'العنوان','username':'المستخدم','role':'الدور','amount':'المبلغ','kind':'النوع','description':'الوصف','reference':'المرجع','quantity':'الكمية','net_sales':'الصافي','invoices':'عدد الفواتير','supplier':'المورد','opening':'رصيد افتتاحي','expected':'المتوقع','counted':'الفعلي','difference':'الفرق','opened':'فتح','closed':'إغلاق','actor':'المستخدم','method':'طريقة الدفع','action':'الإجراء','detail':'التفاصيل','product_id':'رقم المنتج','qty_text':'الكمية','price_text':'سعر الوحدة','cost_text':'التكلفة','stock_text':'المخزون','minimum_text':'حد التنبيه','returned_text':'مرتجع','total_text':'القيمة','balance_text':'الرصيد','amount_text':'المبلغ','supplier_id':'رقم المورد'}


MONEY_COLUMNS={'cost','price','total','balance','amount','net_sales','opening','expected','counted','difference','paid','subtotal','discount','tax','cash','card','credit','change_amount','line_total','net_total','refunded','cost_returned'}
QUANTITY_COLUMNS={'stock','min_stock','qty','quantity','returned'}


def display_value(column,value):
    if value is None: return '—'
    if isinstance(value,(int,float)) and column in MONEY_COLUMNS: return formatted(value)
    if isinstance(value,(int,float)) and column in QUANTITY_COLUMNS: return quantity_text(value)
    return value


class Table(ctk.CTkFrame):
    def __init__(self,parent,columns):
        super().__init__(parent,fg_color=theme.SURFACE,corner_radius=12); self.columns=list(columns); self.rows=[]
        style=ttk.Style()
        if 'clam' in style.theme_names(): style.theme_use('clam')
        style.configure('Treeview',font=('Tahoma',11),rowheight=42,background=theme.SURFACE,fieldbackground=theme.SURFACE,foreground=theme.TEXT,borderwidth=0)
        style.configure('Treeview.Heading',font=('Tahoma',11,'bold'),background=theme.BG,foreground=theme.MUTED,relief='flat',padding=10)
        style.map('Treeview',background=[('selected',theme.TINT)],foreground=[('selected',theme.PRIMARY)])
        self.tree=ttk.Treeview(self,columns=self.columns,show='headings',selectmode='browse')
        for col in self.columns:
            self.tree.heading(col,text=rtl(LABELS.get(col,col))); self.tree.column(col,width=120,anchor='e',minwidth=80)
        y=ttk.Scrollbar(self,orient='vertical',command=self.tree.yview); y.pack(side='left',fill='y')
        x=ttk.Scrollbar(self,orient='horizontal',command=self.tree.xview); x.pack(side='bottom',fill='x')
        self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set); self.tree.pack(fill='both',expand=True)
    def load(self,rows):
        self.rows=rows; self.tree.delete(*self.tree.get_children())
        for index,row in enumerate(rows): self.tree.insert('', 'end',iid=str(index),values=[rtl(display_value(k,row.get(k,''))) for k in self.columns])
    def selected(self):
        ids=self.tree.selection()
        if not ids: raise ValueError('اختر صفًا من الجدول أولًا')
        return self.rows[int(ids[0])]


class Page(ctk.CTkFrame):
    def __init__(self,parent,app,title):
        super().__init__(parent,fg_color=theme.BG,corner_radius=0); self.app=app
        Label(self,text=title,font=('Tahoma',24,'bold')).pack(anchor='e',padx=15,pady=8)
        self.toolbar=ctk.CTkFrame(self,fg_color=theme.SURFACE,corner_radius=12); self.toolbar.pack(fill='x',padx=10,pady=8)
    def notify(self,text): messagebox.showinfo('StorePro',text)
