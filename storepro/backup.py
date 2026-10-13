from datetime import datetime
from pathlib import Path
import os
import sqlite3
import tempfile
from .db import VERSION,audit
from .auth import Auth


class Backup:
    def __init__(self,db): self.db=db

    def export(self,actor,destination):
        Auth(self.db).require(actor,'manage')
        return self.create(destination)

    def create(self,destination):
        destination=Path(destination)
        if destination.resolve()==self.db.path.resolve(): raise ValueError('لا تستخدم قاعدة التشغيل كوجهة للنسخ')
        destination.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='backup-',suffix='.db',dir=destination.parent); os.close(fd)
        source=self.db.connect()
        try:
            with sqlite3.connect(tmp) as target: source.backup(target)
            self.validate(tmp)
            os.replace(tmp,destination)
        finally:
            source.close()
            if Path(tmp).exists(): Path(tmp).unlink()
        return destination

    def validate(self,path):
        path=Path(path)
        if not path.is_file(): raise ValueError('ملف النسخة غير موجود')
        try:
            c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                if c.execute('pragma integrity_check').fetchone()[0]!='ok': raise ValueError('النسخة تالفة')
                if c.execute('pragma user_version').fetchone()[0]!=VERSION: raise ValueError('إصدار النسخة غير متوافق')
                if c.execute('pragma foreign_key_check').fetchone(): raise ValueError('علاقات النسخة غير سليمة')
                required={'users','products','sales','sale_items','purchases','purchase_items','stock_moves','shifts','cash_moves','parties','party_moves','returns','return_items','settings','audit'}
                tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
                if not required.issubset(tables): raise ValueError('هذا ليس ملف StorePro كاملًا')
                # Validate columns as well as version; a renamed unrelated SQLite DB is not sufficient.
                live=self.db.connect()
                try:
                    for table in required:
                        expected={r['name'] for r in live.execute(f'pragma table_info({table})')}
                        actual={r[1] for r in c.execute(f'pragma table_info({table})')}
                        if not expected.issubset(actual): raise ValueError('مخطط النسخة غير متوافق')
                finally: live.close()
            finally: c.close()
        except sqlite3.DatabaseError as e: raise ValueError('ملف قاعدة بيانات غير صالح') from e

    def restore(self,actor,path):
        Auth(self.db).require(actor,'manage')
        path=Path(path)
        if path.resolve()==self.db.path.resolve(): raise ValueError('اختر نسخة مختلفة عن قاعدة التشغيل')
        self.validate(path)
        stamp=datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.create(self.db.path.with_name(self.db.path.name+'.before-restore-'+stamp))
        # No persistent DB connections are held by services; build a clean DB before atomic replacement.
        fd,temp=tempfile.mkstemp(prefix='restore-',suffix='.db',dir=self.db.path.parent); os.close(fd)
        try:
            source=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                with sqlite3.connect(temp) as target: source.backup(target)
            finally: source.close()
            self.validate(temp)
            os.replace(temp,self.db.path)
            with self.db.transaction() as c:
                found=c.execute('select id from users where id=?',(actor,)).fetchone()
                audit(c,actor if found else None,'database_restored',path.name)
        finally:
            if Path(temp).exists(): Path(temp).unlink()

    def automatic(self,directory,keep=10):
        if type(keep) is not int or not 1<=keep<=100: raise ValueError('عدد النسخ بين 1 و100')
        directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
        path=directory/('storepro-'+datetime.now().strftime('%Y%m%d-%H%M%S%f')+'.db')
        self.create(path)
        for old in sorted(directory.glob('storepro-*.db'),key=lambda p:p.name,reverse=True)[keep:]: old.unlink()
        return path
