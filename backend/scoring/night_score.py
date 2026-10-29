import math
import numpy as np
from datetime import datetime, timedelta
from typing import Literal, List, Dict, Any, Tuple
from .weights import (
    WALKING_WEIGHTS, DRIVING_WEIGHTS, SATURATION_K,
    SCORING_PARAMS, COMPONENT_METADATA, DISCLAIMER_TEXT
)
from ..services.opening_hours import check_opening_hours

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def metric_projection(lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
    R = 6371000.0
    x = math.radians(lon) * R * math.cos(math.radians(ref_lat))
    y = math.radians(lat) * R
    return x, y

def inverse_metric_projection(x: float, y: float, ref_lat: float) -> Tuple[float, float]:
    R = 6371000.0
    lat = math.degrees(y / R)
    lon = math.degrees(x / (R * math.cos(math.radians(ref_lat))))
    return lat, lon

def resample_route(coords: List[List[float]], interval_m: float) -> List[Tuple[float, float, float]]:
    """
    Resamples a polyline [[lat, lon], ...] at regular metric distance intervals.
    Returns: [(lat, lon, cumulative_dist_m), ...]
    """
    if len(coords) < 2:
        return [(coords[0][0], coords[0][1], 0.0)] if coords else []

    ref_lat = coords[0][0]
    metric_pts = [metric_projection(p[0], p[1], ref_lat) for p in coords]

    cum_dists = [0.0]
    for i in range(1, len(metric_pts)):
        d = math.hypot(metric_pts[i][0] - metric_pts[i-1][0], metric_pts[i][1] - metric_pts[i-1][1])
        cum_dists.append(cum_dists[-1] + d)

    total_len = cum_dists[-1]
    if total_len <= 1.0:
        return [(coords[0][0], coords[0][1], 0.0)]

    resampled = []
    target_d = 0.0
    v_idx = 0

    while target_d <= total_len:
        while v_idx < len(cum_dists) - 1 and cum_dists[v_idx + 1] < target_d:
            v_idx += 1

        seg_start_d = cum_dists[v_idx]
        seg_end_d = cum_dists[v_idx + 1] if v_idx + 1 < len(cum_dists) else seg_start_d
        seg_len = seg_end_d - seg_start_d

        if seg_len > 0.001:
            ratio = (target_d - seg_start_d) / seg_len
            x = metric_pts[v_idx][0] + ratio * (metric_pts[v_idx+1][0] - metric_pts[v_idx][0])
            y = metric_pts[v_idx][1] + ratio * (metric_pts[v_idx+1][1] - metric_pts[v_idx][1])
        else:
            x, y = metric_pts[v_idx][0], metric_pts[v_idx][1]

        lat, lon = inverse_metric_projection(x, y, ref_lat)
        resampled.append((lat, lon, target_d))
        target_d += interval_m

    # Append exact destination endpoint
    resampled.append((coords[-1][0], coords[-1][1], total_len))
    return resampled

def deduplicate_clusters(features: List[Dict[str, Any]], cluster_radius_m: float = 40.0) -> float:
    """
    De-duplicates features within cluster_radius_m so that 20 shops clustered together
    count as 1.0 + 0.3 * (extra features) rather than 20 separate features.
    Returns effective weighted cluster count.
    """
    if not features:
        return 0.0

    visited = set()
    total_effective = 0.0

    for i, f1 in enumerate(features):
        if i in visited:
            continue
        visited.add(i)
        cluster_extras = 0.0
        w1 = f1.get("effective_weight", 1.0)

        for j in range(i + 1, len(features)):
            if j in visited:
                continue
            f2 = features[j]
            d = haversine_m(f1["lat"], f1["lon"], f2["lat"], f2["lon"])
            if d <= cluster_radius_m:
                visited.add(j)
                w2 = f2.get("effective_weight", 1.0)
                cluster_extras += 0.3 * w2

        total_effective += (w1 + cluster_extras)

    return total_effective

def compute_turns(coords: List[List[float]], min_angle_deg: float = 45.0) -> int:
    """Computes significant direction changes (> 45 deg) along polyline."""
    if len(coords) < 3:
        return 0

    turns = 0
    # Sample every ~30m to filter GPS jitter
    pts = coords[::max(1, len(coords)//25)]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i-1], pts[i], pts[i+1]
        b1 = math.atan2(p1[0] - p0[0], p1[1] - p0[1])
        b2 = math.atan2(p2[0] - p1[0], p2[1] - p1[1])
        diff = abs(math.degrees(b2 - b1))
        if diff > 180:
            diff = 360 - diff
        if diff >= min_angle_deg:
            turns += 1
    return turns

def score_route_v2(
    route: Dict[str, Any],
    places: List[Dict[str, Any]],
    cameras: List[Dict[str, Any]],
    roads: List[Dict[str, Any]],
    street_lamps: List[Dict[str, Any]] = None,
    isolating_landuse: List[Dict[str, Any]] = None,
    transport: List[Dict[str, Any]] = None,
    departure_time: datetime = None,
    mode: Literal["walking", "driving"] = "walking",
    force_lighting_unavailable: bool = False,
    weights_override: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Calculates the Night Activity Score (v2) across the 9 deterministic components.
    """
    if street_lamps is None:
        street_lamps = []
    if isolating_landuse is None:
        isolating_landuse = []
    if transport is None:
        transport = []
    if departure_time is None:
        departure_time = datetime.now()

    coords = route["coordinates"]
    dist_m = float(route.get("distance_m", 1000.0))
    dist_km = max(0.2, dist_m / 1000.0)
    duration_s = float(route.get("duration_s", 600.0))
    avg_speed = max(0.5, dist_m / max(1.0, duration_s))

    if weights_override:
        weights = dict(weights_override)
    else:
        weights = dict(WALKING_WEIGHTS if mode == "walking" else DRIVING_WEIGHTS)
    params = SCORING_PARAMS[mode]
    sample_interval_m = params["sample_interval_m"]
    coverage_radius_m = params["coverage_radius_m"]
    cluster_radius_m = params["cluster_radius_m"]

    # 1. Resample route every 25m (walking) or 50m (driving)
    samples = resample_route(coords, interval_m=sample_interval_m)
    num_samples = len(samples)

    # 2. Time-of-night factor dampener (01:00 - 04:00 gives 0.6x to general daytime shops)
    dep_hour = departure_time.hour
    is_deep_night = (1 <= dep_hour <= 4)
    time_factor = 0.6 if is_deep_night else 1.0

    # 3. Evaluate Open Places along route
    evaluated_places = []
    evaluated_help = []
    unique_open_places = []
    unique_help_points = []
    open_count = 0
    hours_mapped_count = 0

    for p in places:
        if not p.get("lat") or not p.get("lon"):
            continue
        # Find closest sample point to estimate arrival time
        min_d = float("inf")
        closest_sample = samples[0]
        for s in samples:
            d = haversine_m(s[0], s[1], p["lat"], p["lon"])
            if d < min_d:
                min_d = d
                closest_sample = s

        # Discard if outside corridor buffer (150m walking, 250m driving)
        corridor_limit = 150.0 if mode == "walking" else 250.0
        if min_d > corridor_limit:
            continue

        sample_dist = closest_sample[2]
        travel_time_s = sample_dist / avg_speed
        arrival_dt = departure_time + timedelta(seconds=travel_time_s)

        op_eval = check_opening_hours(p.get("opening_hours"), arrival_dt, p.get("category", "shop"))
        w = op_eval["weight"]
        if p.get("opening_hours"):
            hours_mapped_count += 1

        # Apply deep night dampener on non-essential / non-24x7 establishments
        if is_deep_night and not op_eval["is_24x7"] and not p.get("is_help_point"):
            w *= time_factor

        p_copy = dict(p)
        p_copy["effective_weight"] = w
        p_copy["is_open_at_arrival"] = op_eval["is_open"]
        p_copy["open_weight"] = w

        if w > 0.0:
            evaluated_places.append(p_copy)
            if op_eval["is_open"]:
                unique_open_places.append(p_copy)
                open_count += 1
            if p.get("is_help_point"):
                evaluated_help.append(p_copy)
                unique_help_points.append(p_copy)

    # Effective cluster-deduplicated counts
    eff_places = deduplicate_clusters(evaluated_places, cluster_radius_m)
    eff_help = deduplicate_clusters(evaluated_help, cluster_radius_m)

    # 4. Transport Stops
    evaluated_transport = []
    for t in transport:
        if not t.get("lat") or not t.get("lon"):
            continue
        min_d = min(haversine_m(s[0], s[1], t["lat"], t["lon"]) for s in samples)
        if min_d <= (120.0 if mode == "walking" else 200.0):
            t_copy = dict(t)
            t_copy["effective_weight"] = 1.0
            evaluated_transport.append(t_copy)

    eff_transport = deduplicate_clusters(evaluated_transport, cluster_radius_m)

    # 5. Surveillance Cameras
    evaluated_cams = []
    for c in cameras:
        if not c.get("lat") or not c.get("lon"):
            continue
        min_d = min(haversine_m(s[0], s[1], c["lat"], c["lon"]) for s in samples)
        if min_d <= (80.0 if mode == "walking" else 150.0):
            c_copy = dict(c)
            c_copy["effective_weight"] = 1.0
            evaluated_cams.append(c_copy)

    eff_cams = deduplicate_clusters(evaluated_cams, cluster_radius_m)

    # Camera spread across 200m route windows
    num_windows = max(1, int(math.ceil(dist_m / 200.0)))
    window_cams = [0] * num_windows
    for c in evaluated_cams:
        # find window
        closest_sample_dist = min(s[2] for s in samples if haversine_m(s[0], s[1], c["lat"], c["lon"]) <= 80.0) if samples else 0.0
        w_idx = min(num_windows - 1, int(closest_sample_dist // 200.0))
        window_cams[w_idx] += 1
    camera_spread = sum(1 for cnt in window_cams if cnt > 0) / float(num_windows)

    # 6. Sample Coverage & Gaps Analysis
    covered_mask = [False] * num_samples
    all_covering_features = evaluated_places + evaluated_help + evaluated_transport + evaluated_cams

    for i, s in enumerate(samples):
        for f in all_covering_features:
            if haversine_m(s[0], s[1], f["lat"], f["lon"]) <= coverage_radius_m:
                covered_mask[i] = True
                break

    # Calculate gaps
    gaps_m = []
    current_gap = 0.0
    for i in range(1, num_samples):
        d_step = samples[i][2] - samples[i-1][2]
        if not covered_mask[i]:
            current_gap += d_step
        else:
            if current_gap > 0:
                gaps_m.append(current_gap)
                current_gap = 0.0
    if current_gap > 0:
        gaps_m.append(current_gap)

    longest_dark_gap_m = max(gaps_m) if gaps_m else 0.0
    mean_gap_m = float(np.mean(gaps_m)) if gaps_m else 0.0
    p90_gap_m = float(np.percentile(gaps_m, 90)) if gaps_m else 0.0

    # Evenness using coefficient of variation over 200m windows
    window_covered = [0] * num_windows
    for i, s in enumerate(samples):
        if covered_mask[i]:
            w_idx = min(num_windows - 1, int(s[2] // 200.0))
            window_covered[w_idx] += 1
    mean_cov = float(np.mean(window_covered)) if window_covered else 0.0
    std_cov = float(np.std(window_covered)) if window_covered else 0.0
    cv = (std_cov / mean_cov) if mean_cov > 0.001 else 1.0
    evenness = max(0.0, min(1.0, 1.0 - (cv / 2.0)))

    # Gaps penalty
    full_gap_thresh = params["full_gap_penalty_m"]
    p90_gap_thresh = params["p90_gap_penalty_m"]
    longest_gap_ratio = min(1.0, longest_dark_gap_m / full_gap_thresh)
    p90_gap_ratio = min(1.0, p90_gap_m / p90_gap_thresh)
    gap_penalty = 0.5 * longest_gap_ratio + 0.3 * p90_gap_ratio + 0.2 * (1.0 - evenness)

    # 7. Main Road Classification
    main_classes = {"motorway", "trunk", "primary", "secondary", "tertiary"}
    main_road_samples = 0
    lit_road_samples = 0
    total_road_eval = 0

    for s in samples:
        # Match nearest road
        closest_r = None
        min_rd = float("inf")
        for r in roads:
            if r.get("lat") and r.get("lon"):
                rd = haversine_m(s[0], s[1], r["lat"], r["lon"])
                if rd < min_rd:
                    min_rd = rd
                    closest_r = r
        if closest_r and min_rd < 50.0:
            total_road_eval += 1
            if closest_r.get("highway") in main_classes:
                main_road_samples += 1
            if closest_r.get("is_lit") is True:
                lit_road_samples += 1

    main_road_ratio = (main_road_samples / max(1, total_road_eval)) if total_road_eval > 0 else 0.75
    lit_tag_coverage = (lit_road_samples / max(1, total_road_eval)) if total_road_eval > 0 else 0.0

    # 8. Street Lamps
    close_lamps = []
    for l in street_lamps:
        if l.get("lat") and l.get("lon"):
            if min(haversine_m(s[0], s[1], l["lat"], l["lon"]) for s in samples) <= 30.0:
                close_lamps.append(l)
    lamp_density_per_km = len(close_lamps) / dist_km

    # 9. Turns (simplicity)
    num_turns = compute_turns(coords, min_angle_deg=45.0)
    turns_per_km = num_turns / dist_km

    # 10. Surroundings (isolating land use)
    isolated_samples = 0
    for s in samples:
        for u in isolating_landuse:
            if u.get("lat") and u.get("lon"):
                if haversine_m(s[0], s[1], u["lat"], u["lon"]) <= 80.0:
                    isolated_samples += 1
                    break
    isolation_share = isolated_samples / max(1, num_samples)

    # -------------------------------------------------------------
    # CALCULATE COMPONENT POINTS (Saturating Curves)
    # -------------------------------------------------------------
    k = SATURATION_K
    
    # 1. Open Places (max 20 walk, 15 drive)
    dens_places = eff_places / dist_km
    norm_places = 1.0 - math.exp(-dens_places / k["open_places"])
    pts_places = weights.get("open_places", 0.0) * norm_places

    # 2. Help Points (max 15 walk, 10 drive)
    dens_help = eff_help / dist_km
    norm_help = 1.0 - math.exp(-dens_help / k["help_points"])
    pts_help = weights.get("help_points", 0.0) * norm_help

    # 3. Main Roads (max 10 walk, 20 drive)
    pts_main = weights.get("main_roads", 0.0) * main_road_ratio

    # 4. Transport (max 10 walk, 10 drive)
    dens_trans = eff_transport / dist_km
    norm_trans = 1.0 - math.exp(-dens_trans / k["transport"])
    pts_trans = weights.get("transport", 0.0) * norm_trans

    # 5. Gaps (max 15 walk, 10 drive)
    pts_gaps = weights.get("gaps", 0.0) * max(0.0, 1.0 - min(1.0, gap_penalty))

    # 6. Cameras (max 10 walk, 5 drive)
    dens_cams = eff_cams / dist_km
    norm_cams_dens = 1.0 - math.exp(-dens_cams / k["cameras"])
    norm_cams = 0.5 * norm_cams_dens + 0.5 * camera_spread
    pts_cams = weights.get("cameras", 0.0) * norm_cams

    # 7. Street Lighting (max 10 walk, 10 drive)
    norm_lamps = 1.0 - math.exp(-lamp_density_per_km / k["street_lamps"])
    norm_lighting = 0.6 * lit_tag_coverage + 0.4 * norm_lamps
    pts_lighting = weights.get("lighting", 0.0) * norm_lighting
    lighting_available = not force_lighting_unavailable and (lit_tag_coverage >= 0.15 or len(close_lamps) > 0)

    # 8. Turns (max 5 walk, 10 drive)
    pts_turns = weights.get("turns", 0.0) * math.exp(-turns_per_km / params["turns_divisor"])

    # 9. Surroundings (max 5 walk, 10 drive)
    pts_surroundings = weights.get("surroundings", 0.0) * max(0.0, 1.0 - isolation_share)
    if (isolation_share * dist_m) > params["isolation_penalty_threshold_m"]:
        pts_surroundings = max(0.0, pts_surroundings - (0.2 * weights.get("surroundings", 0.0)))

    # Construct Raw Breakdown
    raw_breakdown = {
        "open_places": {
            "component_id": 1,
            "name": COMPONENT_METADATA["open_places"]["display_name"],
            "note": f"{int(eff_places)} open venues along corridor ({dens_places:.1f}/km)",
            "raw_value": f"{int(eff_places)} places",
            "points": round(pts_places, 1),
            "max_points": weights.get("open_places", 0.0),
            "available": True
        },
        "help_points": {
            "component_id": 2,
            "name": COMPONENT_METADATA["help_points"]["display_name"],
            "note": f"{len(unique_help_points)} emergency services, police & 24/7 pharmacies",
            "raw_value": f"{len(unique_help_points)} points",
            "points": round(pts_help, 1),
            "max_points": weights.get("help_points", 0.0),
            "available": True
        },
        "main_roads": {
            "component_id": 3,
            "name": COMPONENT_METADATA["main_roads"]["display_name"],
            "note": f"Main roads identified along {int(main_road_ratio*100)}% of this route",
            "raw_value": f"{int(main_road_ratio*100)}%",
            "points": round(pts_main, 1),
            "max_points": weights.get("main_roads", 0.0),
            "available": True
        },
        "transport": {
            "component_id": 4,
            "name": COMPONENT_METADATA["transport"]["display_name"],
            "note": f"{len(evaluated_transport)} active transit & bus stops mapped",
            "raw_value": f"{len(evaluated_transport)} stops",
            "points": round(pts_trans, 1),
            "max_points": weights.get("transport", 0.0),
            "available": True
        },
        "gaps": {
            "component_id": 5,
            "name": COMPONENT_METADATA["gaps"]["display_name"],
            "note": f"Longest continuous dark gap: {int(longest_dark_gap_m)} m",
            "raw_value": f"{int(longest_dark_gap_m)} m gap",
            "points": round(pts_gaps, 1),
            "max_points": weights.get("gaps", 0.0),
            "available": True
        },
        "cameras": {
            "component_id": 6,
            "name": COMPONENT_METADATA["cameras"]["display_name"],
            "note": f"{len(evaluated_cams)} surveillance cameras ({int(camera_spread*100)}% route spread)",
            "raw_value": f"{len(evaluated_cams)} cams",
            "points": round(pts_cams, 1),
            "max_points": weights.get("cameras", 0.0),
            "available": True
        },
        "lighting": {
            "component_id": 7,
            "name": COMPONENT_METADATA["lighting"]["display_name"],
            "note": f"Street lamps & lit ways mapped ({int(lit_tag_coverage*100)}% lit ways)" if lighting_available else "Data unavailable across area (score rescaled fairly)",
            "raw_value": f"{int(lit_tag_coverage*100)}% lit" if lighting_available else "Data unavailable",
            "points": round(pts_lighting, 1) if lighting_available else 0.0,
            "max_points": weights.get("lighting", 0.0) if lighting_available else 0.0,
            "available": lighting_available
        },
        "turns": {
            "component_id": 8,
            "name": COMPONENT_METADATA["turns"]["display_name"],
            "note": f"Navigational complexity: {num_turns} significant turns ({turns_per_km:.1f}/km)",
            "raw_value": f"{num_turns} turns",
            "points": round(pts_turns, 1),
            "max_points": weights.get("turns", 0.0),
            "available": True
        },
        "surroundings": {
            "component_id": 9,
            "name": COMPONENT_METADATA["surroundings"]["display_name"],
            "note": f"{int((1.0 - isolation_share)*100)}% active urban corridor (minimal desolation)",
            "raw_value": f"{int((1.0 - isolation_share)*100)}% active",
            "points": round(pts_surroundings, 1),
            "max_points": weights.get("surroundings", 0.0),
            "available": True
        }
    }

    # 11. Fair Comparison Rescaling (Rule 9)
    available_max_pts = sum(comp["max_points"] for comp in raw_breakdown.values() if comp["available"])
    rescale_factor = (100.0 / available_max_pts) if available_max_pts > 0 else 1.0

    final_breakdown = {}
    sum_points = 0.0
    for k_comp, comp in raw_breakdown.items():
        if comp["available"]:
            rescaled_p = round(comp["points"] * rescale_factor, 1)
            rescaled_max = round(comp["max_points"] * rescale_factor, 1)
            sum_points += rescaled_p
            final_breakdown[k_comp] = {
                **comp,
                "points": rescaled_p,
                "max_points": rescaled_max
            }
        else:
            final_breakdown[k_comp] = {
                **comp,
                "points": 0.0,
                "max_points": 0.0,
                "note": "Data unavailable in area (rescaled fairly across other components)"
            }

    final_score = round(max(0.0, min(100.0, sum_points)), 1)

    # 12. Data Confidence Calculation
    pois_per_km = len(places) / dist_km
    hours_pct = (hours_mapped_count / max(1, len(places))) * 100.0

    if pois_per_km >= 8.0 and (hours_pct >= 20.0 or lit_tag_coverage >= 0.15):
        data_confidence = "High"
    elif pois_per_km >= 3.0:
        data_confidence = "Medium"
    else:
        data_confidence = "Low"

    return {
        "night_score": final_score,
        "mode": mode,
        "data_confidence": data_confidence,
        "confidence_warning": "OpenStreetMap data is sparse here, so treat this score as rough." if data_confidence == "Low" else None,
        "metrics": {
            "open_places_count": len(unique_open_places),
            "help_points_count": len(unique_help_points),
            "transport_points_count": len(evaluated_transport),
            "cameras_count": len(evaluated_cams),
            "street_lamps_count": len(close_lamps),
            "camera_spread": round(camera_spread, 2),
            "main_road_ratio": round(main_road_ratio, 2),
            "lit_ratio": round(lit_tag_coverage, 2),
            "longest_dark_gap_m": round(longest_dark_gap_m, 1),
            "mean_gap_m": round(mean_gap_m, 1),
            "p90_gap_m": round(p90_gap_m, 1),
            "turns_count": num_turns,
            "turns_per_km": round(turns_per_km, 1),
            "isolation_share": round(isolation_share, 2),
            "evenness": round(evenness, 2),
            "pois_per_km": round(pois_per_km, 1),
            "hours_pct": round(hours_pct, 1)
        },
        "breakdown": final_breakdown,
        "disclaimer": DISCLAIMER_TEXT
    }

# Backward compatibility alias
score_route = score_route_v2
