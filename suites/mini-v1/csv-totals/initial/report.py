import sys,json
rows=open(sys.argv[1]).read().splitlines()[1:]
totals={}
for row in rows:
    customer,amount,status=row.split(',')
    totals[customer]=totals.get(customer,0)+int(float(amount)*100)
json.dump(totals,open(sys.argv[2],'w'))
