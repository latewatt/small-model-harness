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
