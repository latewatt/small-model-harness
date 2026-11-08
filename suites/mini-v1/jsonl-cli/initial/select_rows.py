import sys,json,argparse
p=argparse.ArgumentParser();p.add_argument('--min-score',default='0');a=p.parse_args()
rows=[json.loads(line) for line in sys.stdin]
for row in sorted(rows,key=lambda r:r['score'],reverse=True):
    if row['score']>=a.min_score: print(row['id'])
