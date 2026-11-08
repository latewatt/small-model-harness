import sys,json,argparse,math
p=argparse.ArgumentParser();p.add_argument('--min-score',type=float,default=0);a=p.parse_args()
rows=[]
for line in sys.stdin:
    try:
        r=json.loads(line)
        if not isinstance(r,dict) or r.get('status')!='active' or not isinstance(r.get('id'),str) or not r['id'] or isinstance(r.get('score'),bool): continue
        s=float(r['score'])
        if math.isfinite(s) and s>=a.min_score: rows.append((s,r['id']))
    except (ValueError,TypeError,KeyError): continue
for s,key in sorted(rows,key=lambda x:(-x[0],x[1])): print(key)
