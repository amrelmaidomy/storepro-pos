import pytest
from storepro.sales import Sales
from storepro.catalog import Catalog
from storepro.parties import Parties
from storepro.auth import Auth

@pytest.fixture
def sale_env(env):
    db,u=env; cat=Catalog(db)
    p=cat.save_product(u,dict(name='سكر',barcode='1',cost=200,price=500,min_stock=0))
    cat.adjust(u,p,10000,'رصيد افتتاحي')
    return db,u,p

def test_sale_atomic_and_idempotent(sale_env):
    db,u,p=sale_env; s=Sales(db)
    args=(u,[dict(product_id=p,qty=2000)],0,0,dict(cash=1200,card=0,credit=0),None,'sale1')
    inv=s.checkout(*args)
    assert s.checkout(*args)==inv
    detail=s.detail(inv)
    assert detail['total']==1000 and detail['change_amount']==200
    assert db.rows('select stock from products')[0]['stock']==8000
    assert sum(x['amount'] for x in db.rows('select amount from cash_moves'))==1000
    with pytest.raises(ValueError): s.checkout(u,[dict(product_id=p,qty=1000),dict(product_id=999,qty=1000)],0,0,dict(cash=1000),None,'bad')
    assert db.rows('select stock from products')[0]['stock']==8000
    assert len(db.rows('select * from sales'))==1

@pytest.mark.parametrize('qty,discount,tax,payments',[(11000,0,0,dict(cash=999999)),(0,0,0,dict(cash=500)),(1000,501,0,dict(cash=500)),(1000,0,10001,dict(cash=500)),(1000,0,0,dict(cash=499)),(1000,0,0,dict(card=501))])
def test_reject_invalid_sales(sale_env,qty,discount,tax,payments):
    db,u,p=sale_env
    with pytest.raises(ValueError): Sales(db).checkout(u,[dict(product_id=p,qty=qty)],discount,tax,payments,None,'invalid')
    assert not db.rows('select * from sales')
    assert db.rows('select stock from products')[0]['stock']==10000

def test_credit_permissions_and_payments(sale_env):
    db,u,p=sale_env; parties=Parties(db); customer=parties.save(u,'customer',dict(name='عميل'))
    cashier=Auth(db).save_user(u,None,'cashier','Strong123!','Cashier',True)
    s=Sales(db)
    with pytest.raises(PermissionError): s.checkout(cashier,[dict(product_id=p,qty=1000)],0,0,dict(credit=500),customer,'no')
    with pytest.raises(ValueError): s.checkout(u,[dict(product_id=p,qty=1000)],0,0,dict(credit=500),None,'missing')
    inv=s.checkout(u,[dict(product_id=p,qty=2000)],0,0,dict(cash=200,card=300,credit=500),customer,'mixed')
    assert parties.balance(customer)==500
    parties.pay(u,'customer',customer,100,'cash')
    assert parties.balance(customer)==400
    item=s.detail(inv)['items'][0]['id']
    s.refund(u,inv,[dict(item_id=item,qty=1000)],'cash')
    assert parties.balance(customer)==0
    assert db.rows('select stock from products')[0]['stock']==9000

def test_discount_tax_refunds_rounding_and_limits(sale_env):
    db,u,p=sale_env; s=Sales(db)
    inv=s.checkout(u,[dict(product_id=p,qty=3000)],100,1400,dict(cash=1600),None,'tax')
    assert s.detail(inv)['total']==1596
    item=s.detail(inv)['items'][0]['id']
    for _ in range(3): s.refund(u,inv,[dict(item_id=item,qty=1000)],'cash')
    assert sum(x['amount'] for x in db.rows('select amount from cash_moves'))==0
    assert db.rows('select stock from products')[0]['stock']==10000
    assert db.rows('select sum(total) total from returns')[0]['total']==1596
    with pytest.raises(ValueError): s.refund(u,inv,[dict(item_id=item,qty=1000)],'cash')

def test_disabled_product_rechecked_and_user_permissions(sale_env):
    db,u,p=sale_env
    with db.transaction() as c: c.execute('update products set active=0 where id=?',(p,))
    with pytest.raises(ValueError): Sales(db).checkout(u,[dict(product_id=p,qty=1000)],0,0,dict(cash=500),None,'disabled')
    with db.transaction() as c: c.execute('update users set active=0 where id=?',(u,))
    with pytest.raises(PermissionError): Sales(db).checkout(u,[dict(product_id=p,qty=1000)],0,0,dict(cash=500),None,'disabled-user')
