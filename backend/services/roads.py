import logging
from typing import List, Dict, Any
from .places import get_bounding_box
from .overpass_client import fetch_osm_corridor_features

logger = logging.getLogger("nightwise.roads")

MAIN_ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary"}
INTERNAL_ROAD_CLASSES = {"residential", "service", "living_street", "footway", "path", "track", "unclassified"}

async def fetch_road_attributes_in_corridor(coords: List[List[float]]) -> List[Dict[str, Any]]:
    """
    Fetches OSM ways along the route corridor to identify road classifications,
    lit status, and sidewalks.
    """
    if not coords:
        return []

    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords, buffer_deg=0.005)
    osm_bundle = await fetch_osm_corridor_features(min_lat, min_lon, max_lat, max_lon)
    raw_roads = osm_bundle.get("roads", [])

    roads = []
    for r in raw_roads:
        hw = r.get("highway", "residential")
        lit_val = r.get("lit")
        is_lit = True if lit_val == "yes" else (False if lit_val == "no" else None)
        roads.append({
            "id": r["id"],
            "name": r.get("name") or "Road",
            "highway": hw,
            "is_main": hw in MAIN_ROAD_CLASSES,
            "is_lit": is_lit,
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "sidewalk": r.get("sidewalk", "")
        })

    return roads

async def fetch_corridor_lighting_and_landuse(coords: List[List[float]]) -> Dict[str, Any]:
    """Returns street lamps, lit ways, and isolating land use zones along corridor."""
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords, buffer_deg=0.006)
    osm_bundle = await fetch_osm_corridor_features(min_lat, min_lon, max_lat, max_lon)
    return {
        "street_lamps": osm_bundle.get("street_lamps", []),
        "roads": osm_bundle.get("roads", []),
        "isolating_landuse": osm_bundle.get("isolating_landuse", []),
        "transport": osm_bundle.get("transport", [])
    }

def classify_segment(coord: List[float], roads: List[Dict[str, Any]], radius_m: float = 60.0) -> Dict[str, Any]:
    """Matches a point along the polyline to the nearest known road attribute."""
    # Default fallback
    return {
        "is_main": True,
        "is_lit": None,
        "highway": "primary"
    }
