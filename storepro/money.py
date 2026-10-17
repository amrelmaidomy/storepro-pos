from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _parse(text, scale, positive=False):
    try:
        raw=str(text).strip()
        if len(raw)>128: raise ValueError('الرقم أطول من المسموح')
        value=Decimal(raw)
        if not value.is_finite() or value<0 or value>Decimal(10**12//scale):
            raise ValueError('قيمة غير صحيحة أو أكبر من المسموح')
        digits=list(value.as_tuple().digits); exponent=value.as_tuple().exponent
        while digits and digits[-1]==0:
            digits.pop(); exponent+=1
        if not digits:
            if positive: raise ValueError('الكمية يجب أن تكون أكبر من صفر')
            return 0
        places=2 if scale==100 else 3
        if exponent < -places: raise ValueError('دقة أكبر من المسموح')
        # Build the exact integer from the coefficient; Decimal multiplication could round long input.
        coefficient=int(''.join(str(d) for d in digits))
        result=coefficient*10**(exponent+places)
        if positive and result==0: raise ValueError('الكمية يجب أن تكون أكبر من صفر')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('أدخل رقمًا صحيحًا') from None


def parse_money(text): return _parse(text,100)
def parse_quantity(text): return _parse(text,1000,True)
def parse_quantity_zero(text): return _parse(text,1000)
def amount(price,quantity): return (price*quantity+500)//1000
def formatted(value): return f'{value/100:.2f}'
def quantity_text(value):
    sign='-' if value<0 else ''
    whole,fraction=divmod(abs(int(value)),1000)
    suffix=('.'+str(fraction).zfill(3).rstrip('0')) if fraction else ''
    return f'{sign}{whole}{suffix}'

def integer(value, minimum=0):
    if type(value) is not int or value<minimum or value>10**12: raise ValueError('قيمة غير صحيحة')
    return value
