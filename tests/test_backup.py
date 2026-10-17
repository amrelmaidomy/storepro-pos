import sqlite3
import pytest
from storepro.backup import Backup
from storepro.catalog import Catalog

def test_backup_restore_and_reject_corrupt(env,tmp_path):
    db,u=env; cat=Catalog(db); cat.save_product(u,dict(name='أصل',cost=0,price=100))
    backup=Backup(db); target=backup.create(tmp_path/'backup.db')
    cat.save_product(u,dict(name='جديد',cost=0,price=100))
    backup.restore(u,target)
    assert [p['name'] for p in cat.search()]==['أصل']
    broken=tmp_path/'broken.db'; broken.write_text('not sqlite')
    with pytest.raises(ValueError): backup.restore(u,broken)
    assert len(cat.search())==1
    future=tmp_path/'future.db'
    with sqlite3.connect(future) as c: c.execute('pragma user_version=999')
    with pytest.raises(ValueError): backup.restore(u,future)
    with pytest.raises(ValueError): backup.create(db.path)
    assert list(tmp_path.glob('store.db.before-restore-*'))
