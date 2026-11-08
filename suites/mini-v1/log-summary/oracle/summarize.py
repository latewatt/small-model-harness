import sys,json
counts={};seen=set()
for line in open(sys.argv[1]):
    try: row=json.loads(line)
    except ValueError: continue
    if not isinstance(row,dict) or row.get('level')!='ERROR': continue
    service,key=row.get('service'),row.get('request_id')
    if not isinstance(service,str) or not service or not isinstance(key,str) or not key or key in seen: continue
    seen.add(key);counts[service]=counts.get(service,0)+1
json.dump(counts,open(sys.argv[2],'w'))
