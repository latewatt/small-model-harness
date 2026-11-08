import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
from indexer import python_files
root=Path('tree');root.mkdir()
for name in ['a.py','z.txt','space dir/b.py','uni/é.py','.hidden.py','.git/evil.py','sub/.cache/x.py']:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('hello')
(root/'link.py').symlink_to('a.py');(root/'linked').symlink_to('space dir',target_is_directory=True)
assert python_files(root)==['a.py','space dir/b.py','uni/é.py']
assert (root/'a.py').read_text()=='hello'
empty=Path('empty');empty.mkdir();assert python_files(empty)==[]

print("VERIFIED")
