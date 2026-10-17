import sqlite3
from .auth import Auth
from .db import audit
from .money import integer


class Catalog:
    def __init__(self,db): self.db=db; self.auth=Auth(db)

    def save_product(self,actor,fields):
        name=str(fields.get('name','')).strip(); barcode=str(fields.get('barcode','') or '').strip() or None
        if not name: raise ValueError('اسم المنتج مطلوب')
        cost=integer(fields.get('cost',0)); price=integer(fields.get('price',0)); minimum=integer(fields.get('min_stock',0))
        pid=fields.get('id')
        try:
            with self.db.transaction() as c:
                self.auth.require(actor,'manage',c)
                values=(barcode,name,str(fields.get('category','')),str(fields.get('unit','قطعة')),cost,price,minimum,int(bool(fields.get('active',True))))
                if pid:
                    if not c.execute('select 1 from products where id=?',(pid,)).fetchone(): raise ValueError('المنتج غير موجود')
                    c.execute('update products set barcode=?,name=?,category=?,unit=?,cost=?,price=?,min_stock=?,active=? where id=?',values+(pid,))
                else:
                    pid=c.execute('insert into products(barcode,name,category,unit,cost,price,min_stock,active) values(?,?,?,?,?,?,?,?)',values).lastrowid
                audit(c,actor,'product_saved',pid)
                return pid
        except sqlite3.IntegrityError as e: raise ValueError('باركود مكرر أو بيانات غير صحيحة') from e

    def search(self,query='',include_inactive=False):
        query=str(query).strip()
        return self.db.rows("select * from products where (active=1 or ?) and (barcode=? or cast(id as text)=? or name like ?) order by name,id",(int(include_inactive),query,query,'%'+query+'%'))

    def adjust(self,actor,product_id,quantity,reason):
        if type(quantity) is not int or not quantity or abs(quantity)>10**12 or not reason.strip(): raise ValueError('أدخل كمية وسبب التسوية')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            move=stock_move(c,actor,product_id,quantity,'adjust',reason)
            audit(c,actor,'stock_adjusted',f'{product_id}: {quantity}; {reason}')
            return move


def stock_move(c,actor,pid,qty,kind,reference):
    changed=c.execute('update products set stock=stock+? where id=? and stock+?>=0',(qty,pid,qty)).rowcount
    if not changed: raise ValueError('المنتج غير موجود أو المخزون غير كافٍ')
    return c.execute('insert into stock_moves(product_id,qty,kind,reference,actor) values(?,?,?,?,?)',(pid,qty,kind,str(reference),actor)).lastrowid
