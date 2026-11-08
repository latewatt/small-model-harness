from .money import cents
def quote(items):
    return sum(cents(x["price"]) for x in items)
