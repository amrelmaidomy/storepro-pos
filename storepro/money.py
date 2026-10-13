from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _parse(text, scale, positive=False):
    try:
        value=Decimal(str(text).strip())
        scaled=value*scale
        if not value.is_finite() or value<0 or scaled != scaled.to_integral_value() or scaled>10**12:
            raise ValueError('قيمة غير صحيحة أو دقة أكبر من المسموح')
        result=int(scaled)
        if positive and result==0: raise ValueError('الكمية يجب أن تكون أكبر من صفر')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('أدخل رقمًا صحيحًا') from None


def parse_money(text): return _parse(text,100)
def parse_quantity(text): return _parse(text,1000,True)
def amount(price,quantity): return (price*quantity+500)//1000
def formatted(value): return f'{value/100:.2f}'
def quantity_text(value): return f'{value/1000:g}'

def integer(value, minimum=0):
    if type(value) is not int or value<minimum or value>10**12: raise ValueError('قيمة غير صحيحة')
    return value
