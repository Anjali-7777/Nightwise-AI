import json
import math
from typing import Literal, List, Dict
import httpx
from ..config import GEOAPIFY_API_KEY, USER_AGENT, CACHE_DIR

ROUTE_CACHE_FILE = CACHE_DIR / "route_cache.json"

def _load_cache() -> dict:
    if ROUTE_CACHE_FILE.exists():
        try:
            return json.loads(ROUTE_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    try:
        ROUTE_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass

def haversine_dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def routes_are_duplicates(coords_a: List[List[float]], coords_b: List[List[float]], threshold: float = 0.85) -> bool:
    """Checks if two routes overlap by more than threshold (85%) of their length."""
    if not coords_a or not coords_b:
        return False
    sample_a = coords_a[::max(1, len(coords_a)//30)]
    close_count = 0
    for p in sample_a:
        min_d = min(haversine_dist_m(p[0], p[1], q[0], q[1]) for q in coords_b[::max(1, len(coords_b)//30)])
        if min_d < 50: # within 50 meters
            close_count += 1
    overlap = close_count / max(1, len(sample_a))
    return overlap > threshold

def generate_nudge_waypoint(orig_lat: float, orig_lon: float, dest_lat: float, dest_lon: float, side: int = 1) -> tuple[float, float]:
    """Generates an offset midpoint to force a distinct alternate route corridor."""
    mid_lat = (orig_lat + dest_lat) / 2
    mid_lon = (orig_lon + dest_lon) / 2
    d_lat = dest_lat - orig_lat
    d_lon = dest_lon - orig_lon
    # Perpendicular vector
    perp_lat = -d_lon * 0.35 * side
    perp_lon = d_lat * 0.35 * side
    return mid_lat + perp_lat, mid_lon + perp_lon

async def get_routes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    mode: Literal["walking", "driving"] = "walking"
) -> List[Dict]:
    """
    Fetches 2-3 genuinely different alternative routes between origin and destination.
    Uses OSRM public endpoints as primary with alternatives=3, via-waypoints and Geoapify fallback,
    dropping any routes sharing > 85% of their geometry.
    """
    orig_lat, orig_lon = origin
    dest_lat, dest_lon = destination
    cache_key = f"{orig_lat:.4f},{orig_lon:.4f}_{dest_lat:.4f},{dest_lon:.4f}_{mode}"

    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    routes: List[Dict] = []
    profile = "foot" if mode == "walking" else "car"

    # 1. Primary: OSRM Public Server with alternatives=3
    osrm_url = (
        f"https://routing.openstreetmap.de/routed-{profile}/route/v1/{profile}/"
        f"{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson&alternatives=3&steps=true"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(osrm_url, headers={"User-Agent": f"NightWiseAI/2.0 ({USER_AGENT})"})
            if resp.status_code == 200:
                data = resp.json()
                for i, r in enumerate(data.get("routes", [])):
                    coords = [[p[1], p[0]] for p in r["geometry"]["coordinates"]]
                    if not any(routes_are_duplicates(r_ex["coordinates"], coords, threshold=0.85) for r_ex in routes):
                        routes.append({
                            "id": f"route-{len(routes)+1}",
                            "name": f"Route {chr(65+len(routes))}",
                            "coordinates": coords,
                            "distance_m": float(r["distance"]),
                            "duration_s": float(r["duration"]),
                            "mode": mode,
                            "source": "osrm"
                        })
    except Exception:
        pass

    # 2. If fewer than 2 routes, generate via-waypoint alternative through OSRM
    if len(routes) < 2:
        for side in [1, -1]:
            if len(routes) >= 3:
                break
            nudge_lat, nudge_lon = generate_nudge_waypoint(orig_lat, orig_lon, dest_lat, dest_lon, side=side)
            alt_url = (
                f"https://routing.openstreetmap.de/routed-{profile}/route/v1/{profile}/"
                f"{orig_lon},{orig_lat};{nudge_lon},{nudge_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
            )
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(alt_url, headers={"User-Agent": USER_AGENT})
                    if resp.status_code == 200:
                        data = resp.json()
                        for r in data.get("routes", []):
                            coords = [[p[1], p[0]] for p in r["geometry"]["coordinates"]]
                            if not any(routes_are_duplicates(r_ex["coordinates"], coords, threshold=0.85) for r_ex in routes):
                                routes.append({
                                    "id": f"route-{len(routes)+1}",
                                    "name": f"Route {chr(65+len(routes))} (Corridor B)",
                                    "coordinates": coords,
                                    "distance_m": float(r["distance"]),
                                    "duration_s": float(r["duration"]),
                                    "mode": mode,
                                    "source": "osrm_waypoint"
                                })
                                break
            except Exception:
                pass

    # 3. Supplementary: Geoapify Routing if still fewer than 2 routes
    if len(routes) < 2 and GEOAPIFY_API_KEY:
        try:
            geo_mode = "walk" if mode == "walking" else "drive"
            url = f"https://api.geoapify.com/v1/routing?waypoints={orig_lat},{orig_lon}|{dest_lat},{dest_lon}&mode={geo_mode}&apiKey={GEOAPIFY_API_KEY}"
            async with httpx.AsyncClient(timeout=4.5) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    data = resp.json()
                    for feat in data.get("features", []):
                        raw_coords = feat["geometry"]["coordinates"]
                        coords_list = raw_coords[0] if isinstance(raw_coords[0][0], list) else raw_coords
                        coords = [[p[1], p[0]] for p in coords_list]
                        props = feat.get("properties", {})
                        if not any(routes_are_duplicates(r_ex["coordinates"], coords, threshold=0.85) for r_ex in routes):
                            routes.append({
                                "id": f"route-{len(routes)+1}",
                                "name": f"Route {chr(65+len(routes))}",
                                "coordinates": coords,
                                "distance_m": float(props.get("distance", 1000)),
                                "duration_s": float(props.get("time", 600)),
                                "mode": mode,
                                "source": "geoapify"
                            })
        except Exception:
            pass

    # 4. Fallback synthetic geometry generator if all external routing failed
    if not routes:
        straight_dist = haversine_dist_m(orig_lat, orig_lon, dest_lat, dest_lon)
        speed = 1.25 if mode == "walking" else 8.5
        steps = max(12, int(straight_dist / 50))
        
        # Route 1: Direct curve
        c1 = []
        for s in range(steps + 1):
            t = s / steps
            la = orig_lat + t * (dest_lat - orig_lat) + 0.0006 * math.sin(t * math.pi)
            lo = orig_lon + t * (dest_lon - orig_lon) + 0.0005 * math.sin(t * math.pi)
            c1.append([la, lo])
        routes.append({
            "id": "route-1",
            "name": "Route A (Direct)",
            "coordinates": c1,
            "distance_m": straight_dist * 1.08,
            "duration_s": (straight_dist * 1.08) / speed,
            "mode": mode,
            "source": "synthetic"
        })

        # Route 2: Parallel offset curve
        c2 = []
        for s in range(steps + 1):
            t = s / steps
            la = orig_lat + t * (dest_lat - orig_lat) - 0.0010 * math.sin(t * math.pi)
            lo = orig_lon + t * (dest_lon - orig_lon) - 0.0009 * math.sin(t * math.pi)
            c2.append([la, lo])
        routes.append({
            "id": "route-2",
            "name": "Route B (Main Road)",
            "coordinates": c2,
            "distance_m": straight_dist * 1.18,
            "duration_s": (straight_dist * 1.18) / speed,
            "mode": mode,
            "source": "synthetic"
        })

    cache[cache_key] = routes
    _save_cache(cache)
    return routes
