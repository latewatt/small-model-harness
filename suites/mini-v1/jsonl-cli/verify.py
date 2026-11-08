import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
rows=[{'id':'z','score':'9','status':'active'},{'id':'b','score':10,'status':'active'},{'id':'a','score':'10','status':'active'},{'id':'off','score':50,'status':'inactive'},{'id':'bad','score':'NaN','status':'active'},{'id':'bool','score':True,'status':'active'},[],{}]
data='\n'.join(json.dumps(r) for r in rows)+'\nnot-json\n'
out=subprocess.check_output([sys.executable,'select_rows.py','--min-score','9.5'],input=data,text=True)
assert out=='a\nb\n',repr(out)
out=subprocess.check_output([sys.executable,'select_rows.py'],input='',text=True)
assert out==''

print("VERIFIED")
