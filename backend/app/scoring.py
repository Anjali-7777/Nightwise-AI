DEFAULT_WEIGHTS={"establishment_support":0.30,"main_road_coverage":0.30,"transit_access":0.20,"assistance_point_support":0.10,"isolated_segment_penalty":0.10}
def score_route(route, preferences=None):
    preferences=preferences or {}; f=route['features']; w=DEFAULT_WEIGHTS.copy()
    if preferences.get('main_road_preference'): w['main_road_coverage']+=.15
    if preferences.get('nearby_establishments_preference'): w['establishment_support']+=.15
    if preferences.get('public_transport_preference'): w['transit_access']+=.15
    if preferences.get('shorter_distance'): w['isolated_segment_penalty']+=.05
    total=sum(w.values()); w={k:v/total for k,v in w.items()}
    value=sum(f[k]*w[k] for k in ('establishment_support','main_road_coverage','transit_access','assistance_point_support'))-f['isolated_segment_penalty']*w['isolated_segment_penalty']
    return round(max(0,min(100,value*100)),1)
