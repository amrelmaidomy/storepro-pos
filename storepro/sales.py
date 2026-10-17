from .auth import Auth
from .db import audit
from .catalog import stock_move
from .money import integer,amount
from .finance import active_shift,cash_move,party_move,party_balance,valid_party,payment_values


def allocations(total,weights):
    whole=sum(weights); out=[]; accumulated=0; allocated=0
    for weight in weights:
        accumulated+=weight
        cumulative=(total*accumulated+whole//2)//whole if whole else 0
        out.append(cumulative-allocated); allocated=cumulative
    return out


class Sales:
    def __init__(self,db): self.db=db; self.auth=Auth(db)

    def checkout(self,actor,items,discount,tax_rate,payments,customer_id,request_id):
        integer(discount); integer(tax_rate)
        if tax_rate>10000 or not items or not request_id: raise ValueError('بيانات البيع غير صحيحة')
        cash,card,credit=payment_values(payments)
        if len({x['product_id'] for x in items})!=len(items): raise ValueError('ادمج كميات المنتج المكرر')
        with self.db.transaction() as c:
            self.auth.require(actor,'sell',c)
            old=c.execute('select id from sales where request_id=?',(request_id,)).fetchone()
            if old: return old[0]
            shift=active_shift(c)
            if credit: self.auth.require(actor,'manage',c)
            if customer_id: valid_party(c,customer_id,'customer')
            if credit and not customer_id: raise ValueError('البيع الآجل يحتاج عميلًا')
            prepared=[]
            for item in items:
                q=integer(item['qty'],1)
                p=c.execute('select * from products where id=? and active=1',(item['product_id'],)).fetchone()
                if not p or p['stock']<q: raise ValueError('المنتج معطل أو المخزون غير كافٍ')
                prepared.append((p,q,amount(p['price'],q)))
            subtotal=sum(x[2] for x in prepared)
            if discount>subtotal: raise ValueError('الخصم أكبر من قيمة البيع')
            tax=((subtotal-discount)*tax_rate+5000)//10000
            total=subtotal-discount+tax
            if card+credit>total or cash+card+credit<total: raise ValueError('الدفع غير مكتمل أو مبلغ البطاقة/الآجل أكبر من الإجمالي')
            change=cash+card+credit-total
            sid=c.execute('insert into sales(actor,customer_id,shift_id,subtotal,discount,tax,total,cash,card,credit,change_amount,request_id) values(?,?,?,?,?,?,?,?,?,?,?,?)',(actor,customer_id,shift['id'],subtotal,discount,tax,total,cash,card,credit,change,request_id)).lastrowid
            c.execute('update sales set number=? where id=?',(f'SP-{sid:08d}',sid))
            discounts=allocations(discount,[x[2] for x in prepared])
            net=[x[2]-d for x,d in zip(prepared,discounts)]
            taxes=allocations(tax,net)
            for (p,q,line),n,t in zip(prepared,net,taxes):
                c.execute('insert into sale_items(sale_id,product_id,name,qty,price,cost,line_total,net_total,tax) values(?,?,?,?,?,?,?,?,?)',(sid,p['id'],p['name'],q,p['price'],p['cost'],line,n,t))
                stock_move(c,actor,p['id'],-q,'sale',sid)
            cash_move(c,actor,cash-change,'sale',sid)
            if credit: party_move(c,actor,customer_id,credit,'sale',sid)
            audit(c,actor,'sale_completed',sid)
            return sid

    def detail(self,sale_id):
        found=self.db.rows('select * from sales where id=?',(sale_id,))
        if not found: raise ValueError('الفاتورة غير موجودة')
        return dict(found[0],items=self.db.rows('select * from sale_items where sale_id=? order by id',(sale_id,)))

    def refund(self,actor,sale_id,items,method):
        if not items or method not in ('cash','card'): raise ValueError('حدد البنود وطريقة الاسترداد')
        if len({x['item_id'] for x in items})!=len(items): raise ValueError('بنود مرتجع مكررة')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            header=c.execute('select * from sales where id=?',(sale_id,)).fetchone()
            if not header: raise ValueError('الفاتورة غير موجودة')
            if header['legacy']: raise ValueError('الفاتورة القديمة بدون توزيع موثوق للخصم والضريبة؛ سجّل تسوية موثقة بدل مرتجع تلقائي')
            active_shift(c)
            prepared=[]
            for item in items:
                q=integer(item['qty'],1)
                line=c.execute('select * from sale_items where id=? and sale_id=?',(item['item_id'],sale_id)).fetchone()
                if not line or q+line['returned']>line['qty'] or not line['product_id']: raise ValueError('كمية المرتجع غير صحيحة')
                newqty=line['returned']+q
                value=((line['net_total']+line['tax'])*newqty+line['qty']//2)//line['qty']-line['refunded']
                cost=(amount(line['cost'],line['qty'])*newqty+line['qty']//2)//line['qty']-line['cost_returned']
                netvalue=(line['net_total']*newqty+line['qty']//2)//line['qty']-(line['net_total']*line['returned']+line['qty']//2)//line['qty']
                prepared.append((line,q,value,cost,netvalue))
            total=sum(x[2] for x in prepared)
            rid=c.execute("insert into returns(kind,source_id,actor,total,method) values('sale',?,?,?,?)",(sale_id,actor,total,method)).lastrowid
            for line,q,value,cost,netvalue in prepared:
                stock_move(c,actor,line['product_id'],q,'sale_return',rid)
                p=c.execute('select * from products where id=?',(line['product_id'],)).fetchone()
                oldqty=p['stock']-q
                newcost=(oldqty*p['cost']+q*line['cost']+p['stock']//2)//p['stock']
                c.execute('update products set cost=? where id=?',(newcost,p['id']))
                c.execute('update sale_items set returned=returned+?,refunded=refunded+?,cost_returned=cost_returned+? where id=?',(q,value,cost,line['id']))
                c.execute('insert into return_items(return_id,item_id,qty,amount,cost,net_amount,tax_amount) values(?,?,?,?,?,?,?)',(rid,line['id'],q,value,cost,netvalue,value-netvalue))
            debt=0
            if header['credit']:
                previous=c.execute("select coalesce(sum(-amount),0) from party_moves where kind='sale_return' and reference=?",(str(sale_id),)).fetchone()[0]
                debt=min(total,max(0,header['credit']-previous),max(0,party_balance(c,header['customer_id'])))
                party_move(c,actor,header['customer_id'],-debt,'sale_return',sale_id)
            if method=='cash': cash_move(c,actor,-(total-debt),'sale_return',rid)
            audit(c,actor,'sale_return',rid)
            return rid
