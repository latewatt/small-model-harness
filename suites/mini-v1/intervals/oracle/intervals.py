def merge_intervals(intervals):
    if any(a>b for a,b in intervals): raise ValueError('reversed')
    result=[]
    for a,b in sorted(intervals):
        if result and a<=result[-1][1]: result[-1][1]=max(b,result[-1][1])
        else: result.append([a,b])
    return result
