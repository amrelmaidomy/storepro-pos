from .auth import Auth
from .db import audit
from .money import integer,amount
from .catalog import stock_move
from .finance import valid_party,party_move,party_balance,cash_move,payment_values


class Purchases:
    def __init__(self,db): self.db=db; self.auth=Auth(db)

    def receive(self,actor,supplier_id,items,payments,request_id):
        if not items or not request_id: raise ValueError('أضف بنودًا للفـاتورة')
        cash,card,credit=payment_values(payments)
        if credit: raise ValueError('مستحق المورد يحسب تلقائيًا')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            old=c.execute('select id from purchases where request_id=?',(request_id,)).fetchone()
            if old: return old[0]
            valid_party(c,supplier_id,'supplier')
            prepared=[]
            if len({x['product_id'] for x in items})!=len(items): raise ValueError('ادمج الكميات المكررة لنفس المنتج')
            for item in items:
                q=integer(item['qty'],1); price=integer(item['price'])
                p=c.execute('select * from products where id=? and active=1',(item['product_id'],)).fetchone()
                if not p: raise ValueError('المنتج غير موجود أو معطل')
                prepared.append((p,q,price,amount(price,q)))
            total=sum(x[3] for x in prepared)
            if cash+card>total: raise ValueError('المدفوع أكبر من الإجمالي')
            invoice=c.execute('insert into purchases(supplier_id,actor,total,paid,request_id) values(?,?,?,?,?)',(supplier_id,actor,total,cash+card,request_id)).lastrowid
            for p,q,price,line in prepared:
                newcost=(p['stock']*p['cost']+q*price+(p['stock']+q)//2)//(p['stock']+q)
                c.execute('update products set cost=? where id=?',(newcost,p['id']))
                c.execute('insert into purchase_items(purchase_id,product_id,name,qty,price,line_total) values(?,?,?,?,?,?)',(invoice,p['id'],p['name'],q,price,line))
                stock_move(c,actor,p['id'],q,'purchase',invoice)
            party_move(c,actor,supplier_id,total-cash-card,'purchase',invoice)
            cash_move(c,actor,-cash,'purchase',invoice)
            audit(c,actor,'purchase_received',invoice)
            return invoice

    def detail(self,invoice):
        headers=self.db.rows('select * from purchases where id=?',(invoice,))
        if not headers: raise ValueError('الفاتورة غير موجودة')
        return dict(headers[0],items=self.db.rows('select * from purchase_items where purchase_id=?',(invoice,)))

    def return_items(self,actor,purchase_id,items,method='cash'):
        if not items or method not in ('cash','card'): raise ValueError('اختر البنود وطريقة الاسترداد')
        if len({x['item_id'] for x in items})!=len(items): raise ValueError('بنود مكررة')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            header=c.execute('select * from purchases where id=?',(purchase_id,)).fetchone()
            if not header: raise ValueError('الفاتورة غير موجودة')
            prepared=[]
            for item in items:
                q=integer(item['qty'],1)
                line=c.execute('select * from purchase_items where id=? and purchase_id=?',(item['item_id'],purchase_id)).fetchone()
                if not line or q+line['returned']>line['qty']: raise ValueError('الكمية أكبر من المتبقي للمرتجع')
                cumulative=(line['line_total']*(line['returned']+q)+line['qty']//2)//line['qty']
                value=cumulative-line['refunded']
                prepared.append((line,q,value))
            total=sum(x[2] for x in prepared)
            rid=c.execute("insert into returns(kind,source_id,actor,total,method) values('purchase',?,?,?,?)",(purchase_id,actor,total,method)).lastrowid
            for line,q,value in prepared:
                stock_move(c,actor,line['product_id'],-q,'purchase_return',rid)
                c.execute('update purchase_items set returned=returned+?,refunded=refunded+? where id=?',(q,value,line['id']))
                c.execute('insert into return_items(return_id,item_id,qty,amount) values(?,?,?,?)',(rid,line['id'],q,value))
                # Reverse weighted cost of the returned purchase; prevent negative valuation.
                p=c.execute('select * from products where id=?',(line['product_id'],)).fetchone()
                if p['stock']:
                    oldstock=p['stock']+q
                    cost=max(0,(oldstock*p['cost']-q*line['price']+p['stock']//2)//p['stock'])
                    c.execute('update products set cost=? where id=?',(cost,p['id']))
            # Cancel invoice debt first, limited to its unpaid amount and current supplier balance.
            previous=c.execute("select coalesce(sum(-amount),0) from party_moves where kind='purchase_return' and reference=?",(str(purchase_id),)).fetchone()[0]
            debt=min(total,max(0,header['total']-header['paid']-previous),max(0,party_balance(c,header['supplier_id'])))
            party_move(c,actor,header['supplier_id'],-debt,'purchase_return',purchase_id)
            if method=='cash': cash_move(c,actor,total-debt,'purchase_return',rid)
            audit(c,actor,'purchase_return',rid)
            return rid
