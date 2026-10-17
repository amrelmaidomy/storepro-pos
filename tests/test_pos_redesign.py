import os
import pytest
from storepro.ui.app import App
from storepro.auth import Auth
from storepro.catalog import Catalog
from storepro.shifts import Shifts
from storepro.sales import Sales

pytestmark=pytest.mark.skipif(os.name!='nt' and not os.environ.get('DISPLAY'),reason='Requires display')

@pytest.fixture
def shop(tmp_path):
    app=App(tmp_path); app.withdraw()
    u=app.auth.setup_admin('owner','Strong123!'); app.sign_in('owner','Strong123!')
    cat=Catalog(app.db)
    p=cat.save_product(u,dict(name='قهوة',category='مشروبات',cost=1200,price=2500,unit='كجم'))
    q=cat.save_product(u,dict(name='سكر',category='بقالة',cost=500,price=1000))
    cat.adjust(u,p,5000,'initial'); cat.adjust(u,q,4000,'initial')
    Shifts(app.db).open(u,0)
    app.show('pos'); app.update()
    yield app,p,q
    app.destroy()

def test_catalog_cards_filter_and_search(shop):
    app,p,q=shop; page=app.page
    assert set(page.product_cards)=={p,q}
    page.select_category('مشروبات')
    assert set(page.product_cards)=={p}
    page.select_category(None); page.query.set('سكر'); page.search()
    assert set(page.product_cards)=={q}

def test_inline_quantity_totals_and_remove(shop):
    app,p,q=shop; page=app.page
    page.add_product(p,1000)
    page.change_quantity(p,1000)
    assert page.cart[p]['qty']==2000 and page.totals()==5000
    page.change_quantity(p,-1000)
    assert page.totals()==2500
    page.set_quantity(p,'0.250')
    assert page.cart[p]['qty']==250 and page.totals()==625
    with pytest.raises(ValueError): page.set_quantity(p,'6')
    assert page.cart[p]['qty']==250
    page.remove_product(p)
    assert not page.cart and page.empty_cart.winfo_exists()

def test_checkout_defaults_to_exact_cash_and_calculates_change(shop):
    app,p,q=shop; page=app.page; page.add_product(p,1000)
    dialog=page.open_payment(); app.update()
    assert dialog.cash.get()=='25.00'
    dialog.cash.set('30.00'); dialog.recalculate()
    assert dialog.change_amount==500
    sale_id=dialog.submit()
    sale=Sales(app.db).detail(sale_id)
    assert sale['total']==2500 and sale['change_amount']==500
    assert not page.cart

def test_card_checkout_and_cancel_preserve_cart(shop):
    app,p,q=shop; page=app.page; page.add_product(p,1000)
    dialog=page.open_payment(); dialog.choose_method('بطاقة')
    assert dialog.card.get()=='25.00' and dialog.cash.get()=='0'
    dialog.destroy()
    assert page.cart[p]['qty']==1000 and not app.db.rows('select * from sales')
    dialog=page.open_payment(); dialog.choose_method('بطاقة'); sid=dialog.submit()
    assert Sales(app.db).detail(sid)['card']==2500

def test_cart_survives_navigation_but_not_logout(shop):
    app,p,q=shop; app.page.add_product(p,1000)
    app.show('products'); app.show('pos')
    assert p in app.page.cart
    app.logout(); app.sign_in('owner','Strong123!')
    assert not app.page.cart

def test_no_shift_offers_opening_instead_of_broken_checkout(shop):
    app,p,q=shop; Shifts(app.db).close(app.actor,0)
    page=app.page; page.add_product(p,1000)
    dialog=page.open_payment()
    assert dialog.needs_shift
    dialog.open_shift('100')
    assert not dialog.needs_shift
    assert Shifts(app.db).current()['opening']==10000
    dialog.destroy()

@pytest.mark.parametrize('size',['1360x900','1060x780'])
def test_payment_button_fits_at_supported_sizes(shop,size):
    app,p,q=shop; app.deiconify(); app.geometry(size); app.update()
    page=app.page
    assert page.pay_button.winfo_ismapped()
    assert page.pay_button.winfo_rooty()+page.pay_button.winfo_height()<=app.winfo_rooty()+app.winfo_height()
    assert page.product_area.winfo_width()>=300
    assert page.invoice_panel.winfo_width()>=300

def test_display_table_uses_normal_units_preserves_source_values(shop):
    from storepro.ui.forms import Table
    app,p,q=shop
    table=Table(app,['price','stock'])
    table.load([{'price':1250,'stock':1500}])
    assert table.tree.item('0','values')==('12.50','1.5')
    table.tree.selection_set('0')
    assert table.selected()=={'price':1250,'stock':1500}

