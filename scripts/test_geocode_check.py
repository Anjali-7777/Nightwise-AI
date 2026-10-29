import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from backend.services.geocode import geocode

async def main():
    queries = [
        'RUB Collage Nagpur',
        'rub college nagpur',
        'RBU Nagpur',
        'VR mall nagpur',
        'VR Mall, Nagpur',
        'trillium mall nagpur',
        'Church Street',
        'Indiranagar',
        'VNIT Nagpur'
    ]
    print("\n--- Geocode Verification ---")
    for q in queries:
        res = await geocode(q)
        top = res[0]
        print(f"[{q}] -> ({top['lat']:.4f}, {top['lon']:.4f}) | {top['name']} (via {top['provider']})")

if __name__ == '__main__':
    asyncio.run(main())
