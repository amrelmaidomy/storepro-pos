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

def test_checkout_controls_fit_window(tmp_path):
    app=App(tmp_path); app.geometry('1360x900')
    app.auth.setup_admin('o','Strong123!'); app.sign_in('o','Strong123!'); app.update()
    page=app.page
    assert page.cash.winfo_rooty()+page.cash.winfo_height() < app.winfo_rooty()+app.winfo_height()
    assert page.total_label.winfo_ismapped()
    assert page.total_label.winfo_rooty()+page.total_label.winfo_height() < app.winfo_rooty()+app.winfo_height()
    app.destroy()

def test_arabic_display_preserves_logical_choices(tmp_path):
    from storepro.ui.forms import Field,rtl
    assert rtl('نقطة البيع') != 'نقطة البيع'
    assert rtl('StorePro 123') == 'StorePro 123'
    app=App(tmp_path); app.withdraw()
    field=Field(app,'الطريقة','نقدي',['نقدي','بطاقة'])
    assert field.get()=='نقدي'
    field.set('بطاقة')
    assert field.get()=='بطاقة'
    app.destroy()

def test_barcode_takes_priority_over_numeric_id(tmp_path):
    app=App(tmp_path); app.withdraw(); u=app.auth.setup_admin('o','Strong123!'); app.sign_in('o','Strong123!')
    a=Catalog(app.db).save_product(u,dict(name='A',barcode='different',cost=0,price=100))
    b=Catalog(app.db).save_product(u,dict(name='Z',barcode=str(a),cost=0,price=100))
    app.page.query.set(str(a)); app.page.search(True)
    assert list(app.page.cart)==[b]
    app.destroy()

@pytest.mark.parametrize('page_key,action',[('settings','backup'),('reports','refresh'),('reports','export'),('products','refresh'),('customer','refresh'),('supplier','refresh'),('users','refresh'),('purchases','refresh')])
def test_stale_admin_page_cannot_read_or_export(tmp_path,monkeypatch,page_key,action):
    app=App(tmp_path); app.withdraw(); u=app.auth.setup_admin('o','Strong123!'); app.sign_in('o','Strong123!')
    other=app.auth.save_user(u,None,'other','Strong123!','Admin',True)
    app.show(page_key); page=app.page
    monkeypatch.setattr(page,'notify',lambda text:None)
    app.auth.save_user(other,u,'o','','Cashier',True)
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename',lambda **kw:str(tmp_path/'leak.db'))
    with pytest.raises(PermissionError): getattr(page,action)()
    assert not (tmp_path/'leak.db').exists()
    app.destroy()
