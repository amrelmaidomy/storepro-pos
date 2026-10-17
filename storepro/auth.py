import hashlib
import hmac
import secrets
from .db import audit


def hash_password(password):
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'


def verify_password(password,encoded):
    try:
        algorithm,iterations,salt,digest=encoded.split('$')
        if algorithm!='pbkdf2_sha256': return False
        check=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations)).hex()
        return hmac.compare_digest(check,digest)
    except (ValueError,TypeError): return False


def validate_password(password):
    if len(password)<8 or len(password)>128: raise ValueError('كلمة المرور من 8 إلى 128 حرفًا')


class Auth:
    def __init__(self,db): self.db=db

    def setup_admin(self,username,password):
        validate_password(password)
        if not username.strip(): raise ValueError('اسم المستخدم مطلوب')
        with self.db.transaction() as c:
            if c.execute('select 1 from users').fetchone(): raise ValueError('تم إنشاء المدير بالفعل')
            uid=c.execute("insert into users(username,password_hash,role) values(?,?,'Admin')",(username.strip(),hash_password(password))).lastrowid
            audit(c,uid,'setup','first administrator')
            return uid

    def login(self,username,password):
        users=self.db.rows('select * from users where username=? and active=1',(username.strip(),))
        if not users or not verify_password(password,users[0]['password_hash']): raise ValueError('اسم المستخدم أو كلمة المرور غير صحيحة')
        return users[0]['id']

    def require(self,actor,permission,c=None):
        if c is None:
            rows=self.db.rows('select * from users where id=?',(actor,))
            user=rows[0] if rows else None
        else: user=c.execute('select * from users where id=?',(actor,)).fetchone()
        if not user or not user['active']: raise PermissionError('الحساب غير نشط')
        if user['must_reset']: raise PermissionError('غيّر كلمة المرور القديمة قبل المتابعة')
        if user['role']!='Admin' and permission not in ('sell','view','shift'):
            raise PermissionError('هذه العملية تحتاج صلاحية المدير')

    def change_password(self,actor,old,new):
        validate_password(new)
        with self.db.transaction() as c:
            user=c.execute('select * from users where id=? and active=1',(actor,)).fetchone()
            if not user or not verify_password(old,user['password_hash']): raise ValueError('كلمة المرور الحالية غير صحيحة')
            c.execute('update users set password_hash=?,must_reset=0 where id=?',(hash_password(new),actor))
            audit(c,actor,'password_changed','self')

    def save_user(self,actor,uid,username,password,role,active):
        if role not in ('Admin','Cashier') or not username.strip(): raise ValueError('بيانات المستخدم غير صحيحة')
        if password: validate_password(password)
        with self.db.transaction() as c:
            self.require(actor,'manage',c)
            if uid:
                previous=c.execute('select * from users where id=?',(uid,)).fetchone()
                if not previous: raise ValueError('المستخدم غير موجود')
                if previous['role']=='Admin' and previous['active'] and (role!='Admin' or not active):
                    if c.execute("select count(*) from users where role='Admin' and active=1").fetchone()[0]<=1: raise ValueError('لا يمكن تعطيل آخر مدير')
                c.execute('update users set username=?,role=?,active=? where id=?',(username.strip(),role,int(active),uid))
                if password: c.execute('update users set password_hash=?,must_reset=0 where id=?',(hash_password(password),uid))
            else:
                validate_password(password)
                uid=c.execute('insert into users(username,password_hash,role,active) values(?,?,?,?)',(username.strip(),hash_password(password),role,int(active))).lastrowid
            audit(c,actor,'user_saved',uid)
            return uid
