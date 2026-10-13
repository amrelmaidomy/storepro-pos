import pytest
from storepro.db import Database
from storepro.auth import Auth

@pytest.fixture
def env(tmp_path):
    db=Database(tmp_path/'store.db')
    uid=Auth(db).setup_admin('owner','Strong123!')
    with db.transaction() as c: c.execute('insert into shifts(actor,opening) values(?,0)',(uid,))
    return db,uid
