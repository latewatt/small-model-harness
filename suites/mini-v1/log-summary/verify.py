import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
records=[{'level':'ERROR','service':'api','request_id':'a'}, {'level':'INFO','service':'api','request_id':'b'}, {'level':'ERROR','service':'worker','request_id':'b'}, {'level':'ERROR','service':'other','request_id':'a'}, {'level':'ERROR','service':'api','request_id':'c'}, {'level':'ERROR','service':None,'request_id':'d'}, [], {'level':'ERROR','service':'x','request_id':''}]
Path('input.jsonl').write_text('\n'.join(json.dumps(x) for x in records)+'\n{broken\n')
subprocess.run([sys.executable,'summarize.py','input.jsonl','out.json'],check=True)
assert json.loads(Path('out.json').read_text())=={'api':2,'worker':1}
subprocess.run([sys.executable,'summarize.py','logs.jsonl','out.json'],check=True)
assert json.loads(Path('out.json').read_text())=={'worker':1}

print("VERIFIED")
