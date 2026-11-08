import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from config import parse_config
text=' # comment\n\n name = a=b \n retries=+03\n retries=-2\n empty=\n tag = x # keep\n pi=3.14\n'
assert parse_config(text)=={'name':'a=b','retries':-2,'empty':'','tag':'x # keep','pi':'3.14'}
assert parse_config('')=={}
assert parse_config('num=１２')=={'num':'１２'}
for bad in ['# comment\nno equals','# c\n =bad']:
    try: parse_config(bad)
    except ValueError as e: assert '2' in str(e)
    else: raise AssertionError('invalid line accepted')

print("VERIFIED")
