from decimal import Decimal,ROUND_HALF_UP
def cents(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
