from storepro.reports import Reports
from storepro.catalog import Catalog
from storepro.sales import Sales
from storepro.exports import export_rows,render_receipt
from openpyxl import load_workbook

def test_report_historical_cost_and_returns(env,tmp_path):
    db,u=env; cat=Catalog(db); p=cat.save_product(u,dict(name='سكر',cost=200,price=500))
    cat.adjust(u,p,2000,'initial')
    sales=Sales(db); inv=sales.checkout(u,[dict(product_id=p,qty=2000)],0,1400,dict(cash=1140),None,'a')
    with db.transaction() as c: c.execute('update products set cost=900 where id=?',(p,))
    item=sales.detail(inv)['items'][0]['id']
    sales.refund(u,inv,[dict(item_id=item,qty=1000)],'cash')
    report=Reports(db).summary('2000-01-01','2099-01-01')
    assert report['net_sales']==500 and report['tax']==70 and report['profit']==300
    assert report['refunds']==570 and report['sales']==1140
    assert Reports(db).summary('2000-01-01','2000-01-02')['sales']==0
    assert Reports(db).table('products','2000-01-01','2099-01-01')[0]['name']=='سكر'
    rows=[{'اسم':'سكر','قيمة':'=1+1'}]
    for ext in ('csv','xlsx','pdf'):
        path=tmp_path/f'report.{ext}'; export_rows(rows,path)
        assert path.stat().st_size>0
        if ext=='csv': assert 'سكر' in path.read_text(encoding='utf-8-sig')
    book=load_workbook(tmp_path/'report.xlsx')
    assert book.active['B2'].data_type=='s'
    path=render_receipt(sales.detail(inv),tmp_path/'receipt.html',58)
    text=path.read_text()
    assert 'سكر' in text and 'SP-' in text and '58mm' in text
