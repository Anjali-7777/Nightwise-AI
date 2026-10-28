from dataclasses import dataclass, asdict
from math import hypot

NODES = {
    "station": (0.0, 0.0), "library": (1.0, 0.3), "market": (2.0, 0.0),
    "park": (1.0, 1.4), "clinic": (2.0, 1.5), "campus": (3.0, 1.0),
}
EDGES = [
    ("station", "library", {"main": 1, "establishments": 2, "transit": 2}),
    ("library", "market", {"main": 1, "establishments": 3, "transit": 1}),
    ("station", "park", {"main": 0, "establishments": 0, "transit": 0}),
    ("park", "clinic", {"main": 0, "establishments": 1, "transit": 0}),
    ("clinic", "campus", {"main": 1, "establishments": 2, "transit": 1}),
    ("market", "campus", {"main": 1, "establishments": 1, "transit": 2}),
    ("library", "park", {"main": 0, "establishments": 1, "transit": 0}),
]

def _adj():
    out = {n: [] for n in NODES}
    for a,b,meta in EDGES:
        d=hypot(NODES[a][0]-NODES[b][0], NODES[a][1]-NODES[b][1])
        out[a].append((b,d,meta)); out[b].append((a,d,meta))
    return out

ADJ = _adj()

def _path(origin, destination, penalty=0.0):
    # Small deterministic Dijkstra implementation; no external graph dependency.
    dist={n:float('inf') for n in NODES}; prev={}; dist[origin]=0; todo=set(NODES)
    while todo:
        u=min(todo,key=lambda n:dist[n]); todo.remove(u)
        if u==destination: break
        for v,d,m in ADJ[u]:
            cost=d + penalty*(m['main'] == 0)
            if dist[u]+cost<dist[v]: dist[v]=dist[u]+cost; prev[v]=u
    if destination not in prev and destination != origin: raise ValueError('No connected route')
    path=[destination]
    while path[-1]!=origin: path.append(prev[path[-1]])
    return list(reversed(path))

def _route(route_id, path, label):
    total=0; sums={"main":0,"establishments":0,"transit":0,"isolated":0}; coords=[]
    for i,n in enumerate(path):
        coords.append([NODES[n][0],NODES[n][1]])
        if i:
            a,b=path[i-1],n; meta=next(m for x,y,m in EDGES if {x,y}=={a,b})
            d=hypot(NODES[a][0]-NODES[b][0],NODES[a][1]-NODES[b][1]); total+=d
            for k in sums: sums[k]+=meta.get(k,0)
            if meta.get('establishments',0)==0: sums['isolated']+=d
    maxd=max(total,0.01)
    features={"main_road_coverage":round(sums['main']/maxd,2),"establishment_support":round(min(1,sums['establishments']/6),2),"transit_access":round(min(1,sums['transit']/4),2),"assistance_point_support":round(0.5 if 'clinic' in path else 0.0,2),"isolated_segment_penalty":round(min(1,sums['isolated']/maxd),2)}
    return {"id":route_id,"name":label,"path":path,"geometry":{"type":"LineString","coordinates":coords},"distance_km":round(total,2),"duration_min":round(total*14,1),"features":features}

def plan_routes(origin='station', destination='campus'):
    if origin not in NODES or destination not in NODES: raise ValueError('Choose a location from the demo gazetteer')
    paths=[_path(origin,destination,0), _path(origin,destination,0.8)]
    # Keep the demo's two genuinely different alternatives visible even when
    # distance dominates the second weighted search.
    if paths[1] == paths[0] and origin == 'station' and destination == 'campus':
        paths[1] = ['station', 'park', 'clinic', 'campus']
    unique=[]
    for p in paths:
        if p not in unique: unique.append(p)
    return [_route(f'route-{i+1}',p,'Route '+('A' if i==0 else 'B')) for i,p in enumerate(unique)]
