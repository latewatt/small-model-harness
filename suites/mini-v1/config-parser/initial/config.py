def parse_config(text):
    result={}
    for line in text.splitlines():
        key,value=line.split('=')
        result[key]=int(value)
    return result
