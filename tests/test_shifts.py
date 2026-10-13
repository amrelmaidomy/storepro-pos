import pytest
from storepro.shifts import Shifts
from storepro.auth import Auth
from storepro.catalog import Catalog
from storepro.sales import Sales

def test_shift_expected_and_ownership(env):
    db,u=env; shifts=Shifts(db)
    shifts.movement(u,'income',10000,'إيداع')
    shifts.movement(u,'expense',2000,'مصروف')
    with pytest.raises(ValueError): shifts.open(u,100)
    cashier=Auth(db).save_user(u,None,'c','Strong123!','Cashier',True)
    with pytest.raises(PermissionError): shifts.close(cashier,8000)
    result=shifts.close(u,7900)
    assert result['expected']==8000 and result['difference']==-100
    shifts.open(cashier,5000)
    with pytest.raises(PermissionError): shifts.movement(cashier,'expense',100,'x')
    assert shifts.close(cashier,5000)['difference']==0

def test_sale_requires_open_shift(env):
    db,u=env; Shifts(db).close(u,0)
    p=Catalog(db).save_product(u,dict(name='x',cost=0,price=0))
    Catalog(db).adjust(u,p,1000,'initial')
    with pytest.raises(ValueError): Sales(db).checkout(u,[dict(product_id=p,qty=1000)],0,0,dict(cash=0),None,'no-shift')