def test_saved_cart_uses_updated_product_price_after_navigation(shop):
    app,p,q=shop; app.page.add_product(p,1000)
    app.show('products')
    row=app.db.rows('select * from products where id=?',(p,))[0]
    Catalog(app.db).save_product(app.actor,dict(row,price=3000))
    app.show('pos')
    assert app.page.totals()==3000
    payment=app.page.open_payment()
    assert payment.cash.get()=='30.00'
    payment.destroy()

def test_mixed_checkout_and_duplicate_submit(shop):
    app,p,q=shop; app.page.add_product(p,1000)
    dialog=app.page.open_payment(); dialog.choose_method('مختلط')
    dialog.cash.set('10'); dialog.card.set('15'); dialog.recalculate()
    sid=dialog.submit()
    assert dialog.submit()==sid
    sale=Sales(app.db).detail(sid)
    assert sale['cash']==1000 and sale['card']==1500
    assert len(app.db.rows('select * from sales'))==1

def test_credit_checkout_requires_customer(shop):
    from storepro.parties import Parties
    app,p,q=shop; customer=Parties(app.db).save(app.actor,'customer',dict(name='عميل'))
    app.show('pos'); app.page.add_product(p,1000)
    dialog=app.page.open_payment(); dialog.choose_method('آجل')
    with pytest.raises(ValueError): dialog.submit()
    dialog.customer.set(f'{customer} — عميل')
    sid=dialog.submit()
    assert Sales(app.db).detail(sid)['credit']==2500
    assert Parties(app.db).balance(customer)==2500

def test_details_discount_and_tax_are_automatic(shop):
    app,p,q=shop; page=app.page; page.add_product(p,1000)
    page.toggle_details(); page.discount.set('5'); page.tax.set('14'); page.update_totals()
    assert page.totals()==2280
    payment=page.open_payment()
    assert payment.cash.get()=='22.80'
    sid=payment.submit()
    sale=Sales(app.db).detail(sid)
    assert sale['discount']==500 and sale['tax']==280 and sale['total']==2280

@pytest.mark.parametrize('route',['card','barcode'])
def test_fractional_remaining_stock_can_enter_invoice(shop,monkeypatch,route):
    from storepro.ui.forms import Button
    app,p,q=shop
    Catalog(app.db).adjust(app.actor,p,-4500,'stock now half kilogram')
    app.show('pos'); page=app.page
    monkeypatch.setattr('tkinter.messagebox.showerror',lambda *args:None)
    if route=='card':
        action=next(w for w in page.product_cards[p].winfo_children() if isinstance(w,Button))
        action.invoke()
    else:
        page.query.set(str(p)); page.search(True)
    assert page.cart[p]['qty']==500
    assert page.totals()==1250

def test_quantity_buttons_keep_all_three_decimal_places(shop):
    from storepro.money import quantity_text
    app,p,q=shop
    Catalog(app.db).adjust(app.actor,p,2000000,'large stock')
    page=app.page; page.add_product(p,999999)
    assert quantity_text(999999)=='999.999'
    page.change_quantity(p,1000)
    assert page.cart[p]['qty']==1000999
    assert quantity_text(page.cart[p]['qty'])=='1000.999'
    page.change_quantity(p,-1000)
    assert page.cart[p]['qty']==999999

def test_clicking_product_name_adds_it_to_invoice(shop):
    from storepro.ui.forms import Label,rtl
    app,p,q=shop; app.deiconify(); app.update()
    page=app.page
    name=next(w for w in page.product_cards[p].winfo_children() if isinstance(w,Label) and w.cget('text')==rtl('قهوة'))
    name._label.event_generate('<Button-1>'); app.update()
    assert page.cart[p]['qty']==1000

def test_scaling_after_navigation_does_not_call_destroyed_dropdown(tmp_path):
    import subprocess,sys
    code='''
import sys
from pathlib import Path
import customtkinter as ctk
from storepro.ui.app import App
app=App(Path(sys.argv[1]))
app.auth.setup_admin('owner','Strong123!')
app.sign_in('owner','Strong123!')
app.show('products'); app.show('pos'); app.update()
ctk.set_widget_scaling(1.25); app.update()
assert app.page.pay_button.winfo_ismapped()
ctk.set_widget_scaling(1.0); app.update()
app.destroy()
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path/'dpi')],capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stderr
