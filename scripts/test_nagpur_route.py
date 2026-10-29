import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from datetime import datetime
from backend.services.routing import get_routes
from backend.services.places import fetch_places_in_corridor
from backend.services.cameras import fetch_cameras_in_corridor
from backend.services.roads import fetch_road_attributes_in_corridor
from backend.scoring.night_score import score_route

async def test_rbu_to_vr():
    orig = (21.1767, 79.0620) # Ramdeobaba University / College (RBU / RCOEM)
    dest = (21.1320, 79.0962) # VR Mall Nagpur (Trillium Mall)
    routes = await get_routes(orig, dest, mode='walking')
    print('Found routes:', len(routes))
    for r in routes:
        print(f"Route: {r['id']} - {r['name']}: {r['distance_m']/1000:.2f} km, {r['duration_s']/60:.1f} min, {len(r['coordinates'])} points")
    
    combined = []
    for r in routes:
        combined.extend(r['coordinates'])
    
    places, cameras, roads = await asyncio.gather(
        fetch_places_in_corridor(combined),
        fetch_cameras_in_corridor(combined),
        fetch_road_attributes_in_corridor(combined)
    )
    print(f"Corridor features: {len(places)} places, {len(cameras)} cameras, {len(roads)} roads")
    for r in routes:
        sc = score_route(r, places, cameras, roads, datetime.now(), 'walking')
        print(f"Score for {r['name']}: {sc['night_score']}/100, Open Places: {sc['metrics']['open_places_count']}, Cameras: {sc['metrics']['cameras_count']}")

if __name__ == '__main__':
    asyncio.run(test_rbu_to_vr())
