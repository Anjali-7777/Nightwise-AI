import re
def predict(text):
    t=text.lower()
    return {'intent':'compare_routes' if any(x in t for x in ('compare','alternative','options')) else 'plan_route','preferences':{'shorter_distance':bool(re.search(r'short|quick|faster',t)),'main_road_preference':bool(re.search(r'main road|well[- ]lit',t)),'nearby_establishments_preference':bool(re.search(r'shop|business|establishment',t)),'public_transport_preference':bool(re.search(r'transit|bus|transport',t))}}
