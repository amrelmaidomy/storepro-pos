from .auth import Auth
from .db import audit
from .finance import valid_party,party_balance,party_move,cash_move
from .money import integer


class Parties:
    def __init__(self,db): self.db=db; self.auth=Auth(db)

    def save(self,actor,kind,fields):
        if kind not in ('customer','supplier') or not str(fields.get('name','')).strip(): raise ValueError('الاسم والنوع مطلوبان')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            pid=fields.get('id'); values=(str(fields['name']).strip(),str(fields.get('phone','')),str(fields.get('address','')),int(bool(fields.get('active',True))))
            if pid:
                if not c.execute('select 1 from parties where id=? and kind=?',(pid,kind)).fetchone(): raise ValueError('الحساب غير موجود')
                c.execute('update parties set name=?,phone=?,address=?,active=? where id=?',values+(pid,))
            else: pid=c.execute('insert into parties(name,phone,address,active,kind) values(?,?,?,?,?)',values+(kind,)).lastrowid
            audit(c,actor,'party_saved',pid)
            return pid

    def list(self,kind):
        return self.db.rows('select p.*,coalesce(sum(m.amount),0) balance from parties p left join party_moves m on m.party_id=p.id where p.kind=? group by p.id order by p.name',(kind,))

    def balance(self,pid):
        return self.db.rows('select coalesce(sum(amount),0) balance from party_moves where party_id=?',(pid,))[0]['balance']

    def pay(self,actor,kind,party_id,amount,method):
        integer(amount,1)
        if method not in ('cash','card'): raise ValueError('طريقة الدفع غير صحيحة')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            valid_party(c,party_id,kind)
            if amount>party_balance(c,party_id): raise ValueError('المبلغ أكبر من المستحق')
            party_move(c,actor,party_id,-amount,'payment',party_id)
            if method=='cash': cash_move(c,actor,amount if kind=='customer' else -amount,'party_payment',party_id)
            audit(c,actor,'party_payment',f'{party_id}: {amount}')
