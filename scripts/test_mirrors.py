import httpx
import time

mirrors = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter"
]

q = "[out:json][timeout:15]; node[\"amenity\"=\"hospital\"](12.97,77.60,12.98,77.62); out count;"

for m in mirrors:
    t0 = time.time()
    try:
        r = httpx.post(m, data={"data": q}, headers={"User-Agent": "NightWiseAI/2.0"}, timeout=12.0)
        print(f"{m} -> {r.status_code} in {time.time()-t0:.2f}s (len {len(r.text)})", flush=True)
    except Exception as e:
        print(f"{m} -> FAIL in {time.time()-t0:.2f}s: {e}", flush=True)
