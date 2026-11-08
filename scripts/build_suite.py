"""Rebuild the deterministic local development suite; never a Terminal-Bench score.

Each oracle is kept outside the agent's readable workspace. Verifiers execute
only after the agent stops. These fixtures test infrastructure, not frontier work.
"""
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "suites/mini-v1"
TASKS = []


def clean(s):
    return textwrap.dedent(s).lstrip("\n")


def add(name, category, prompt, files, verify, oracle):
    path = SUITE / name
    for folder, values in (("initial", files), ("oracle", oracle)):
        for relative, content in values.items():
            dest = path / folder / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(clean(content))
    (path / "instruction.md").write_text(prompt + "\n")
    preamble = '''import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
'''
    (path / "verify.py").write_text(preamble + clean(verify) + '\nprint("VERIFIED")\n')
    TASKS.append({"id": name, "category": category, "path": str(path.relative_to(ROOT))})


add("csv-totals", "data-processing",
    "Fix report.py. CLI: python3 report.py INPUT.csv OUTPUT.json. CSV columns customer,amount,status; quoted names may contain commas. Sum only rows whose status is exactly paid, in integer cents per customer; amounts are decimal strings with at most two fractional digits and can be negative. Exclude customers without paid rows. Output a JSON object. Preserve the input file.",
    {"report.py": r'''
        import sys,json
        rows=open(sys.argv[1]).read().splitlines()[1:]
        totals={}
        for row in rows:
            customer,amount,status=row.split(',')
            totals[customer]=totals.get(customer,0)+int(float(amount)*100)
        json.dump(totals,open(sys.argv[2],'w'))
        ''', "sample.csv": 'customer,amount,status\n"Acme, Inc",12.30,paid\nAda,2.10,pending\n"Acme, Inc",-1.20,paid\n'},
    r'''
    data='customer,amount,status\n"Acme, Inc",12.30,paid\nAda,2.10,pending\n"Acme, Inc",-1.20,paid\nAda,0.29,paid\nZero,0,paid\n'
    Path('hidden.csv').write_text(data)
    subprocess.run([sys.executable,'report.py','hidden.csv','answer.json'],check=True)
    assert json.loads(Path('answer.json').read_text()) == {'Acme, Inc':1110,'Ada':29,'Zero':0}
    assert Path('hidden.csv').read_text()==data
    Path('hidden.csv').write_text('customer,amount,status\n')
    subprocess.run([sys.executable,'report.py','hidden.csv','answer.json'],check=True)
    assert json.loads(Path('answer.json').read_text())=={}
    ''',
    {"report.py": r'''
        import csv,json,sys
        from decimal import Decimal
        totals={}
        with open(sys.argv[1],newline='') as stream:
            for row in csv.DictReader(stream):
                if row['status']=='paid':
                    k=row['customer']
                    totals[k]=totals.get(k,0)+int(Decimal(row['amount'])*100)
        with open(sys.argv[2],'w') as stream: json.dump(totals,stream)
        '''})

add("merge-config", "python-repair",
    "Fix merge.py: deep_merge(left, right) recursively merges dictionaries, with right values winning. Lists are replaced, not concatenated. Neither input nor any nested value may be mutated or aliased in the result. Inputs are JSON-compatible dicts.",
    {"merge.py": 'def deep_merge(left, right):\n    left.update(right)\n    return left\n'},
    r'''
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
    ''',
    {"merge.py": r'''
        from copy import deepcopy
        def deep_merge(left,right):
            result=deepcopy(left)
            for key,value in right.items():
                if isinstance(result.get(key),dict) and isinstance(value,dict):
                    result[key]=deep_merge(result[key],value)
                else: result[key]=deepcopy(value)
            return result
        '''})

add("intervals", "algorithm",
    "Fix intervals.py: merge_intervals(intervals) takes a list of [start,end] integer inclusive intervals, returns sorted nonoverlapping intervals, merging overlaps AND touching endpoints (e.g. [1,2],[2,3] -> [[1,3]]). Do not merge merely adjacent [1,2],[3,4]. Do not mutate input. Empty input returns []. A reversed interval raises ValueError.",
    {"intervals.py": r'''
        def merge_intervals(intervals):
            intervals.sort()
            result=[intervals[0]]
            for start,end in intervals[1:]:
                if start<result[-1][1]: result[-1][1]=end
                else: result.append([start,end])
            return result
        '''},
    r'''
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
    ''',
    {"intervals.py": r'''
        def merge_intervals(intervals):
            if any(a>b for a,b in intervals): raise ValueError('reversed')
            result=[]
            for a,b in sorted(intervals):
                if result and a<=result[-1][1]: result[-1][1]=max(b,result[-1][1])
                else: result.append([a,b])
            return result
        '''})

