import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from intervals import merge_intervals
assert merge_intervals([])==[]
data=[[5,8],[1,4],[2,3],[4,5],[10,10]];before=copy.deepcopy(data)
assert merge_intervals(data)==[[1,8],[10,10]] and data==before
assert merge_intervals([[1,2],[3,4]])==[[1,2],[3,4]]
assert merge_intervals([[-2,0],[0,3],[1,2]])==[[-2,3]]
try: merge_intervals([[3,1]])
except ValueError: pass
else: raise AssertionError('reversed interval accepted')
rng=random.Random(29)
for _ in range(30):
    xs=[sorted([rng.randint(-9,9),rng.randint(-9,9)]) for _ in range(8)]
    out=merge_intervals(xs)
    assert all(a[1]<b[0] for a,b in zip(out,out[1:]))
    assert {i for a,b in xs for i in range(a,b+1)}=={i for a,b in out for i in range(a,b+1)}

print("VERIFIED")
