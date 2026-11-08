import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
data='customer,amount,status\n"Acme, Inc",12.30,paid\nAda,2.10,pending\n"Acme, Inc",-1.20,paid\nAda,0.29,paid\nZero,0,paid\n'
Path('hidden.csv').write_text(data)
subprocess.run([sys.executable,'report.py','hidden.csv','answer.json'],check=True)
assert json.loads(Path('answer.json').read_text()) == {'Acme, Inc':1110,'Ada':29,'Zero':0}
assert Path('hidden.csv').read_text()==data
Path('hidden.csv').write_text('customer,amount,status\n')
subprocess.run([sys.executable,'report.py','hidden.csv','answer.json'],check=True)
assert json.loads(Path('answer.json').read_text())=={}

print("VERIFIED")
