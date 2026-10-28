import re
from .routing import plan_routes
from .scoring import score_route

def parse_request(text):
    t=text.lower(); intent='compare_routes' if any(x in t for x in ['compare','alternative','options']) else 'plan_route'
    return {'intent':intent,'preferences':{'shorter_distance':bool(re.search(r'short|quick|faster',t)),'main_road_preference':bool(re.search(r'main road|well[- ]lit',t)),'nearby_establishments_preference':bool(re.search(r'shop|business|establishment',t)),'public_transport_preference':bool(re.search(r'transit|bus|transport',t))}}

def chat(text, origin='station', destination='campus'):
    parsed=parse_request(text); routes=plan_routes(origin,destination)
    for r in routes: r['score']=score_route(r,parsed['preferences'])
    best=max(routes,key=lambda r:r['score'])
    return {'parsed':parsed,'trace':['Request understood','Tool selected: get_routes → calculate_route_score','Route data calculated','Grounded explanation generated'],'routes':routes,'recommendation':best['id'],'explanation':f"{best['name']} has the highest environmental-support estimate ({best['score']}/100). This is based on mapped indicators only; it is not a crime-risk or personal-safety probability."}
