import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from merge import deep_merge
a={'db':{'host':'localhost','port':1},'flags':[1], 'same':{'x':[1]}}
b={'db':{'port':2},'flags':[2,3], 'fresh':{'z':[9]}}
aa,bb=copy.deepcopy(a),copy.deepcopy(b)
r=deep_merge(a,b)
assert r=={'db':{'host':'localhost','port':2},'flags':[2,3],'same':{'x':[1]},'fresh':{'z':[9]}}
assert a==aa and b==bb
r['same']['x'].append(4);r['fresh']['z'].append(4)
assert a==aa and b==bb
assert deep_merge({'x':{'a':1}}, {'x':None})=={'x':None}
assert deep_merge({}, {})=={}

print("VERIFIED")
