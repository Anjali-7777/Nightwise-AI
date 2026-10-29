import pytest
from datetime import datetime
from backend.scoring.night_score import score_route_v2

def create_real_city_route(name: str, coords: list, distance_m: float, duration_s: float):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "coordinates": coords,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "mode": "walking"
    }

# 1. Bengaluru Coordinates
# Route A: MG Road Arterial (well-lit, broad avenue)
BENGALURU_MG_ROAD = [[12.9756 + i * 0.0008, 77.6066 + i * 0.0004] for i in range(12)]
# Route B: Dark Interior Alleys (narrow, dead-end lanes)
BENGALURU_BACK_ALLEY = [[12.9756 + i * 0.0008, 77.6010 + i * 0.0002] for i in range(12)]

# 2. Nagpur Coordinates
# Route A: Katol Road Arterial to Sitabuldi
NAGPUR_MAIN_ROAD = [[21.1767 - i * 0.0040, 79.0620 + i * 0.0025] for i in range(12)]
# Route B: Desolate Rail & Scrub Border
NAGPUR_ISOLATED_PATH = [[21.1767 - i * 0.0040, 79.0510 + i * 0.0010] for i in range(12)]

# 3. Delhi Coordinates
# Route A: Connaught Place Outer Circle
DELHI_CP_MAIN = [[28.6315 + i * 0.0010, 77.2167 + i * 0.0015] for i in range(10)]
# Route B: Congested Dark Alleys
DELHI_ALLEY = [[28.6315 + i * 0.0010, 77.2080 + i * 0.0005] for i in range(10)]

# 4. Hyderabad Coordinates
# Route A: HITEC City Cyber Towers Avenue
HYDERABAD_HITEC_MAIN = [[17.4474 + i * 0.0012, 78.3762 + i * 0.0010] for i in range(10)]
# Route B: Interior Unlit Dirt Track
HYDERABAD_INTERIOR = [[17.4474 + i * 0.0012, 78.3680 + i * 0.0003] for i in range(10)]

# 5. Mumbai Coordinates
# Route A: Marine Drive Promenade
MUMBAI_MARINE_DRIVE = [[18.9438 + i * 0.0015, 72.8232 + i * 0.0008] for i in range(10)]
# Route B: Port Siding / Warehouse Stretch
MUMBAI_INDUSTRIAL = [[18.9438 + i * 0.0015, 72.8400 + i * 0.0002] for i in range(10)]

@pytest.mark.parametrize("city,main_coords,back_coords", [
    ("Bengaluru", BENGALURU_MG_ROAD, BENGALURU_BACK_ALLEY),
    ("Nagpur", NAGPUR_MAIN_ROAD, NAGPUR_ISOLATED_PATH),
    ("Delhi", DELHI_CP_MAIN, DELHI_ALLEY),
    ("Hyderabad", HYDERABAD_HITEC_MAIN, HYDERABAD_INTERIOR),
    ("Mumbai", MUMBAI_MARINE_DRIVE, MUMBAI_INDUSTRIAL)
])
def test_real_city_arterial_vs_isolated_ordering(city, main_coords, back_coords):
    dep_time = datetime(2026, 10, 29, 2, 0) # 2:00 AM walking

    route_main = create_real_city_route(f"{city} Main Arterial", main_coords, 1200.0, 900.0)
    route_back = create_real_city_route(f"{city} Isolated Back Lane", back_coords, 1150.0, 860.0)

    # Main road has 24/7 pharmacies, police booth, street lamps, and cameras
    mid_lat = main_coords[5][0]
    mid_lon = main_coords[5][1]
    main_places = [
        {"id": f"p-pharmacy-{city}", "lat": mid_lat, "lon": mid_lon, "category": "pharmacy", "opening_hours": "24/7", "is_help_point": True, "is_24x7": True},
        {"id": f"p-police-{city}", "lat": mid_lat + 0.001, "lon": mid_lon + 0.001, "category": "police", "opening_hours": "24/7", "is_help_point": True, "is_24x7": True},
        {"id": f"p-cafe-{city}", "lat": mid_lat - 0.001, "lon": mid_lon - 0.001, "category": "restaurant", "opening_hours": "Mo-Su 18:00-03:00", "is_help_point": False, "is_24x7": False}
    ]
    main_cameras = [
        {"id": f"c-1-{city}", "lat": mid_lat, "lon": mid_lon, "type": "cctv"},
        {"id": f"c-2-{city}", "lat": mid_lat + 0.002, "lon": mid_lon + 0.001, "type": "cctv"}
    ]
    main_lamps = [
        {"id": f"l-{city}-{i}", "lat": main_coords[i][0], "lon": main_coords[i][1]}
        for i in range(len(main_coords))
    ]
    main_roads = [
        {"id": f"r-main-{city}", "highway": "primary", "is_main": True, "is_lit": True, "lat": mid_lat, "lon": mid_lon}
    ]

    # Back lane has isolating landuse, no lamps, no cameras, no open venues
    back_mid_lat = back_coords[5][0]
    back_mid_lon = back_coords[5][1]
    back_landuse = [
        {"id": f"iso-{city}", "type": "industrial", "lat": back_mid_lat, "lon": back_mid_lon}
    ]
    back_roads = [
        {"id": f"r-back-{city}", "highway": "service", "is_main": False, "is_lit": False, "lat": back_mid_lat, "lon": back_mid_lon}
    ]

    score_main = score_route_v2(
        route=route_main, places=main_places, cameras=main_cameras, roads=main_roads,
        street_lamps=main_lamps, isolating_landuse=[], transport=[], departure_time=dep_time, mode="walking"
    )

    score_back = score_route_v2(
        route=route_back, places=[], cameras=[], roads=back_roads,
        street_lamps=[], isolating_landuse=back_landuse, transport=[], departure_time=dep_time, mode="walking"
    )

    # Main well-lit arterial route must strictly outscore the isolated/dark back lane
    assert score_main["night_score"] > score_back["night_score"] + 15.0, (
        f"Expected {city} main arterial to outscore dark back lane by >15 pts, got {score_main['night_score']} vs {score_back['night_score']}"
    )
    # Longest dark gap on back lane must be significantly longer
    assert score_back["metrics"]["longest_dark_gap_m"] > score_main["metrics"]["longest_dark_gap_m"]
