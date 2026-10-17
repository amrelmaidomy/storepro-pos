import sqlite3
import pytest
from storepro.db import Database
from storepro.money import parse_money, parse_quantity
from storepro.auth import Auth

@pytest.fixture
def db(tmp_path):
    return Database(tmp_path/'db.sqlite')

@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '1.001', 'abc'])
def test_money_rejects_invalid(value):
    with pytest.raises(ValueError): parse_money(value)

def test_fixed_precision():
    assert parse_money('12.34') == 1234
    assert parse_quantity('1.250') == 1250
    with pytest.raises(ValueError): parse_quantity('0')

def test_setup_auth_and_permission(db):
    a=Auth(db)
    assert db.rows('select * from users') == []
    uid=a.setup_admin('owner','Strong123!')
    assert a.login('owner','Strong123!') == uid
    with pytest.raises(ValueError): a.login('owner','wrong')
    assert db.rows('select password_hash from users')[0]['password_hash'] != 'Strong123!'
    cashier=a.save_user(uid, None, 'cashier', 'Cashier123!', 'Cashier', True)
    with pytest.raises(PermissionError): a.require(cashier,'manage')
    with db.transaction() as c: c.execute('update users set active=0 where id=?',(cashier,))
    with pytest.raises(PermissionError): a.require(cashier,'sell')
    with pytest.raises(ValueError): a.setup_admin('other','Strong123!')

def test_transaction_rolls_back(db):
    with pytest.raises(RuntimeError):
        with db.transaction() as c:
            c.execute("insert into settings(key,value) values('x','1')")
            raise RuntimeError()
    assert not db.rows("select * from settings where key='x'")

def test_foreign_keys(db):
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as c:
            c.execute("insert into stock_moves(product_id,qty,kind,reference,actor) values(999,1000,'adjust','x',999)")

def test_legacy_migration(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as c:
        c.executescript("create table users(id integer primary key,username text,password text,role text); insert into users values(1,'admin','1234','Admin'); create table products(id integer primary key,barcode text,name text,category text,buy real,sell real,stock integer,min_stock integer); insert into products values(1,'a','قديم','عام',2.5,5,3,1); create table sales(id integer primary key,date text,total real,discount real,tax real); insert into sales values(1,'2026-01-01',5,0,0); create table sale_items(id integer primary key,sale_id integer,product text,qty integer,price real); insert into sale_items values(1,1,'قديم',1,5); create table cashflow(id integer primary key,type text,description text,amount real,date text);")
    db=Database(path)
    assert Auth(db).login('admin','1234') == 1
    assert db.rows('select must_reset from users')[0]['must_reset']==1
    assert db.rows('select stock,cost from products')[0] == {'stock':3000,'cost':250}
    assert db.rows('select total from sales')[0]['total']==500
    assert list(tmp_path.glob('*.pre-migration-*'))

@pytest.mark.parametrize('value',['1.000000000000000000000000000001','0.999999999999999999999999999999','1e1000000','1e-1000000'])
def test_exact_precision_without_decimal_context_rounding(value):
    with pytest.raises(ValueError): parse_money(value)

def test_legacy_duplicate_barcodes_are_preserved_without_ambiguous_search(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as c:
        c.executescript("create table users(id integer primary key,username text,password text,role text); insert into users values(1,'admin','1234','Admin'); create table products(id integer primary key,barcode text,name text,category text,buy real,sell real,stock integer,min_stock integer); insert into products values(1,'same','a','',1,2,3,0); insert into products values(2,'same','b','',1,2,3,0);")
    db=Database(path)
    assert len(db.rows('select * from products'))==2
    assert db.rows('select barcode from products order by id')==[{'barcode':'same'},{'barcode':None}]
    assert db.rows('select barcode from legacy_products where id=2')[0]['barcode']=='same'
    assert '2' in db.rows("select value from settings where key='migration_notice'")[0]['value']
