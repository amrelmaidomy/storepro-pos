import os
import pytest
from storepro.ui.app import App
from storepro.catalog import Catalog
from storepro.shifts import Shifts
from storepro.sales import Sales
from storepro.auth import Auth

pytestmark=pytest.mark.skipif(os.name!='nt' and not os.environ.get('DISPLAY'),reason='Requires a display')

def test_app_setup_navigation_and_checkout(tmp_path):
    app=App(tmp_path); app.withdraw()
    assert app.actor is None
    uid=app.auth.setup_admin('owner','Strong123!')
    app.sign_in('owner','Strong123!')
    Shifts(app.db).open(uid,0)
    p=Catalog(app.db).save_product(uid,dict(name='سكر',barcode='100',cost=200,price=500))
    Catalog(app.db).adjust(uid,p,2000,'initial')
    app.show('pos'); app.update()
    page=app.page
    page.add_product(p,1000)
    page.cash.delete(0,'end'); page.cash.insert(0,'5.00')
    invoice=page.complete()
    assert Sales(app.db).detail(invoice)['total']==500
    for key in ('products','customer','supplier','purchases','sales','finance','reports','users','settings'):
        app.show(key); app.update()
        assert app.page is not None
    cashier=Auth(app.db).save_user(uid,None,'cashier','Cashier123!','Cashier',True)
    app.sign_in('cashier','Cashier123!')
    with pytest.raises(PermissionError): app.show('users')
    app.destroy()

def test_cart_invalid_quantity_leaves_stock_unchanged(tmp_path):
    app=App(tmp_path); app.withdraw()
    uid=app.auth.setup_admin('o','Strong123!'); app.sign_in('o','Strong123!')
    p=Catalog(app.db).save_product(uid,dict(name='x',cost=0,price=100))
    app.show('pos')
    with pytest.raises(ValueError): app.page.add_product(p,0)
    assert not app.page.cart
    app.destroy()
