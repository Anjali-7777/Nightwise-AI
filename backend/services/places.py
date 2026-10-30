import math
import time
import logging
from typing import List, Dict, Any, Tuple
import httpx
from ..config import GEOAPIFY_API_KEY, USER_AGENT
from .overpass_client import fetch_osm_corridor_features

logger = logging.getLogger("nightwise.places")

HELP_POINT_CATEGORIES = {
    "police", "hospital", "clinic", "doctors", "pharmacy",
    "petrol_pump", "fire_station", "emergency_phone"
}

# In-memory LRU-like cache for Geoapify responses
_GEOAPIFY_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 3600.0  # 1 hour

def haversine_dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def name_similarity(name1: str, name2: str) -> float:
    s1 = set(name1.lower().replace(",", " ").split())
    s2 = set(name2.lower().replace(",", " ").split())
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / max(len(s1), len(s2))

def get_bounding_box(coords: List[List[float]], buffer_deg: float = 0.008) -> tuple[float, float, float, float]:
    lats = [p[0] for p in coords]
    lons = [p[1] for p in coords]
    return (
        min(lats) - buffer_deg,
        min(lons) - buffer_deg,
        max(lats) + buffer_deg,
        max(lons) + buffer_deg,
    )

async def fetch_supplementary_geoapify_places(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> List[Dict[str, Any]]:
    """Supplementary places from Geoapify Places API with fast memory caching."""
    if not GEOAPIFY_API_KEY:
        return []

    # Quantize bounding box to ~0.005 deg (~500m) for high cache hit rate
    cache_key = f"{round(min_lat, 3)},{round(min_lon, 3)},{round(max_lat, 3)},{round(max_lon, 3)}"
    now = time.time()
    if cache_key in _GEOAPIFY_CACHE:
        ts, cached_places = _GEOAPIFY_CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return cached_places

    try:
        cats = "commercial.supermarket,catering.restaurant,catering.cafe,service.financial.atm,healthcare.pharmacy,healthcare.hospital,service.police,service.vehicle.fuel"
        url = f"https://api.geoapify.com/v2/places?categories={cats}&filter=rect:{min_lon},{min_lat},{max_lon},{max_lat}&limit=60&apiKey={GEOAPIFY_API_KEY}"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                features = resp.json().get("features", [])
                results = []
                for f in features:
                    props = f.get("properties", {})
                    coords = f.get("geometry", {}).get("coordinates", [0, 0])
                    g_cat = props.get("categories", ["shop"])[0]
                    cat = "shop"
                    if "police" in g_cat: cat = "police"
                    elif "pharmacy" in g_cat: cat = "pharmacy"
                    elif "healthcare" in g_cat: cat = "hospital"
                    elif "fuel" in g_cat: cat = "petrol_pump"
                    elif "catering" in g_cat: cat = "restaurant"
                    elif "atm" in g_cat: cat = "atm"

                    op_hours = props.get("opening_hours", "")
                    results.append({
                        "id": f"geo-{props.get('place_id', len(results))}",
                        "name": props.get("name", f"Local {cat.title()}"),
                        "category": cat,
                        "display_category": cat.replace("_", " ").title(),
                        "lat": coords[1],
                        "lon": coords[0],
                        "opening_hours": op_hours,
                        "is_help_point": cat in HELP_POINT_CATEGORIES,
                        "is_24x7": "24/7" in op_hours.lower() or cat in ["police", "hospital"],
                        "source": "geoapify"
                    })
                _GEOAPIFY_CACHE[cache_key] = (now, results)
                return results
    except Exception as e:
        logger.warning(f"Geoapify supplementary fetch skipped or timed out: {e}")
    return []

async def fetch_places_in_corridor(coords: List[List[float]]) -> List[Dict[str, Any]]:
    """
    Primary: OpenStreetMap via Overpass / SQLite tile cache.
    Supplementary: Geoapify Places.
    Merged and deduplicated within 25 m and name similarity.
    """
    if not coords:
        return []

    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords)

    # 1. Primary: OSM Features from Overpass / SQLite cache
    osm_bundle = await fetch_osm_corridor_features(min_lat, min_lon, max_lat, max_lon)
    osm_places = osm_bundle.get("places", [])
    for p in osm_places:
        p["source"] = "osm"

    # 2. Supplementary: Geoapify Places
    geo_places = await fetch_supplementary_geoapify_places(min_lat, min_lon, max_lat, max_lon)

    # 3. Merge & Deduplicate with spatial fast-pruning
    merged = list(osm_places)

    for gp in geo_places:
        gp_lat, gp_lon = gp["lat"], gp["lon"]
        is_dup = False
        for op in merged:
            op_lat, op_lon = op["lat"], op["lon"]
            # Fast degree box filter before trigonometric calculation
            if abs(gp_lat - op_lat) > 0.0006 or abs(gp_lon - op_lon) > 0.0006:
                continue
            d = haversine_dist_m(gp_lat, gp_lon, op_lat, op_lon)
            if d < 25.0:
                is_dup = True
                if not op.get("opening_hours") and gp.get("opening_hours"):
                    op["opening_hours"] = gp["opening_hours"]
                    op["is_24x7"] = gp["is_24x7"]
                break
            elif d < 45.0 and name_similarity(gp["name"], op["name"]) > 0.4:
                is_dup = True
                if not op.get("opening_hours") and gp.get("opening_hours"):
                    op["opening_hours"] = gp["opening_hours"]
                    op["is_24x7"] = gp["is_24x7"]
                break
        
        if not is_dup:
            merged.append(gp)

    return merged