add("toposort", "algorithm",
    "Fix graph.py: order_tasks(dependencies) maps task names to lists of prerequisite names. Return all names including prerequisites absent as dictionary keys, each after its prerequisites. At every step choose the lexicographically smallest currently available task. Duplicate prerequisites count once. Raise ValueError on any cycle. Do not mutate inputs.",
    {"graph.py": 'def order_tasks(dependencies):\n    return sorted(dependencies)\n'},
    r'''
    from graph import order_tasks
    d={'test':['build','build'],'build':['fetch'],'lint':[]};before=copy.deepcopy(d)
    assert order_tasks(d)==['fetch','build','lint','test'] and d==before
    assert order_tasks({})==[]
    assert order_tasks({'a':['z'],'b':[]})==['b','z','a']
    for cycle in [{'a':['a']},{'a':['b'],'b':['a']},{'x':[],'a':['b'],'b':['a']}]:
        try: order_tasks(cycle)
        except ValueError: pass
        else: raise AssertionError('cycle accepted')
    ''',
    {"graph.py": r'''
        def order_tasks(dependencies):
            nodes=set(dependencies)
            for values in dependencies.values(): nodes.update(values)
            remaining={n:set(dependencies.get(n,[])) for n in nodes}
            result=[]
            while remaining:
                ready=sorted(n for n,d in remaining.items() if not d)
                if not ready: raise ValueError('cycle')
                n=ready[0];result.append(n);del remaining[n]
                for d in remaining.values(): d.discard(n)
            return result
        '''})

logs = ''.join(json.dumps({'level':'INFO','service':'api','request_id':f'r{i}'})+'\n' for i in range(1000))
logs += '{bad json\n'+json.dumps({'level':'ERROR','service':'worker','request_id':'last'})+'\n'
add("log-summary", "terminal-data",
    "Implement summarize.py. CLI: python3 summarize.py INPUT.jsonl OUTPUT.json. Count ERROR records per service, counting each request_id once globally among ERROR records (first valid ERROR wins). A valid record is a JSON object with nonempty string service and request_id and level exactly ERROR. Skip malformed JSON, other levels and invalid records. Write a JSON object mapping service to count; exclude services without errors. logs.jsonl is a large sample.",
    {"summarize.py": 'import sys,json\njson.dump({},open(sys.argv[2],"w"))\n',"logs.jsonl":logs},
    r'''
    records=[{'level':'ERROR','service':'api','request_id':'a'}, {'level':'INFO','service':'api','request_id':'b'}, {'level':'ERROR','service':'worker','request_id':'b'}, {'level':'ERROR','service':'other','request_id':'a'}, {'level':'ERROR','service':'api','request_id':'c'}, {'level':'ERROR','service':None,'request_id':'d'}, [], {'level':'ERROR','service':'x','request_id':''}]
    Path('input.jsonl').write_text('\n'.join(json.dumps(x) for x in records)+'\n{broken\n')
    subprocess.run([sys.executable,'summarize.py','input.jsonl','out.json'],check=True)
    assert json.loads(Path('out.json').read_text())=={'api':2,'worker':1}
    subprocess.run([sys.executable,'summarize.py','logs.jsonl','out.json'],check=True)
    assert json.loads(Path('out.json').read_text())=={'worker':1}
    ''',
    {"summarize.py": r'''
        import sys,json
        counts={};seen=set()
        for line in open(sys.argv[1]):
            try: row=json.loads(line)
            except ValueError: continue
            if not isinstance(row,dict) or row.get('level')!='ERROR': continue
            service,key=row.get('service'),row.get('request_id')
            if not isinstance(service,str) or not service or not isinstance(key,str) or not key or key in seen: continue
            seen.add(key);counts[service]=counts.get(service,0)+1
        json.dump(counts,open(sys.argv[2],'w'))
        '''})

