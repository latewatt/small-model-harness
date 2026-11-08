import csv,json,sys
from decimal import Decimal
totals={}
with open(sys.argv[1],newline='') as stream:
    for row in csv.DictReader(stream):
        if row['status']=='paid':
            k=row['customer']
            totals[k]=totals.get(k,0)+int(Decimal(row['amount'])*100)
with open(sys.argv[2],'w') as stream: json.dump(totals,stream)
