from copy import deepcopy
def deep_merge(left,right):
    result=deepcopy(left)
    for key,value in right.items():
        if isinstance(result.get(key),dict) and isinstance(value,dict):
            result[key]=deep_merge(result[key],value)
        else: result[key]=deepcopy(value)
    return result
