from .money import integer


def active_shift(c):
    shift=c.execute('select * from shifts where closed is null').fetchone()
    if not shift: raise ValueError('افتح وردية أولًا')
    return shift


def cash_move(c,actor,amount,kind,reference,description=''):
    if not amount: return
    shift=active_shift(c)
    c.execute('insert into cash_moves(shift_id,actor,amount,kind,reference,description) values(?,?,?,?,?,?)',(shift['id'],actor,amount,kind,str(reference),description))


def party_balance(c,pid):
    return c.execute('select coalesce(sum(amount),0) from party_moves where party_id=?',(pid,)).fetchone()[0]


def party_move(c,actor,pid,value,kind,reference):
    if value: c.execute('insert into party_moves(party_id,actor,amount,kind,reference) values(?,?,?,?,?)',(pid,actor,value,kind,str(reference)))


def valid_party(c,pid,kind):
    row=c.execute('select * from parties where id=? and kind=? and active=1',(pid,kind)).fetchone()
    if not row: raise ValueError('اختر عميلًا أو موردًا نشطًا صحيحًا')
    return row


def payment_values(payments):
    if set(payments)-{'cash','card','credit'}: raise ValueError('طريقة دفع غير صحيحة')
    return tuple(integer(payments.get(k,0)) for k in ('cash','card','credit'))
