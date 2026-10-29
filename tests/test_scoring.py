import pytest
from datetime import datetime
from backend.scoring.night_score import score_route_v2
from backend.scoring.weights import WALKING_WEIGHTS, DRIVING_WEIGHTS

def make_synthetic_route(length_m=1000.0, duration_s=900.0, mode="walking"):
    # Straight line route along latitude from 12.9700 to ~12.9790
    steps = 25
    coords = []
    lat_start = 12.9700
    lon = 77.6000
    for i in range(steps + 1):
        t = i / steps
        coords.append([lat_start + t * 0.009, lon])

    return {
        "id": "synthetic-test-route",
        "name": "Synthetic Route",
        "coordinates": coords,
        "distance_m": length_m,
        "duration_s": duration_s,
        "mode": mode
    }

def test_walking_and_driving_tables_sum_to_100():
    assert sum(WALKING_WEIGHTS.values()) == pytest.approx(100.0, 0.01)
    assert sum(DRIVING_WEIGHTS.values()) == pytest.approx(100.0, 0.01)

def test_closed_shops_do_not_count():
    route = make_synthetic_route()
    departure_time = datetime(2026, 10, 28, 2, 0) # 2:00 AM

    place_open = {
        "id": "p-open",
        "name": "24/7 Pharmacy",
        "category": "pharmacy",
        "lat": 12.9720,
        "lon": 77.6000,
        "opening_hours": "24/7",
        "is_help_point": True,
        "is_24x7": True
    }

    place_closed = {
        "id": "p-closed",
        "name": "Daytime Boutique",
        "category": "shop",
        "lat": 12.9740,
        "lon": 77.6000,
        "opening_hours": "10:00-19:00",
        "is_help_point": False,
        "is_24x7": False
    }

    res_with_closed = score_route_v2(
        route=route,
        places=[place_open, place_closed],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    res_without_closed = score_route_v2(
        route=route,
        places=[place_open],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    assert res_with_closed["metrics"]["open_places_count"] == 1
    assert res_with_closed["night_score"] == res_without_closed["night_score"]

def test_unknown_hours_add_less_than_open():
    route = make_synthetic_route()
    departure_time = datetime(2026, 10, 28, 22, 0) # 10:00 PM

    place_verified = {
        "id": "p-1",
        "name": "Verified Supermarket",
        "category": "shop",
        "lat": 12.9730,
        "lon": 77.6000,
        "opening_hours": "Mo-Su 08:00-23:30",
        "is_help_point": False,
        "is_24x7": False
    }

    place_unknown = {
        "id": "p-2",
        "name": "Unmapped Supermarket",
        "category": "shop",
        "lat": 12.9730,
        "lon": 77.6000,
        "opening_hours": "Not mapped",
        "is_help_point": False,
        "is_24x7": False
    }

    res_verified = score_route_v2(
        route=route,
        places=[place_verified],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    res_unknown = score_route_v2(
        route=route,
        places=[place_unknown],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    pts_verified = res_verified["breakdown"]["open_places"]["points"]
    pts_unknown = res_unknown["breakdown"]["open_places"]["points"]
    assert pts_verified > pts_unknown
    assert pts_unknown <= 0.3 * pts_verified

def test_time_of_night_factor():
    route = make_synthetic_route()
    time_evening = datetime(2026, 10, 28, 22, 0) # 10:00 PM
    time_late_night = datetime(2026, 10, 29, 2, 30) # 2:30 AM (deep night)

    # Place with late evening hours
    place = {
        "id": "p-cafe",
        "name": "Midnight Diner",
        "category": "restaurant",
        "lat": 12.9740,
        "lon": 77.6000,
        "opening_hours": "Mo-Su 18:00-03:00",
        "is_help_point": False,
        "is_24x7": False
    }

    res_evening = score_route_v2(
        route=route,
        places=[place],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=time_evening,
        mode="walking"
    )

    res_late_night = score_route_v2(
        route=route,
        places=[place],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=time_late_night,
        mode="walking"
    )

    # 2:30 AM route scores lower due to deep night dampener
    assert res_evening["night_score"] >= res_late_night["night_score"]
    assert res_evening["breakdown"]["open_places"]["points"] > res_late_night["breakdown"]["open_places"]["points"]

def test_cameras_raise_the_score():
    route = make_synthetic_route()
    departure_time = datetime(2026, 10, 28, 2, 0)

    res_no_cameras = score_route_v2(
        route=route,
        places=[],
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    cameras = [
        {"id": f"cam-{i}", "lat": 12.9700 + i * 0.002, "lon": 77.6000, "type": "CCTV", "operator": "Police"}
        for i in range(4)
    ]

    res_with_cameras = score_route_v2(
        route=route,
        places=[],
        cameras=cameras,
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    assert res_with_cameras["metrics"]["cameras_count"] > 0
    assert res_with_cameras["night_score"] > res_no_cameras["night_score"]

def test_clustered_vs_evenly_spread_scoring():
    route = make_synthetic_route(length_m=1000.0)
    departure_time = datetime(2026, 10, 28, 2, 0)

    # 4 places all clustered within the first 60 meters
    clustered_places = [
        {"id": f"cp-{i}", "name": f"Shop {i}", "category": "shop", "lat": 12.9701 + i * 0.0001, "lon": 77.6000, "opening_hours": "24/7", "is_help_point": False, "is_24x7": True}
        for i in range(4)
    ]

    # 4 places evenly spread every 250 meters along the route
    spread_places = [
        {"id": f"sp-{i}", "name": f"Shop {i}", "category": "shop", "lat": 12.9700 + i * 0.0022, "lon": 77.6000, "opening_hours": "24/7", "is_help_point": False, "is_24x7": True}
        for i in range(4)
    ]

    res_clustered = score_route_v2(
        route=route,
        places=clustered_places,
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    res_spread = score_route_v2(
        route=route,
        places=spread_places,
        cameras=[],
        roads=[],
        street_lamps=[],
        isolating_landuse=[],
        transport=[],
        departure_time=departure_time,
        mode="walking"
    )

    # Evenly spread route has shorter dark gap and higher score
    assert res_spread["metrics"]["longest_dark_gap_m"] < res_clustered["metrics"]["longest_dark_gap_m"]
    assert res_spread["night_score"] > res_clustered["night_score"]

def test_saturation_works():
    route = make_synthetic_route(length_m=1000.0)
    departure_time = datetime(2026, 10, 28, 2, 0)

    # 15 shops in a tight cluster (within 30m)
    places_15 = [
        {"id": f"p-{i}", "name": f"Shop {i}", "category": "shop", "lat": 12.9710 + i * 0.000008, "lon": 77.6000, "opening_hours": "24/7", "is_help_point": False, "is_24x7": True}
        for i in range(15)
    ]

    # 30 shops in the same tight cluster (within 30m)
    places_30 = [
        {"id": f"p-{i}", "name": f"Shop {i}", "category": "shop", "lat": 12.9710 + i * 0.000008, "lon": 77.6000, "opening_hours": "24/7", "is_help_point": False, "is_24x7": True}
        for i in range(30)
    ]

    res_15 = score_route_v2(route, places_15, [], [], [], [], [], departure_time, "walking")
    res_30 = score_route_v2(route, places_30, [], [], [], [], [], departure_time, "walking")

    # The additional 15 shops in the same cluster should add minimal marginal points due to cluster dampening & saturation
    delta = res_30["breakdown"]["open_places"]["points"] - res_15["breakdown"]["open_places"]["points"]
    assert delta <= 5.0

def test_fair_comparison_missing_data_rescaling():
    route = make_synthetic_route()
    departure_time = datetime(2026, 10, 28, 2, 0)

    places = [
        {"id": "p-1", "name": "Pharmacy", "category": "pharmacy", "lat": 12.9730, "lon": 77.6000, "opening_hours": "24/7", "is_help_point": True, "is_24x7": True}
    ]

    # Standard run with lighting available
    res_with_light = score_route_v2(
        route=route, places=places, cameras=[], roads=[], street_lamps=[{"lat": 12.972, "lon": 77.600}],
        isolating_landuse=[], transport=[], departure_time=departure_time, mode="walking", force_lighting_unavailable=False
    )

    # Run with lighting forced unavailable
    res_unavailable = score_route_v2(
        route=route, places=places, cameras=[], roads=[], street_lamps=[],
        isolating_landuse=[], transport=[], departure_time=departure_time, mode="walking", force_lighting_unavailable=True
    )

    # Lighting row must be marked unavailable
    assert res_unavailable["breakdown"]["lighting"]["available"] is False
    assert res_unavailable["breakdown"]["lighting"]["max_points"] == 0.0
    # Other components must be rescaled to fill the 100 pt total
    available_max_pts = sum(c["max_points"] for c in res_unavailable["breakdown"].values())
    assert available_max_pts == pytest.approx(100.0, 0.5)