add("jsonl-cli", "cli",
    "Fix select_rows.py. CLI reads JSONL from stdin; --min-score is a float defaulting to 0. Keep dict rows with status exactly active, a nonempty string id and a finite numeric score (number or numeric string, but not bool). Skip invalid JSON and invalid records. Keep score >= threshold. Print each id on its own line, ordered by descending numeric score, then ascending id for ties. No headers or debug output.",
    {"select_rows.py": r'''
        import sys,json,argparse
        p=argparse.ArgumentParser();p.add_argument('--min-score',default='0');a=p.parse_args()
        rows=[json.loads(line) for line in sys.stdin]
        for row in sorted(rows,key=lambda r:r['score'],reverse=True):
            if row['score']>=a.min_score: print(row['id'])
        '''},
    r'''
    rows=[{'id':'z','score':'9','status':'active'},{'id':'b','score':10,'status':'active'},{'id':'a','score':'10','status':'active'},{'id':'off','score':50,'status':'inactive'},{'id':'bad','score':'NaN','status':'active'},{'id':'bool','score':True,'status':'active'},[],{}]
    data='\n'.join(json.dumps(r) for r in rows)+'\nnot-json\n'
    out=subprocess.check_output([sys.executable,'select_rows.py','--min-score','9.5'],input=data,text=True)
    assert out=='a\nb\n',repr(out)
    out=subprocess.check_output([sys.executable,'select_rows.py'],input='',text=True)
    assert out==''
    ''',
    {"select_rows.py": r'''
        import sys,json,argparse,math
        p=argparse.ArgumentParser();p.add_argument('--min-score',type=float,default=0);a=p.parse_args()
        rows=[]
        for line in sys.stdin:
            try:
                r=json.loads(line)
                if not isinstance(r,dict) or r.get('status')!='active' or not isinstance(r.get('id'),str) or not r['id'] or isinstance(r.get('score'),bool): continue
                s=float(r['score'])
                if math.isfinite(s) and s>=a.min_score: rows.append((s,r['id']))
            except (ValueError,TypeError,KeyError): continue
        for s,key in sorted(rows,key=lambda x:(-x[0],x[1])): print(key)
        '''})

add("sql-revenue", "sql",
    "Fix query.sql for SQLite. Schema: customers(id INTEGER PRIMARY KEY, name TEXT, active INTEGER); orders(id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT); items(order_id INTEGER, quantity INTEGER, unit_price_cents INTEGER). Return columns id,name,revenue_cents for every active=1 customer, including customers with no completed orders/items (revenue 0). Only status='completed' orders count. Sum quantity*unit_price_cents. Sort revenue descending then customer id ascending. Keep all data unchanged.",
    {"query.sql": 'SELECT c.id,c.name,SUM(i.unit_price_cents) AS revenue_cents FROM customers c JOIN orders o ON o.customer_id=c.id JOIN items i ON i.order_id=o.id GROUP BY c.id ORDER BY revenue_cents DESC;\n'},
    r'''
    db=sqlite3.connect(':memory:')
    db.executescript("CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,active INTEGER); CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER,status TEXT); CREATE TABLE items(order_id INTEGER,quantity INTEGER,unit_price_cents INTEGER); INSERT INTO customers VALUES(1,'Ada',1),(2,'Bob',1),(3,'Off',0),(4,'Zero',1),(5,'Equal',1); INSERT INTO orders VALUES(10,1,'completed'),(11,1,'pending'),(12,3,'completed'),(13,2,'completed'),(14,5,'completed'); INSERT INTO items VALUES(10,2,150),(10,1,25),(11,9,900),(12,1,999),(14,1,325);")
    query=Path('query.sql').read_text()
    rows=db.execute(query).fetchall()
    assert rows==[(1,'Ada',325),(5,'Equal',325),(2,'Bob',0),(4,'Zero',0)],rows
    assert db.execute('SELECT COUNT(*) FROM customers').fetchone()==(5,)
    ''',
    {"query.sql": "SELECT c.id,c.name,COALESCE(SUM(i.quantity*i.unit_price_cents),0) AS revenue_cents FROM customers c LEFT JOIN orders o ON o.customer_id=c.id AND o.status='completed' LEFT JOIN items i ON i.order_id=o.id WHERE c.active=1 GROUP BY c.id,c.name ORDER BY revenue_cents DESC,c.id ASC;\n"})

