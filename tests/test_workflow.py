from storepro.db import Database
from storepro.auth import Auth
from storepro.catalog import Catalog
from storepro.parties import Parties
from storepro.purchases import Purchases
from storepro.sales import Sales
from storepro.shifts import Shifts
from storepro.reports import Reports
from storepro.backup import Backup


def test_complete_business_workflow(tmp_path):
    db=Database(tmp_path/'store.db'); auth=Auth(db); u=auth.setup_admin('owner','Strong123!')
    Shifts(db).open(u,10000)
    cat=Catalog(db); p=cat.save_product(u,dict(name='أرز',cost=0,price=1000))
    parties=Parties(db); supplier=parties.save(u,'supplier',dict(name='مورد')); customer=parties.save(u,'customer',dict(name='عميل'))
    Purchases(db).receive(u,supplier,[dict(product_id=p,qty=10000,price=600)],dict(cash=4000),'purchase')
    sales=Sales(db); invoice=sales.checkout(u,[dict(product_id=p,qty=3000)],0,0,dict(cash=1000,credit=2000),customer,'sale')
    item=sales.detail(invoice)['items'][0]['id']
    sales.refund(u,invoice,[dict(item_id=item,qty=1000)],'cash')
    parties.pay(u,'customer',customer,1000,'cash')
    parties.pay(u,'supplier',supplier,2000,'cash')
    assert parties.balance(customer)==0 and parties.balance(supplier)==0
    assert cat.search('أرز')[0]['stock']==8000
    result=Shifts(db).close(u,6000)
    assert result['difference']==0 and result['expected']==6000
    summary=Reports(db).summary('2000-01-01','2099-01-01')
    assert summary['profit']==800
    backup=Backup(db).automatic(tmp_path/'backups',2)
    cat.adjust(u,p,1000,'later')
    Backup(db).restore(u,backup)
    assert cat.search('أرز')[0]['stock']==8000
