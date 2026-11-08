import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from pricepkg import cents,quote
assert cents('1.005')==101 and cents('-1.005')==-101 and cents(0.29)==29
rows=[{'price':'1.005','quantity':2},{'price':0.29,'quantity':3}];before=copy.deepcopy(rows)
assert quote(rows)==289 and rows==before and quote([])==0
for bad in [-1,1.5,True,'2']:
    try: quote([{'price':'1','quantity':bad}])
    except ValueError: pass
    else: raise AssertionError('invalid quantity accepted')

print("VERIFIED")
