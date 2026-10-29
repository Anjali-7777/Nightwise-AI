import sys
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

def verify():
    print("==================================================")
    print("        NightWise AI Live API Verification        ")
    print("==================================================")

    client = httpx.Client(timeout=60.0)

    # 1. Config endpoint
    print("\n[1] Testing GET /api/config...")
    r = client.get(f"{BASE_URL}/api/config")
    assert r.status_code == 200, f"Config failed: {r.status_code}"
    cfg = r.json()
    print("Config response:", cfg)

    # 2. Routes endpoint: Nagpur (RUB College to VR Mall)
    print("\n[2] Testing POST /api/routes (Nagpur Corridor)...")
    payload = {
        "origin": "RUB College Nagpur",
        "destination": "VR Mall Nagpur",
        "mode": "walking",
        "departure_time": "2:00 AM"
    }
    r = client.post(f"{BASE_URL}/api/routes", json=payload)
    assert r.status_code == 200, f"Routes failed: {r.status_code} - {r.text}"
    routes_data = r.json()
    print(f"Generated {len(routes_data.get('routes', []))} route options:")
    for idx, rt in enumerate(routes_data.get("routes", [])):
        print(f"  Route {idx+1} ({rt.get('label')}): Dist={rt.get('distance_m')}m, Duration={rt.get('duration_s')}s, NightScore={rt.get('night_score')}, Confidence={rt.get('data_confidence')}")
        print(f"    Breakdown rows: {len(rt.get('breakdown', {}))}")
        for k, v in rt.get('breakdown', {}).items():
            print(f"      - {v.get('name')}: {v.get('points')}/{v.get('max_points')} pts ({v.get('raw_value')})")

    # 3. Agent endpoint: Natural Language Query
    print("\n[3] Testing POST /api/agent (Natural Language Agent)...")
    agent_payload = {
        "message": "I want to walk from RUB College Nagpur to VR Mall Nagpur at 2 AM. Which route is safer and why?"
    }
    r = client.post(f"{BASE_URL}/api/agent", json=agent_payload)
    assert r.status_code == 200, f"Agent failed: {r.status_code} - {r.text}"
    agent_data = r.json()
    print("Agent Trade-off Summary:")
    print(agent_data.get("trade_off_summary"))
    print("\nRoute Identification:")
    print(f"  Fastest Route ID: {agent_data.get('fastest_route_id')}")
    print(f"  Safest Route ID:  {agent_data.get('safest_route_id')}")
    print(f"  Recommendation:   {agent_data.get('recommendation')}")
    print(f"  Total Scored Routes: {len(agent_data.get('routes', []))}")

    # 4. Attention Explorer endpoint
    print("\n[4] Testing POST /api/attention (Transformer Visualizer)...")
    attn_payload = {
        "text": "safest route walking at 2am"
    }
    r = client.post(f"{BASE_URL}/api/attention", json=attn_payload)
    assert r.status_code == 200, f"Attention failed: {r.status_code} - {r.text}"
    attn_data = r.json()
    tokens = attn_data.get("tokens", [])
    layers = attn_data.get("layers", [])
    print(f"Attention tokens count: {len(tokens)} -> {tokens[:6]}...")
    print(f"Layers extracted: {len(layers)} layers")

    print("\n==================================================")
    print("      ALL LIVE ENDPOINTS SUCCESSFULLY VERIFIED    ")
    print("==================================================")

if __name__ == "__main__":
    verify()
