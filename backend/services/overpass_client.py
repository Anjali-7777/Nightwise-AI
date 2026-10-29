import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import httpx
from ..config import USER_AGENT
from .osm_cache import osm_cache

logger = logging.getLogger("nightwise.overpass")

# Configured Overpass API mirrors
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

# Request queue semaphore to prevent hammering public infrastructure
_OVERPASS_SEMAPHORE = asyncio.Semaphore(2)
_mirror_index = 0

def get_next_mirror() -> str:
    global _mirror_index
    mirror = OVERPASS_MIRRORS[_mirror_index % len(OVERPASS_MIRRORS)]
    _mirror_index += 1
    return mirror

def build_corridor_overpass_query(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    """
    Constructs a comprehensive Overpass QL query covering places, transport,
    cameras, street lamps, lit ways, road classes, and isolating land use.
    """
    bbox = f"{min_lat:.5f},{min_lon:.5f},{max_lat:.5f},{max_lon:.5f}"
    return f"""
    [out:json][timeout:25];
    (
      // 1. Places (verified social support, commerce, medical, emergency)
      node["amenity"~"pharmacy|hospital|clinic|doctors|police|fire_station|fuel|restaurant|cafe|fast_food|bar|pub|atm|bank|bus_station|taxi|cinema|marketplace"]({bbox});
      node["shop"]({bbox});
      node["tourism"~"hotel|guest_house"]({bbox});
      node["healthcare"]({bbox});
      node["emergency"~"phone|ambulance_station"]({bbox});

      // 2. Transport
      node["highway"="bus_stop"]({bbox});
      node["railway"~"station|subway_entrance|tram_stop"]({bbox});
      node["public_transport"]({bbox});

      // 3. Surveillance Cameras
      node["man_made"="surveillance"]({bbox});
      node["surveillance"]({bbox});

      // 4. Street Lamps
      node["highway"="street_lamp"]({bbox});

      // 5. Roads and Sidewalks (with lit & classification tags)
      way["highway"]({bbox});

      // 6. Land Use & Surroundings (isolated vs active)
      way["landuse"~"industrial|forest|farmland|construction|cemetery|military"]({bbox});
      way["natural"~"wood|water|scrub"]({bbox});
      way["leisure"="park"]({bbox});
      way["railway"]({bbox});
    );
    out body center;
    """

async def query_overpass_raw(query_str: str, retries: int = 2) -> Optional[Dict[str, Any]]:
    """
    Executes an Overpass QL query with mirror rotation, 25s timeout,
    exponential backoff, and async semaphore throttling.
    """
    async with _OVERPASS_SEMAPHORE:
        for attempt in range(retries + 1):
            mirror = get_next_mirror()
            backoff = 1.0 * (2 ** attempt)
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(
                        mirror,
                        data={"data": query_str},
                        headers={
                            "User-Agent": f"NightWiseAI/2.0 (Women Night Navigation; {USER_AGENT})"
                        }
                    )
                    if resp.status_code == 200:
                        return resp.json()
                    elif resp.status_code in [429, 502, 503, 504]:
                        logger.warning(f"Overpass mirror {mirror} returned {resp.status_code}. Backing off {backoff}s...")
                        await asyncio.sleep(backoff)
            except Exception as e:
                logger.warning(f"Overpass mirror {mirror} request failed: {e}. Retrying with next mirror...")
                await asyncio.sleep(backoff)
    return None

def parse_osm_elements(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parses raw Overpass JSON elements into structured collections:
    places, transport, cameras, street_lamps, roads, and isolating_landuse.
    """
    places = []
    transport = []
    cameras = []
    street_lamps = []
    roads = []
    isolating_landuse = []

    HELP_AMENITIES = {"police", "hospital", "clinic", "doctors", "pharmacy", "fuel", "fire_station", "emergency_phone"}
    TRANSPORT_AMENITIES = {"bus_station", "taxi", "bus_stop", "station", "subway_entrance", "tram_stop"}

    for el in elements:
        tags = el.get("tags", {})
        el_type = el.get("type")
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        name = tags.get("name", "")
        amenity = tags.get("amenity", "")
        shop = tags.get("shop", "")
        highway = tags.get("highway", "")
        railway = tags.get("railway", "")
        man_made = tags.get("man_made", "")
        opening_hours = tags.get("opening_hours", "")

        # 1. Cameras
        if man_made == "surveillance" or "surveillance" in tags:
            cameras.append({
                "id": f"cam-{el.get('id')}",
                "lat": lat,
                "lon": lon,
                "type": tags.get("surveillance:type", tags.get("surveillance", "camera")),
                "operator": tags.get("operator", "public")
            })

        # 2. Street Lamps
        if highway == "street_lamp":
            street_lamps.append({
                "id": f"lamp-{el.get('id')}",
                "lat": lat,
                "lon": lon
            })

        # 3. Transport
        if (highway == "bus_stop" or railway in ["station", "subway_entrance", "tram_stop"] or
            amenity in ["bus_station", "taxi"] or "public_transport" in tags):
            transport.append({
                "id": f"tr-{el.get('id')}",
                "name": name or f"Transit ({highway or railway or amenity})",
                "category": "transport",
                "lat": lat,
                "lon": lon,
                "opening_hours": opening_hours or ("24/7" if railway == "station" else "")
            })

        # 4. Help Points & Places
        is_help = amenity in HELP_AMENITIES or shop == "chemist" or tags.get("emergency") in ["phone", "ambulance_station"]
        is_place = (amenity or shop or tags.get("tourism") in ["hotel", "guest_house"] or tags.get("healthcare"))

        if is_place and lat and lon:
            cat = "shop"
            if amenity == "police": cat = "police"
            elif amenity in ["hospital", "clinic", "doctors"] or tags.get("healthcare"): cat = "hospital"
            elif amenity == "pharmacy" or shop == "chemist": cat = "pharmacy"
            elif amenity == "fuel": cat = "petrol_pump"
            elif amenity in ["restaurant", "cafe", "fast_food", "bar", "pub"]: cat = "restaurant"
            elif amenity in ["atm", "bank"]: cat = "atm"
            elif tags.get("tourism") in ["hotel", "guest_house"]: cat = "hotel"

            places.append({
                "id": f"osm-{el.get('id')}",
                "name": name or f"Local {cat.title()}",
                "category": cat,
                "display_category": cat.replace("_", " ").title(),
                "lat": lat,
                "lon": lon,
                "opening_hours": opening_hours,
                "is_help_point": is_help,
                "is_24x7": "24/7" in opening_hours.lower() or cat in ["police", "hospital"]
            })

        # 5. Roads (ways)
        if el_type == "way" and highway:
            lit_val = tags.get("lit", "")
            roads.append({
                "id": f"way-{el.get('id')}",
                "highway": highway,
                "name": name,
                "lit": lit_val,
                "sidewalk": tags.get("sidewalk", ""),
                "oneway": tags.get("oneway", "no") == "yes",
                "maxspeed": tags.get("maxspeed", ""),
                "nodes": el.get("nodes", []),
                "lat": lat,
                "lon": lon
            })

        # 6. Isolating Land Use / Barriers
        landuse = tags.get("landuse", "")
        natural = tags.get("natural", "")
        leisure = tags.get("leisure", "")
        if (landuse in ["industrial", "forest", "farmland", "construction", "cemetery", "military"] or
            natural in ["wood", "water", "scrub"] or leisure == "park" or (el_type == "way" and railway)):
            isolating_landuse.append({
                "id": f"iso-{el.get('id')}",
                "type": landuse or natural or leisure or "railway",
                "lat": lat,
                "lon": lon
            })

    return {
        "places": places,
        "transport": transport,
        "cameras": cameras,
        "street_lamps": street_lamps,
        "roads": roads,
        "isolating_landuse": isolating_landuse
    }

async def fetch_osm_corridor_features(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> Dict[str, Any]:
    """
    High-level fetcher:
    1. Checks local SQLite 0.01-deg tile cache.
    2. Identifies any missing tiles.
    3. Fetches missing tiles from Overpass mirrors.
    4. Merges and returns deduplicated corridor features.
    """
    tiles = osm_cache.get_tiles_for_bbox(min_lat, min_lon, max_lat, max_lon)
    missing_tiles = []
    cached_data_list = []

    for lat_idx, lon_idx in tiles:
        t_data = osm_cache.get_tile(lat_idx, lon_idx)
        if t_data is not None:
            cached_data_list.append(t_data)
        else:
            missing_tiles.append((lat_idx, lon_idx))

    if missing_tiles:
        logger.info(f"[OSM] Querying {len(missing_tiles)} missing tiles across bbox ({min_lat:.3f}, {min_lon:.3f}) to ({max_lat:.3f}, {max_lon:.3f})")
        q = build_corridor_overpass_query(min_lat, min_lon, max_lat, max_lon)
        raw_res = await query_overpass_raw(q)
        
        if raw_res and "elements" in raw_res:
            parsed = parse_osm_elements(raw_res["elements"])
            
            # Save into tile cache for each tile in bbox
            for lat_idx, lon_idx in missing_tiles:
                t_min_lat, t_min_lon, t_max_lat, t_max_lon = osm_cache.tile_bounds(lat_idx, lon_idx)
                # Filter elements that fall within this tile
                tile_payload = {
                    "places": [p for p in parsed["places"] if t_min_lat <= p["lat"] < t_max_lat and t_min_lon <= p["lon"] < t_max_lon],
                    "transport": [t for t in parsed["transport"] if t_min_lat <= t["lat"] < t_max_lat and t_min_lon <= t["lon"] < t_max_lon],
                    "cameras": [c for c in parsed["cameras"] if t_min_lat <= c["lat"] < t_max_lat and t_min_lon <= c["lon"] < t_max_lon],
                    "street_lamps": [l for l in parsed["street_lamps"] if t_min_lat <= l["lat"] < t_max_lat and t_min_lon <= l["lon"] < t_max_lon],
                    "roads": [r for r in parsed["roads"] if r.get("lat") and t_min_lat <= r["lat"] < t_max_lat and t_min_lon <= r["lon"] < t_max_lon],
                    "isolating_landuse": [u for u in parsed["isolating_landuse"] if u.get("lat") and t_min_lat <= u["lat"] < t_max_lat and t_min_lon <= u["lon"] < t_max_lon]
                }
                osm_cache.save_tile(lat_idx, lon_idx, tile_payload, ttl_days=7.0)
            cached_data_list.append(parsed)

    # Aggregate and deduplicate across tiles
    merged_places = {}
    merged_transport = {}
    merged_cameras = {}
    merged_lamps = {}
    merged_roads = {}
    merged_landuse = {}

    for d in cached_data_list:
        for p in d.get("places", []): merged_places[p["id"]] = p
        for t in d.get("transport", []): merged_transport[t["id"]] = t
        for c in d.get("cameras", []): merged_cameras[c["id"]] = c
        for l in d.get("street_lamps", []): merged_lamps[l["id"]] = l
        for r in d.get("roads", []): merged_roads[r["id"]] = r
        for u in d.get("isolating_landuse", []): merged_landuse[u["id"]] = u

    return {
        "places": list(merged_places.values()),
        "transport": list(merged_transport.values()),
        "cameras": list(merged_cameras.values()),
        "street_lamps": list(merged_lamps.values()),
        "roads": list(merged_roads.values()),
        "isolating_landuse": list(merged_landuse.values())
    }
