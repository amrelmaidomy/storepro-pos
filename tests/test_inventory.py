import pytest
from storepro.catalog import Catalog
from storepro.purchases import Purchases
from storepro.parties import Parties

def product(cat,uid,**kwargs):
    return cat.save_product(uid,dict(name='سكر',barcode='100',cost=200,price=500,min_stock=1000,**kwargs))

def test_catalog_validation_search_and_adjust(env):
    db,u=env; cat=Catalog(db); p=product(cat,u)
    assert cat.search('سكر')[0]['id']==p
    assert cat.search('100')[0]['id']==p
    with pytest.raises(ValueError): product(cat,u)
    cat.save_product(u,dict(name='بدون باركود',barcode='',cost=0,price=100,min_stock=0))
    cat.save_product(u,dict(name='بدون باركود 2',barcode='',cost=0,price=100,min_stock=0))
    cat.adjust(u,p,1500,'جرد')
    assert db.rows('select stock from products where id=?',(p,))[0]['stock']==1500
    with pytest.raises(ValueError): cat.adjust(u,p,-2000,'جرد')
    assert len(db.rows('select * from stock_moves'))==1
    with pytest.raises(ValueError): cat.save_product(u,dict(name='',cost=0,price=-1))

def test_purchase_cost_balance_and_idempotency(env):
    db,u=env; cat=Catalog(db); p=product(cat,u); parties=Parties(db)
    supplier=parties.save(u,'supplier',dict(name='مورد'))
    purchases=Purchases(db)
    args=(u,supplier,[dict(product_id=p,qty=2000,price=300)],dict(cash=100,card=100),'req')
    invoice=purchases.receive(*args)
    assert purchases.receive(*args)==invoice
    assert db.rows('select stock,cost from products')[0]==dict(stock=2000,cost=300)
    assert parties.balance(supplier)==400
    parties.pay(u,'supplier',supplier,100,'cash')
    assert parties.balance(supplier)==300
    cat.adjust(u,p,1000,'جرد')
    purchases.receive(u,supplier,[dict(product_id=p,qty=1000,price=500)],dict(cash=0,card=0),'req2')
    assert db.rows('select cost from products')[0]['cost']==350
    assert sum(x['amount'] for x in db.rows('select amount from cash_moves'))==-200

def test_purchase_returns_and_limits(env):
    db,u=env; cat=Catalog(db); p=product(cat,u); parties=Parties(db)
    supplier=parties.save(u,'supplier',dict(name='مورد'))
    pur=Purchases(db); inv=pur.receive(u,supplier,[dict(product_id=p,qty=3000,price=200)],dict(cash=600,card=0),'a')
    item=db.rows('select id from purchase_items')[0]['id']
    pur.return_items(u,inv,[dict(item_id=item,qty=1000)],'cash')
    assert db.rows('select stock from products')[0]['stock']==2000
    assert sum(x['amount'] for x in db.rows('select amount from cash_moves'))==-400
    with pytest.raises(ValueError): pur.return_items(u,inv,[dict(item_id=item,qty=3000)],'cash')
    cat.adjust(u,p,-2000,'جرد')
    with pytest.raises(ValueError): pur.return_items(u,inv,[dict(item_id=item,qty=1000)],'cash')

def test_party_payments_cannot_overpay(env):
    db,u=env; parties=Parties(db); customer=parties.save(u,'customer',dict(name='عميل'))
    with pytest.raises(ValueError): parties.pay(u,'customer',customer,100,'cash')
