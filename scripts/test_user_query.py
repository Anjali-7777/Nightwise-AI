import httpx
import json

def test():
    # Test routes
    print("Testing /api/routes with user query:")
    resp = httpx.post('http://127.0.0.1:8000/api/routes', json={
        'origin': 'RUB Collage Nagpur',
        'destination': 'VR mall nagpur',
        'mode': 'walking',
        'departure_time': '10:00 PM'
    }, timeout=30.0)
    print('Status:', resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        print('Origin:', data.get('origin'))
        print('Destination:', data.get('destination'))
        print('Num routes:', len(data.get('routes', [])))
        for r in data.get('routes', []):
            print(f"Route {r.get('id')}: {r.get('name')} - dist: {r.get('distance_km')}km, dur: {r.get('duration_min')}m, score: {r.get('night_score')}")
    else:
        print('Error:', resp.text)

    # Test agent
    print("\nTesting /api/agent with natural language:")
    resp = httpx.post('http://127.0.0.1:8000/api/agent', json={
        'message': 'i want to go from RUB Collage Nagpur to VR mall nagpur'
    }, timeout=45.0)
    print('Agent Status:', resp.status_code)
    if resp.status_code == 200:
        d = resp.json()
        print('Parsed:', d.get('parsed'))
        print('Recommendation:', d.get('recommendation'))
        print('Trade-off:', d.get('trade_off_summary'))
    else:
        print('Agent Error:', resp.text)

if __name__ == '__main__':
    test()
