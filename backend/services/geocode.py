import json
import re
import hashlib
from pathlib import Path
import httpx
from ..config import GEOAPIFY_API_KEY, USER_AGENT, CACHE_DIR

GEO_CACHE_FILE = CACHE_DIR / "geocode_cache.json"

# Canonical high-precision gazetteer across major Indian metropolitan areas
INDIA_GAZETTEER = {
    # --- Nagpur ---
    "rub collage nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rub college nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rub nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rub collage": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rub college": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rbu college nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rbu nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rbu college": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rbu": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rcoem nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "rcoem": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "ramdeobaba college nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "ramdeobaba college": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "ramdeobaba university nagpur": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "ramdeobaba university": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},
    "ramdeobaba": {"lat": 21.1767, "lon": 79.0620, "name": "Ramdeobaba University (RBU / RCOEM College), Katol Road, Nagpur", "city": "Nagpur"},

    "vr mall nagpur": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "vr mall, nagpur": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "vr nagpur": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "vr mall": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "trillium mall nagpur": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "trillium mall": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "trilium mall nagpur": {"lat": 21.1320, "lon": 79.0962, "name": "VR Mall Nagpur (formerly Trillium Mall), Medical Square, Untkhana, Nagpur", "city": "Nagpur"},

    "vnit nagpur": {"lat": 21.1256, "lon": 79.0522, "name": "VNIT (Visvesvaraya National Institute of Technology), South Ambazari Road, Nagpur", "city": "Nagpur"},
    "vnit": {"lat": 21.1256, "lon": 79.0522, "name": "VNIT (Visvesvaraya National Institute of Technology), South Ambazari Road, Nagpur", "city": "Nagpur"},
    "sitabuldi": {"lat": 21.1458, "lon": 79.0882, "name": "Sitabuldi Interchange Metro Station, Nagpur", "city": "Nagpur"},
    "sitabuldi metro": {"lat": 21.1458, "lon": 79.0882, "name": "Sitabuldi Interchange Metro Station, Nagpur", "city": "Nagpur"},
    "sitabuldi nagpur": {"lat": 21.1458, "lon": 79.0882, "name": "Sitabuldi Interchange Metro Station, Nagpur", "city": "Nagpur"},
    "nagpur railway station": {"lat": 21.1524, "lon": 79.0889, "name": "Nagpur Junction Railway Station, Nagpur", "city": "Nagpur"},
    "nagpur junction": {"lat": 21.1524, "lon": 79.0889, "name": "Nagpur Junction Railway Station, Nagpur", "city": "Nagpur"},
    "futala lake nagpur": {"lat": 21.1565, "lon": 79.0435, "name": "Futala Lake, Telangkhedi, Nagpur", "city": "Nagpur"},
    "futala lake": {"lat": 21.1565, "lon": 79.0435, "name": "Futala Lake, Telangkhedi, Nagpur", "city": "Nagpur"},
    "futala": {"lat": 21.1565, "lon": 79.0435, "name": "Futala Lake, Telangkhedi, Nagpur", "city": "Nagpur"},
    "eternity mall nagpur": {"lat": 21.1447, "lon": 79.0831, "name": "Eternity Mall, Variety Square, Sitabuldi, Nagpur", "city": "Nagpur"},
    "eternity mall": {"lat": 21.1447, "lon": 79.0831, "name": "Eternity Mall, Variety Square, Sitabuldi, Nagpur", "city": "Nagpur"},
    "central mall nagpur": {"lat": 21.1377, "lon": 79.0688, "name": "Central Mall, Ramdaspeth, Nagpur", "city": "Nagpur"},
    "gmc nagpur": {"lat": 21.1306, "lon": 79.0982, "name": "Government Medical College (GMC), Medical Square, Nagpur", "city": "Nagpur"},
    "medical square nagpur": {"lat": 21.1306, "lon": 79.0982, "name": "Medical Square, Untkhana, Nagpur", "city": "Nagpur"},
    "dharampeth nagpur": {"lat": 21.1432, "lon": 79.0629, "name": "Dharampeth, Nagpur", "city": "Nagpur"},
    "dharampeth": {"lat": 21.1432, "lon": 79.0629, "name": "Dharampeth, Nagpur", "city": "Nagpur"},
    "sadar nagpur": {"lat": 21.1605, "lon": 79.0835, "name": "Sadar Residency Road, Nagpur", "city": "Nagpur"},
    "sadar": {"lat": 21.1605, "lon": 79.0835, "name": "Sadar Residency Road, Nagpur", "city": "Nagpur"},
    "it park nagpur": {"lat": 21.1190, "lon": 79.0450, "name": "IT Park, Gayatri Nagar, Parsodi, Nagpur", "city": "Nagpur"},
    "aiims nagpur": {"lat": 21.0506, "lon": 79.0255, "name": "AIIMS Nagpur, MIHAN, Nagpur", "city": "Nagpur"},
    "mahal nagpur": {"lat": 21.1435, "lon": 79.1120, "name": "Mahal, Nagpur", "city": "Nagpur"},

    # --- Bengaluru ---
    "church street": {"lat": 12.9749, "lon": 77.6074, "name": "Church Street, Bengaluru", "city": "Bengaluru"},
    "church street, bengaluru": {"lat": 12.9749, "lon": 77.6074, "name": "Church Street, Bengaluru", "city": "Bengaluru"},
    "indiranagar": {"lat": 12.9784, "lon": 77.6408, "name": "Indiranagar, Bengaluru", "city": "Bengaluru"},
    "indiranagar metro": {"lat": 12.9784, "lon": 77.6408, "name": "Indiranagar Metro Station, Bengaluru", "city": "Bengaluru"},
    "koramangala sony signal": {"lat": 12.9352, "lon": 77.6245, "name": "Sony World Signal, Koramangala, Bengaluru", "city": "Bengaluru"},
    "koramangala": {"lat": 12.9352, "lon": 77.6245, "name": "Koramangala, Bengaluru", "city": "Bengaluru"},
    "mg road metro": {"lat": 12.9756, "lon": 77.6066, "name": "MG Road Metro Station, Bengaluru", "city": "Bengaluru"},
    "mg road": {"lat": 12.9756, "lon": 77.6066, "name": "MG Road, Bengaluru", "city": "Bengaluru"},
    "majestic station": {"lat": 12.9779, "lon": 77.5724, "name": "KSR Bengaluru City Railway Station (Majestic)", "city": "Bengaluru"},
    "cubbon park": {"lat": 12.9763, "lon": 77.5929, "name": "Cubbon Park, Bengaluru", "city": "Bengaluru"},
    "hsr layout": {"lat": 12.9121, "lon": 77.6446, "name": "HSR Layout Sector 1, Bengaluru", "city": "Bengaluru"},
    "whitefield": {"lat": 12.9698, "lon": 77.7499, "name": "Whitefield Main Road, Bengaluru", "city": "Bengaluru"},
    "office": {"lat": 12.9749, "lon": 77.6074, "name": "Office (Church Street, Bengaluru)", "city": "Bengaluru"},
    "home": {"lat": 12.9784, "lon": 77.6408, "name": "Home (Indiranagar, Bengaluru)", "city": "Bengaluru"},

    # --- Delhi ---
    "connaught place": {"lat": 28.6315, "lon": 77.2167, "name": "Connaught Place Inner Circle, New Delhi", "city": "Delhi"},
    "hauz khas": {"lat": 28.5494, "lon": 77.2001, "name": "Hauz Khas Village, New Delhi", "city": "Delhi"},
    "delhi university": {"lat": 28.6892, "lon": 77.2104, "name": "Delhi University North Campus, New Delhi", "city": "Delhi"},

    # --- Mumbai ---
    "bandra station": {"lat": 19.0544, "lon": 72.8402, "name": "Bandra Railway Station, Mumbai", "city": "Mumbai"},
    "marine drive": {"lat": 18.9438, "lon": 72.8232, "name": "Marine Drive Promenade, Mumbai", "city": "Mumbai"},
    "bkc": {"lat": 19.0657, "lon": 72.8687, "name": "Bandra Kurla Complex (BKC), Mumbai", "city": "Mumbai"},

    # --- Hyderabad ---
    "hitec city": {"lat": 17.4474, "lon": 78.3762, "name": "HITEC City Cyber Towers, Hyderabad", "city": "Hyderabad"},
    "charminar": {"lat": 17.3616, "lon": 78.4747, "name": "Charminar, Old City, Hyderabad", "city": "Hyderabad"},

    # --- Pune ---
    "fc road pune": {"lat": 18.5283, "lon": 73.8415, "name": "Fergusson College Road, Shivajinagar, Pune", "city": "Pune"},
    "koregaon park": {"lat": 18.5362, "lon": 73.8940, "name": "Koregaon Park, Pune", "city": "Pune"},
    "pune station": {"lat": 18.5284, "lon": 73.8744, "name": "Pune Railway Station, Pune", "city": "Pune"},
}

