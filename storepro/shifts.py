from .auth import Auth
from .db import audit
from .finance import active_shift,cash_move
from .money import integer


class Shifts:
    def __init__(self,db): self.db=db; self.auth=Auth(db)

    def current(self):
        rows=self.db.rows('select * from shifts where closed is null')
        if not rows: return None
        shift=rows[0]
        shift['expected']=shift['opening']+self.db.rows('select coalesce(sum(amount),0) n from cash_moves where shift_id=?',(shift['id'],))[0]['n']
        return shift

    def open(self,actor,opening_cash):
        integer(opening_cash)
        with self.db.transaction() as c:
            self.auth.require(actor,'shift',c)
            if c.execute('select 1 from shifts where closed is null').fetchone(): raise ValueError('هناك وردية مفتوحة بالفعل')
            sid=c.execute('insert into shifts(actor,opening) values(?,?)',(actor,opening_cash)).lastrowid
            audit(c,actor,'shift_opened',sid)
            return sid

    def movement(self,actor,kind,amount,reason):
        integer(amount,1)
        if kind not in ('income','expense') or not reason.strip(): raise ValueError('اختر النوع وأدخل السبب')
        with self.db.transaction() as c:
            self.auth.require(actor,'manage',c)
            cash_move(c,actor,amount if kind=='income' else -amount,kind,reason,reason)
            audit(c,actor,'cash_movement',f'{kind}: {amount}; {reason}')

    def close(self,actor,counted_cash):
        integer(counted_cash)
        with self.db.transaction() as c:
            self.auth.require(actor,'shift',c)
            shift=active_shift(c)
            if actor!=shift['actor']: self.auth.require(actor,'manage',c)
            expected=shift['opening']+c.execute('select coalesce(sum(amount),0) from cash_moves where shift_id=?',(shift['id'],)).fetchone()[0]
            c.execute('update shifts set closed=CURRENT_TIMESTAMP,counted=?,expected=? where id=?',(counted_cash,expected,shift['id']))
            audit(c,actor,'shift_closed',f"{shift['id']}: {counted_cash-expected}")
            return dict(id=shift['id'],expected=expected,counted=counted_cash,difference=counted_cash-expected)
