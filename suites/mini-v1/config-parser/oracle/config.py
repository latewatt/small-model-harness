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
