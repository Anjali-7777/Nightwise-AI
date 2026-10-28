import json,random
from pathlib import Path
OUT=Path(__file__).parents[1]/'data'; OUT.mkdir(exist_ok=True)
verbs=['find','show','plan','compare']; objects=['a route with more main roads','the shortest route','an alternative with more shops','a route with better transit access','two available routes']; rows=[]
for i in range(1200):
 v=verbs[i%len(verbs)]; o=objects[(i*7)%len(objects)]; rows.append({'text':f'{v} {o}.','label':{'intent':'compare_routes' if 'compare' in v or 'two' in o else 'plan_route','main_road_preference':'main road' in o,'shorter_distance':'shortest' in o,'nearby_establishments_preference':'shops' in o,'public_transport_preference':'transit' in o},'synthetic':True,'family':i%12})
random.Random(42).shuffle(rows); (OUT/'route_requests.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
print(f'wrote {len(rows)} synthetic examples to {OUT/"route_requests.jsonl"}')
