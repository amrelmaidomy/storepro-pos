from .auth import Auth
from .db import audit
from .money import parse_money

DEFAULTS={'store_name':'StorePro','currency':'ج.م','tax_rate':'0','receipt_width':'80','backup_keep':'10','auto_backup':'1'}


class Settings:
    def __init__(self,db): self.db=db
    def get(self,key):
        rows=self.db.rows('select value from settings where key=?',(key,))
        return rows[0]['value'] if rows else DEFAULTS.get(key,'')
    def save(self,actor,values):
        if set(values)-set(DEFAULTS): raise ValueError('إعداد غير معروف')
        all_values={k:str(values.get(k,self.get(k))) for k in DEFAULTS}
        if not all_values['store_name'].strip() or not all_values['currency'].strip(): raise ValueError('الاسم والعملة مطلوبان')
        rate=parse_money(all_values['tax_rate'])
        if rate>10000 or all_values['receipt_width'] not in ('58','80') or not 1<=int(all_values['backup_keep'])<=100 or all_values['auto_backup'] not in ('0','1'): raise ValueError('إعدادات غير صحيحة')
        with self.db.transaction() as c:
            Auth(self.db).require(actor,'manage',c)
            for key,value in all_values.items(): c.execute('insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value',(key,value))
            audit(c,actor,'settings_saved','preferences')
