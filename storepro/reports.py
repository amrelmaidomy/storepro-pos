from datetime import date


def dates(start,end):
    start=date.fromisoformat(start).isoformat(); end=date.fromisoformat(end).isoformat()
    if start>end: raise ValueError('بداية الفترة بعد نهايتها')
    return start,end


class Reports:
    def __init__(self,db): self.db=db

    def summary(self,start,end):
        args=dates(start,end)
        sold=self.db.rows('select coalesce(sum(total),0) sales,coalesce(sum(subtotal-discount),0) net,coalesce(sum(tax),0) tax,count(*) invoices,coalesce(sum(legacy),0) historical from sales where date(date) between ? and ?',args)[0]
        returned=self.db.rows("select coalesce(sum(total),0) refunds from returns where kind='sale' and date(date) between ? and ?",args)[0]['refunds']
        # Per-return net/tax amounts are stored, so repeated fractional returns retain exact rounding.
        refund=self.db.rows("select coalesce(sum(ri.net_amount),0) net,coalesce(sum(ri.tax_amount),0) tax,coalesce(sum(ri.cost),0) cost from return_items ri join returns r on r.id=ri.return_id where r.kind='sale' and date(r.date) between ? and ?",args)[0]
        cost=self.db.rows('select coalesce(sum((i.cost*i.qty+500)/1000),0) cost from sale_items i join sales s on s.id=i.sale_id where i.cost is not null and date(s.date) between ? and ?',args)[0]['cost']
        known_net=self.db.rows('select coalesce(sum(i.net_total),0) net from sale_items i join sales s on s.id=i.sale_id where i.cost is not null and date(s.date) between ? and ?',args)[0]['net']
        return dict(sales=sold['sales'],refunds=returned,net_sales=sold['net']-refund['net'],tax=sold['tax']-refund['tax'],profit=known_net-refund['net']-cost+refund['cost'],invoices=sold['invoices'],historical_unknown_cost=sold['historical'])

    def table(self,kind,start,end):
        args=dates(start,end)
        queries={
            'sales':('select s.*,u.username from sales s join users u on u.id=s.actor where date(s.date) between ? and ? order by s.id desc',args),
            'by_product':('select i.product_id,i.name,sum(i.qty) quantity,sum(i.net_total) net_sales from sale_items i join sales s on s.id=i.sale_id where date(s.date) between ? and ? group by i.product_id,i.name',args),
            'by_user':('select u.username,count(*) invoices,sum(s.total) total from sales s join users u on u.id=s.actor where date(s.date) between ? and ? group by u.id',args),
            'returns':('select * from returns where date(date) between ? and ? order by id desc',args),
            'purchases':('select p.*,s.name supplier from purchases p join parties s on s.id=p.supplier_id where date(p.date) between ? and ? order by p.id desc',args),
            'products':('select * from products order by name',()),
            'low_stock':('select * from products where active=1 and stock<=min_stock order by name',()),
            'stock':('select m.*,p.name from stock_moves m join products p on p.id=m.product_id where date(m.date) between ? and ? order by m.id desc',args),
            'cash':('select * from cash_moves where date(date) between ? and ? order by id desc',args),
            'shifts':('select *, counted-expected difference from shifts where date(opened) between ? and ? order by id desc',args),
            'balances':('select p.id,p.kind,p.name,coalesce(sum(m.amount),0) balance from parties p left join party_moves m on m.party_id=p.id group by p.id',()),
            'ledger':('select m.*,p.name,p.kind party_kind from party_moves m join parties p on p.id=m.party_id where date(m.date) between ? and ? order by m.id desc',args),
            'audit':('select a.*,u.username from audit a left join users u on u.id=a.actor where date(a.date) between ? and ? order by a.id desc',args),
        }
        if kind not in queries: raise ValueError('نوع تقرير غير صحيح')
        sql,params=queries[kind]
        return self.db.rows(sql,params)
