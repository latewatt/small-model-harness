from .money import cents
def quote(items):
    total=0
    for row in items:
        q=row['quantity']
        if type(q) is not int or q<0: raise ValueError('quantity')
        total+=cents(row['price'])*q
    return total
