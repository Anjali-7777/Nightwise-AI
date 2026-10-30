import re
import asyncio
from datetime import datetime
from typing import Literal
from ..services.geocode import geocode
from ..services.routing import get_routes
from ..services.places import fetch_places_in_corridor
from ..services.cameras import fetch_cameras_in_corridor
from ..services.roads import fetch_road_attributes_in_corridor, fetch_corridor_lighting_and_landuse
from ..scoring.night_score import score_route_v2
from ..scoring.weights import COMPONENT_METADATA

def parse_time_string(time_str: str) -> datetime:
    """Parses various user departure time strings into today's datetime."""
    now = datetime.now()
    if not time_str or time_str.lower() in ["now", "abhi", "immediately", "right now"]:
        return now

    s = time_str.lower().strip()
    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s)
    if match:
        h = int(match.group(1))
        m = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        elif "night" in s and h == 12:
            h = 0
        elif "night" in s and 1 <= h <= 11:
            h += 12
        try:
            return now.replace(hour=h, minute=m, second=0, microsecond=0)
        except ValueError:
            pass

    return now

async def execute_route_workflow(
    origin_query: str,
    destination_query: str,
    mode: Literal["walking", "driving"] = "walking",
    departure_time_str: str = "now",
    saved_places: dict | None = None
) -> dict:
    """
    Full automated pipeline (v2):
    1. Geocode origin and destination
    2. Retrieve 2-3 candidate alternative routes from OSRM / OpenStreetMap
    3. Collect corridor features (places, transport, cameras, street lamps, roads, land use)
    4. Deterministically calculate Night Activity Score v2 for each route
    5. Identify Fastest and Safest routes with tie-break and single biggest difference component
    """
    saved_places = saved_places or {}
    orig_q = saved_places.get(origin_query.lower(), origin_query)
    dest_q = saved_places.get(destination_query.lower(), destination_query)

    dep_dt = parse_time_string(departure_time_str)

    # 1. Geocode
    orig_res = await geocode(orig_q)
    dest_res = await geocode(dest_q)

    if not orig_res:
        raise ValueError(f"Could not find coordinates for origin: '{orig_q}'")
    if not dest_res:
        raise ValueError(f"Could not find coordinates for destination: '{dest_q}'")

    orig_pt = (orig_res[0]["lat"], orig_res[0]["lon"])
    dest_pt = (dest_res[0]["lat"], dest_res[0]["lon"])

    # 2. Get Routes (OSRM primary, 2-3 genuinely different corridors)
    raw_routes = await get_routes(orig_pt, dest_pt, mode=mode)
    if not raw_routes:
        raise ValueError("No accessible routes found between these locations.")

    # Collect corridor coordinates across all candidate routes
    combined_coords = []
    for r in raw_routes:
        combined_coords.extend(r["coordinates"])

    # 3. Gather corridor data concurrently across places, cameras, roads, lighting, and land use
    places, cameras, roads, lighting_landuse = await asyncio.gather(
        fetch_places_in_corridor(combined_coords),
        fetch_cameras_in_corridor(combined_coords),
        fetch_road_attributes_in_corridor(combined_coords),
        fetch_corridor_lighting_and_landuse(combined_coords)
    )

    street_lamps = lighting_landuse.get("street_lamps", [])
    isolating_landuse = lighting_landuse.get("isolating_landuse", [])
    transport = lighting_landuse.get("transport", [])

    # Check if lighting data is completely unavailable across area (Fair Comparison Rule 9)
    lit_samples_count = sum(1 for r in roads if r.get("is_lit") is True)
    force_lighting_unavailable = (lit_samples_count == 0 and len(street_lamps) == 0)

    # 4. Score each route
    scored_routes = []
    for r in raw_routes:
        score_res = score_route_v2(
            route=r,
            places=places,
            cameras=cameras,
            roads=roads,
            street_lamps=street_lamps,
            isolating_landuse=isolating_landuse,
            transport=transport,
            departure_time=dep_dt,
            mode=mode,
            force_lighting_unavailable=force_lighting_unavailable
        )
        scored_routes.append({
            **r,
            **score_res
        })

    # 5. Label Fastest and Safest (Tie-break Safest by smaller longest dark gap)
    scored_routes.sort(key=lambda x: x["duration_s"])
    fastest_route = scored_routes[0]

    safest_route = max(
        scored_routes,
        key=lambda x: (x["night_score"], -x["metrics"]["longest_dark_gap_m"])
    )

    for r in scored_routes:
        labels = []
        if r["id"] == fastest_route["id"]:
            labels.append("Fastest")
        if r["id"] == safest_route["id"]:
            labels.append("Safest")
        r["labels"] = labels

    # Compute trade-off between Fastest and Safest
    time_diff_min = round((safest_route["duration_s"] - fastest_route["duration_s"]) / 60.0, 1)
    score_diff = round(safest_route["night_score"] - fastest_route["night_score"], 1)

    # Identify the single component that changed the most
    biggest_diff_comp_name = "Overall environmental support"
    biggest_diff_pts = 0.0
    s_b = safest_route.get("breakdown", {})
    f_b = fastest_route.get("breakdown", {})

    diffs = []
    for comp_key, comp_data in s_b.items():
        if comp_key in f_b and comp_data.get("available", True):
            diff = abs(comp_data["points"] - f_b[comp_key]["points"])
            diffs.append((diff, comp_data["name"]))

    if diffs:
        diffs.sort(key=lambda x: x[0], reverse=True)
        biggest_diff_pts = round(diffs[0][0], 1)
        biggest_diff_comp_name = diffs[0][1]

    data_confidence = safest_route.get("data_confidence", "High")
    confidence_warning = safest_route.get("confidence_warning")

    return {
        "origin": {
            "name": orig_res[0]["name"],
            "lat": orig_pt[0],
            "lon": orig_pt[1]
        },
        "destination": {
            "name": dest_res[0]["name"],
            "lat": dest_pt[0],
            "lon": dest_pt[1]
        },
        "departure_time": dep_dt.strftime("%Y-%m-%d %H:%M"),
        "mode": mode,
        "data_confidence": data_confidence,
        "confidence_warning": confidence_warning,
        "routes": scored_routes,
        "safest_route_id": safest_route["id"],
        "fastest_route_id": fastest_route["id"],
        "trade_off": {
            "time_diff_min": time_diff_min,
            "score_diff": score_diff,
            "biggest_diff_component": biggest_diff_comp_name,
            "biggest_diff_points": biggest_diff_pts,
            "safest_open_places": safest_route["metrics"]["open_places_count"],
            "fastest_open_places": fastest_route["metrics"]["open_places_count"],
            "safest_cameras": safest_route["metrics"]["cameras_count"],
            "fastest_cameras": fastest_route["metrics"]["cameras_count"],
            "safest_dark_gap": safest_route["metrics"]["longest_dark_gap_m"],
            "fastest_dark_gap": fastest_route["metrics"]["longest_dark_gap_m"]
        },
        "corridor_places": list(places) + list(transport),
        "corridor_cameras": cameras
    }
