from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

VERSION=1
SCHEMA='''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('Admin','Cashier')),active INTEGER NOT NULL DEFAULT 1,must_reset INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,barcode TEXT UNIQUE,name TEXT NOT NULL,category TEXT NOT NULL DEFAULT '',unit TEXT NOT NULL DEFAULT 'قطعة',cost INTEGER NOT NULL CHECK(cost>=0),price INTEGER NOT NULL CHECK(price>=0),stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock>=0),active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS parties(id INTEGER PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('customer','supplier')),name TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',address TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY,actor INTEGER NOT NULL REFERENCES users(id),opened TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,closed TEXT,opening INTEGER NOT NULL,counted INTEGER,expected INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_shift ON shifts((1)) WHERE closed IS NULL;
CREATE TABLE IF NOT EXISTS cash_moves(id INTEGER PRIMARY KEY,shift_id INTEGER NOT NULL REFERENCES shifts(id),actor INTEGER NOT NULL REFERENCES users(id),amount INTEGER NOT NULL,kind TEXT NOT NULL,reference TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,supplier_id INTEGER NOT NULL REFERENCES parties(id),actor INTEGER NOT NULL REFERENCES users(id),total INTEGER NOT NULL,paid INTEGER NOT NULL,request_id TEXT NOT NULL UNIQUE,date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY,purchase_id INTEGER NOT NULL REFERENCES purchases(id),product_id INTEGER NOT NULL REFERENCES products(id),name TEXT NOT NULL,qty INTEGER NOT NULL,returned INTEGER NOT NULL DEFAULT 0,price INTEGER NOT NULL,line_total INTEGER NOT NULL,refunded INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,number TEXT UNIQUE,actor INTEGER NOT NULL REFERENCES users(id),customer_id INTEGER REFERENCES parties(id),shift_id INTEGER REFERENCES shifts(id),subtotal INTEGER NOT NULL,discount INTEGER NOT NULL,tax INTEGER NOT NULL,total INTEGER NOT NULL,cash INTEGER NOT NULL,card INTEGER NOT NULL,credit INTEGER NOT NULL,change_amount INTEGER NOT NULL,request_id TEXT NOT NULL UNIQUE,date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,legacy INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),product_id INTEGER REFERENCES products(id),name TEXT NOT NULL,qty INTEGER NOT NULL,returned INTEGER NOT NULL DEFAULT 0,price INTEGER NOT NULL,cost INTEGER,line_total INTEGER NOT NULL,net_total INTEGER NOT NULL,tax INTEGER NOT NULL,refunded INTEGER NOT NULL DEFAULT 0,cost_returned INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS returns(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,source_id INTEGER NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),total INTEGER NOT NULL,method TEXT NOT NULL,date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS return_items(id INTEGER PRIMARY KEY,return_id INTEGER NOT NULL REFERENCES returns(id),item_id INTEGER NOT NULL,qty INTEGER NOT NULL,amount INTEGER NOT NULL,cost INTEGER,net_amount INTEGER NOT NULL DEFAULT 0,tax_amount INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS party_moves(id INTEGER PRIMARY KEY,party_id INTEGER NOT NULL REFERENCES parties(id),actor INTEGER NOT NULL REFERENCES users(id),amount INTEGER NOT NULL,kind TEXT NOT NULL,reference TEXT NOT NULL,date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS stock_moves(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),qty INTEGER NOT NULL,kind TEXT NOT NULL,reference TEXT NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER REFERENCES users(id),action TEXT NOT NULL,detail TEXT NOT NULL,date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
'''


class Database:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        c=self.connect()
        try:
            columns=[r['name'] for r in c.execute('pragma table_info(users)')]
            if 'password' in columns:
                backup=self.path.with_name(self.path.name+'.pre-migration-'+datetime.now().strftime('%Y%m%d%H%M%S%f'))
                with sqlite3.connect(backup) as target: c.backup(target)
                self._migrate(c)
            else:
                version=c.execute('pragma user_version').fetchone()[0]
                if version>VERSION: raise ValueError('قاعدة البيانات أحدث من البرنامج')
                c.executescript(SCHEMA)
                c.execute(f'pragma user_version={VERSION}')
                c.commit()
        finally: c.close()

    def connect(self):
        c=sqlite3.connect(self.path,timeout=15)
        c.row_factory=sqlite3.Row
        c.execute('pragma foreign_keys=ON')
        c.execute('pragma busy_timeout=15000')
        return c

    @contextmanager
    def transaction(self):
        c=self.connect()
        try:
            c.execute('begin immediate')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally: c.close()

    def rows(self,sql,args=()):
        c=self.connect()
        try: return [dict(r) for r in c.execute(sql,args)]
        finally: c.close()

    def _migrate(self,c):
        from .auth import hash_password
        from .money import parse_money
        tables=[r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
        try:
            c.execute('begin immediate')
            for table in tables:
                # Names originate from SQLite metadata and are quoted as identifiers.
                quoted=table.replace('"','""')
                c.execute(f'ALTER TABLE "{quoted}" RENAME TO "legacy_{quoted}"')
            for statement in SCHEMA.split(';'):
                if statement.strip(): c.execute(statement)
            for r in c.execute('select * from legacy_users').fetchall():
                c.execute('insert into users(id,username,password_hash,role,must_reset) values(?,?,?,?,?)',(r['id'],r['username'],hash_password(r['password']), 'Admin' if r['role']=='Admin' else 'Cashier',1))
            for r in c.execute('select * from legacy_products').fetchall():
                c.execute('insert into products(id,barcode,name,category,cost,price,stock,min_stock) values(?,?,?,?,?,?,?,?)',(r['id'],r['barcode'] or None,r['name'],r['category'] or '',parse_money(r['buy']),parse_money(r['sell']),int(r['stock'])*1000,int(r['min_stock'])*1000))
            actor=c.execute('select id from users order by id limit 1').fetchone()
            if 'sales' in tables and actor:
                for r in c.execute('select * from legacy_sales').fetchall():
                    total=parse_money(r['total']); discount=parse_money(r['discount'] or 0); tax=parse_money(r['tax'] or 0)
                    c.execute('insert into sales(id,number,actor,subtotal,discount,tax,total,cash,card,credit,change_amount,request_id,date,legacy) values(?,?,?,?,?,?,?,?,?,?,?,?,?,1)',(r['id'],f"OLD-{r['id']}",actor[0],total+discount-tax,discount,tax,total,total,0,0,0,f"legacy-{r['id']}",r['date']))
                if 'sale_items' in tables:
                    for r in c.execute('select * from legacy_sale_items').fetchall():
                        found=c.execute('select id from products where name=?',(r['product'],)).fetchall()
                        pid=found[0][0] if len(found)==1 else None
                        qty=int(r['qty'])*1000; price=parse_money(r['price']); line=price*int(r['qty'])
                        c.execute('insert into sale_items(id,sale_id,product_id,name,qty,price,cost,line_total,net_total,tax) values(?,?,?,?,?,?,NULL,?,?,0)',(r['id'],r['sale_id'],pid,r['product'],qty,price,line,line))
            # Remove plaintext credentials from the migrated DB, retaining pre-migration backup for recovery.
            c.execute('drop table legacy_users')
            c.execute(f'pragma user_version={VERSION}')
            c.commit()
        except BaseException:
            c.rollback()
            raise


def audit(c,actor,action,detail):
    c.execute('insert into audit(actor,action,detail) values(?,?,?)',(actor,action,str(detail)))