def normalize_query(query: str) -> str:
    """Preprocesses user queries to normalize common typos, abbreviations, and Indian transliterations."""
    s = query.strip().lower()
    # Normalize common spelling variants
    s = re.sub(r'\bcollage\b', 'college', s)
    s = re.sub(r'\buniversty\b', 'university', s)
    s = re.sub(r'\bstn\b', 'station', s)
    s = re.sub(r'\brly\b', 'railway', s)
    s = re.sub(r'\brd\b', 'road', s)
    s = re.sub(r'\bmkt\b', 'market', s)
    s = re.sub(r'\bsq\b', 'square', s)
    # Acronym expansion for central Indian landmarks
    if 'rub' in s and ('nagpur' in s or 'college' in s):
        s = s.replace('rub', 'rbu')
    return s

def _load_cache() -> dict:
    if GEO_CACHE_FILE.exists():
        try:
            return json.loads(GEO_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    try:
        GEO_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass

async def geocode(query: str) -> list[dict]:
    """
    Geocodes a query string biased to India.
    Returns list of dicts: [{"name": str, "lat": float, "lon": float, "address": str, "provider": str}]
    """
    raw_clean = query.strip().lower()
    if not raw_clean:
        return []

    norm_q = normalize_query(raw_clean)

    # 1. Primary Priority: Check Canonical High-Precision Indian Gazetteer
    # Exact match on normalized or raw query
    if norm_q in INDIA_GAZETTEER:
        v = INDIA_GAZETTEER[norm_q]
        return [{
            "name": v["name"],
            "lat": v["lat"],
            "lon": v["lon"],
            "address": v["name"],
            "provider": "canonical_gazetteer"
        }]

    if raw_clean in INDIA_GAZETTEER:
        v = INDIA_GAZETTEER[raw_clean]
        return [{
            "name": v["name"],
            "lat": v["lat"],
            "lon": v["lon"],
            "address": v["name"],
            "provider": "canonical_gazetteer"
        }]

    # Substring / key containment check in canonical gazetteer
    for k, v in INDIA_GAZETTEER.items():
        if norm_q == k:
            return [{
                "name": v["name"],
                "lat": v["lat"],
                "lon": v["lon"],
                "address": v["name"],
                "provider": "canonical_gazetteer"
            }]
        # If both mention the same city or specific landmark
        if ("nagpur" in norm_q and "nagpur" in k) or ("bengaluru" in norm_q and "bengaluru" in k):
            if (norm_q in k and len(norm_q) >= 4) or (k in norm_q and len(k) >= 4):
                return [{
                    "name": v["name"],
                    "lat": v["lat"],
                    "lon": v["lon"],
                    "address": v["name"],
                    "provider": "canonical_gazetteer"
                }]

    # 2. Check Disk Cache
    cache = _load_cache()
    if norm_q in cache:
        return cache[norm_q]

    # 3. Geoapify Geocoding & Autocomplete API
    if GEOAPIFY_API_KEY:
        try:
            # Query Geoapify with normalized query
            api_q = norm_q if norm_q != raw_clean else query
            url = f"https://api.geoapify.com/v1/geocode/autocomplete?text={api_q}&filter=countrycode:in&bias=countrycode:in&limit=8&apiKey={GEOAPIFY_API_KEY}"
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    raw_results = []
                    for f in features:
                        props = f.get("properties", {})
                        coords = f.get("geometry", {}).get("coordinates", [0, 0])
                        formatted = props.get("formatted", props.get("name", query))
                        raw_results.append({
                            "name": formatted,
                            "lat": coords[1],
                            "lon": coords[0],
                            "address": formatted,
                            "city": props.get("city", ""),
                            "state": props.get("state", ""),
                            "category": props.get("category", ""),
                            "provider": "geoapify"
                        })
                    
                    if raw_results:
                        # Intelligent Re-Ranking:
                        # If user query specifically mentions a city, boost matching results
                        city_match = None
                        for c in ["nagpur", "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "kolkata"]:
                            if c in norm_q:
                                city_match = c
                                break

                        def rank_item(item):
                            score = 0.0
                            item_text = (item["name"] + " " + item["address"] + " " + item.get("city", "")).lower()
                            
                            # City adherence boost
                            if city_match:
                                if city_match in item_text:
                                    score += 100.0
                                else:
                                    score -= 80.0 # Strongly demote results from other cities
                            
                            # Specific POI matching boost
                            if "vr" in norm_q and ("trillium" in item_text or "vr" in item_text):
                                score += 50.0
                            if "mall" in norm_q and "mall" in item_text:
                                score += 20.0
                            if ("college" in norm_q or "rbu" in norm_q) and ("ramdeobaba" in item_text or "college" in item_text):
                                score += 50.0
                            
                            return score

                        raw_results.sort(key=rank_item, reverse=True)
                        
                        # Strip internal metadata before returning
                        final_results = [{
                            "name": r["name"],
                            "lat": r["lat"],
                            "lon": r["lon"],
                            "address": r["address"],
                            "provider": r["provider"]
                        } for r in raw_results]

                        cache[norm_q] = final_results
                        _save_cache(cache)
                        return final_results
        except Exception:
            pass

    # 4. Fallback search across canonical gazetteer for partial match
    for k, v in INDIA_GAZETTEER.items():
        if k in norm_q or norm_q in k:
            res = [{
                "name": v["name"],
                "lat": v["lat"],
                "lon": v["lon"],
                "address": v["name"],
                "provider": "canonical_gazetteer"
            }]
            cache[norm_q] = res
            _save_cache(cache)
            return res

    # 5. Nominatim (OpenStreetMap) Fallback
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={norm_q}&format=json&countrycodes=in&limit=5"
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data[:5]:
                    results.append({
                        "name": item.get("display_name", query),
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "address": item.get("display_name", ""),
                        "provider": "nominatim"
                    })
                if results:
                    cache[norm_q] = results
                    _save_cache(cache)
                    return results
    except Exception:
        pass

    # 6. Default fallback
    fallback = [{
        "name": f"{query.title()} (Estimated Location, India)",
        "lat": 21.1458 if "nagpur" in norm_q else 12.9756,
        "lon": 79.0882 if "nagpur" in norm_q else 77.6066,
        "address": f"{query.title()}, India",
        "provider": "default_fallback"
    }]
    return fallback

async def reverse_geocode(lat: float, lon: float) -> str:
    """Reverse geocodes coordinates to a readable address."""
    # Check nearest in local gazetteer
    for v in INDIA_GAZETTEER.values():
        if abs(v["lat"] - lat) < 0.005 and abs(v["lon"] - lon) < 0.005:
            return v["name"]

    if GEOAPIFY_API_KEY:
        try:
            url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={GEOAPIFY_API_KEY}"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    data = resp.json()
                    feats = data.get("features", [])
                    if feats:
                        return feats[0].get("properties", {}).get("formatted", f"{lat:.4f}, {lon:.4f}")
        except Exception:
            pass

    return f"Location ({lat:.4f}, {lon:.4f})"
