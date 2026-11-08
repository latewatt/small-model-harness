import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from graph import order_tasks
d={'test':['build','build'],'build':['fetch'],'lint':[]};before=copy.deepcopy(d)
assert order_tasks(d)==['fetch','build','lint','test'] and d==before
assert order_tasks({})==[]
assert order_tasks({'a':['z'],'b':[]})==['b','z','a']
for cycle in [{'a':['a']},{'a':['b'],'b':['a']},{'x':[],'a':['b'],'b':['a']}]:
    try: order_tasks(cycle)
    except ValueError: pass
    else: raise AssertionError('cycle accepted')

print("VERIFIED")
