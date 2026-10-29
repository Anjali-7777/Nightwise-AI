import logging
from typing import List, Dict, Any
from .places import get_bounding_box
from .overpass_client import fetch_osm_corridor_features

logger = logging.getLogger("nightwise.cameras")

async def fetch_cameras_in_corridor(coords: List[List[float]]) -> List[Dict[str, Any]]:
    """
    Fetches surveillance cameras along the corridor from OpenStreetMap.
    Also includes police stations as active physical surveillance proxies.
    """
    if not coords:
        return []

    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords)
    osm_bundle = await fetch_osm_corridor_features(min_lat, min_lon, max_lat, max_lon)

    cameras = list(osm_bundle.get("cameras", []))

    # Add police stations as surveillance proxies
    for p in osm_bundle.get("places", []):
        if p.get("category") == "police":
            cameras.append({
                "id": f"cam-proxy-{p['id']}",
                "lat": p["lat"],
                "lon": p["lon"],
                "type": "police_station_cctv_proxy",
                "operator": "police",
                "is_proxy": True
            })

    return cameras
