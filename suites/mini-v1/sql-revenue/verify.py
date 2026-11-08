import sys, os, json, csv, sqlite3, subprocess, random, copy
from pathlib import Path
work = Path(sys.argv[1]).resolve()
os.chdir(work)
sys.path.insert(0, str(work))
db=sqlite3.connect(':memory:')
db.executescript("CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,active INTEGER); CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER,status TEXT); CREATE TABLE items(order_id INTEGER,quantity INTEGER,unit_price_cents INTEGER); INSERT INTO customers VALUES(1,'Ada',1),(2,'Bob',1),(3,'Off',0),(4,'Zero',1),(5,'Equal',1); INSERT INTO orders VALUES(10,1,'completed'),(11,1,'pending'),(12,3,'completed'),(13,2,'completed'),(14,5,'completed'); INSERT INTO items VALUES(10,2,150),(10,1,25),(11,9,900),(12,1,999),(14,1,325);")
query=Path('query.sql').read_text()
rows=db.execute(query).fetchall()
assert rows==[(1,'Ada',325),(5,'Equal',325),(2,'Bob',0),(4,'Zero',0)],rows
assert db.execute('SELECT COUNT(*) FROM customers').fetchone()==(5,)

print("VERIFIED")