add("repair-package", "multi-file",
    "Repair pricepkg. Public API: from pricepkg import quote, cents. cents(value) accepts a decimal string or number and returns integer cents, rounding half away from zero to two decimal places (1.005 -> 101, -1.005 -> -101). quote(items) takes dicts with price and nonnegative integer quantity, sums cents(price)*quantity, returns integer cents. Negative or noninteger/bool quantities raise ValueError. Empty items returns 0. Preserve inputs.",
    {"pricepkg/__init__.py": '',"pricepkg/money.py": 'def cents(value):\n    return int(float(value)*100)\n',"pricepkg/cart.py": 'from .money import cents\ndef quote(items):\n    return sum(cents(x["price"]) for x in items)\n'},
    r'''
    from pricepkg import cents,quote
    assert cents('1.005')==101 and cents('-1.005')==-101 and cents(0.29)==29
    rows=[{'price':'1.005','quantity':2},{'price':0.29,'quantity':3}];before=copy.deepcopy(rows)
    assert quote(rows)==289 and rows==before and quote([])==0
    for bad in [-1,1.5,True,'2']:
        try: quote([{'price':'1','quantity':bad}])
        except ValueError: pass
        else: raise AssertionError('invalid quantity accepted')
    ''',
    {"pricepkg/__init__.py": 'from .money import cents\nfrom .cart import quote\n',"pricepkg/money.py": r'''
        from decimal import Decimal,ROUND_HALF_UP
        def cents(value):
            return int((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        ''',"pricepkg/cart.py": r'''
        from .money import cents
        def quote(items):
            total=0
            for row in items:
                q=row['quantity']
                if type(q) is not int or q<0: raise ValueError('quantity')
                total+=cents(row['price'])*q
            return total
        '''})

add("path-index", "filesystem",
    "Fix indexer.py: python_files(root) returns sorted relative POSIX paths of all .py files recursively. Ignore files and directories with names starting '.', and never include or follow any symlink. Handle spaces and Unicode. Do not modify files. root exists and is a directory.",
    {"indexer.py": 'import os\ndef python_files(root):\n    return [f for f in os.listdir(root) if f.endswith(".py")]\n'},
    r'''
    from indexer import python_files
    root=Path('tree');root.mkdir()
    for name in ['a.py','z.txt','space dir/b.py','uni/é.py','.hidden.py','.git/evil.py','sub/.cache/x.py']:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('hello')
    (root/'link.py').symlink_to('a.py');(root/'linked').symlink_to('space dir',target_is_directory=True)
    assert python_files(root)==['a.py','space dir/b.py','uni/é.py']
    assert (root/'a.py').read_text()=='hello'
    empty=Path('empty');empty.mkdir();assert python_files(empty)==[]
    ''',
    {"indexer.py": r'''
        from pathlib import Path
        def python_files(root):
            root=Path(root);out=[]
            def walk(directory):
                for p in directory.iterdir():
                    if p.name.startswith('.') or p.is_symlink(): continue
                    if p.is_dir(): walk(p)
                    elif p.is_file() and p.suffix=='.py': out.append(p.relative_to(root).as_posix())
            walk(root)
            return sorted(out)
        '''})

add("config-parser", "parser",
    "Fix config.py parse_config(text). Parse key=value lines; trim surrounding whitespace on key/value. Ignore blank lines and full-line # comments (after stripping). Split on FIRST '=' only. Values matching an optional + or - followed by ASCII digits become int; other values stay strings, including empty and inline #. Duplicate keys: last wins. Invalid lines with no '=' or an empty key raise ValueError whose message includes the 1-based physical line number. Return dict.",
    {"config.py": r'''
        def parse_config(text):
            result={}
            for line in text.splitlines():
                key,value=line.split('=')
                result[key]=int(value)
            return result
        '''},
    r'''
    from config import parse_config
    text=' # comment\n\n name = a=b \n retries=+03\n retries=-2\n empty=\n tag = x # keep\n pi=3.14\n'
    assert parse_config(text)=={'name':'a=b','retries':-2,'empty':'','tag':'x # keep','pi':'3.14'}
    assert parse_config('')=={}
    assert parse_config('num=１２')=={'num':'１２'}
    for bad in ['# comment\nno equals','# c\n =bad']:
        try: parse_config(bad)
        except ValueError as e: assert '2' in str(e)
        else: raise AssertionError('invalid line accepted')
    ''',
    {"config.py": r'''
        import re
        def parse_config(text):
            result={}
            for number,line in enumerate(text.splitlines(),1):
                line=line.strip()
                if not line or line.startswith('#'): continue
                if '=' not in line: raise ValueError(f'line {number}')
                key,value=(x.strip() for x in line.split('=',1))
                if not key: raise ValueError(f'line {number}')
                result[key]=int(value) if re.fullmatch(r'[+-]?[0-9]+',value) else value
            return result
        '''})

(SUITE / "manifest.json").write_text(json.dumps({"name":"mini-v1","kind":"local-development-not-terminal-bench","tasks":TASKS},indent=2)+'\n')
(ROOT / "subsets/mini10.json").write_text(json.dumps({"suite":"mini-v1","tasks":[t['id'] for t in TASKS]},indent=2)+'\n')
(ROOT / "subsets/smoke.json").write_text(json.dumps({"suite":"mini-v1","tasks":["merge-config"]},indent=2)+'\n')
print(f"Built {len(TASKS)} tasks in {SUITE}")
