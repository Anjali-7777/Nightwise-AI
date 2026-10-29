"""
NightWise AI - Component Weights and Calibration Parameters (v2)

Separate walking and driving tables summing to exactly 100 max points.
Configurable saturation factors (k) and threshold distances.
"""

# Maximum points per component (must sum to exactly 100)
WALKING_WEIGHTS = {
    "open_places": 20.0,           # 1. Open places along route (open at time passed)
    "help_points": 15.0,           # 2. Open help points (police, hospital, pharmacy, fuel)
    "main_roads": 10.0,            # 3. Distance on main roads
    "transport": 10.0,             # 4. Open transport locations
    "gaps": 15.0,                  # 5. Fewer and shorter dark gaps between covered places
    "cameras": 10.0,               # 6. Surveillance cameras (count + spread)
    "lighting": 10.0,              # 7. Street lighting (lit ways + street lamp density)
    "turns": 5.0,                  # 8. Fewer turns / simple route
    "surroundings": 5.0,           # 9. Active surroundings (avoid isolated/industrial/dark areas)
}

DRIVING_WEIGHTS = {
    "open_places": 15.0,           # 1. Open places along route
    "help_points": 10.0,           # 2. Open help points
    "main_roads": 20.0,            # 3. Distance on main roads (arterials prioritize safety in cars)
    "transport": 10.0,             # 4. Open transport hubs
    "gaps": 10.0,                  # 5. Dark gaps
    "cameras": 5.0,                # 6. Cameras
    "lighting": 10.0,              # 7. Street lighting
    "turns": 10.0,                 # 8. Route simplicity / navigation ease
    "surroundings": 10.0,          # 9. Surroundings (well-trafficked corridor vs desolate service lanes)
}

# Saturation curvature parameters (k) for density per km: 1 - exp(-density / k)
# Larger k means more places are needed to reach maximum points
SATURATION_K = {
    "open_places": 8.0,            # ~16 places/km gets ~86% of max points
    "help_points": 2.5,            # ~5 help points/km gets ~86% of max points
    "transport": 3.0,              # ~6 transit stops/km gets ~86% of max points
    "cameras": 4.0,                # ~8 cameras/km gets ~86% of max points
    "street_lamps": 15.0,          # ~30 lamps/km gets ~86% of max points
}

# Thresholds for Gaps and Radii
SCORING_PARAMS = {
    "walking": {
        "sample_interval_m": 25.0,
        "coverage_radius_m": 75.0,
        "cluster_radius_m": 40.0,
        "full_gap_penalty_m": 300.0,
        "p90_gap_penalty_m": 200.0,
        "turns_divisor": 6.0,
        "isolation_penalty_threshold_m": 300.0,
    },
    "driving": {
        "sample_interval_m": 50.0,
        "coverage_radius_m": 150.0,
        "cluster_radius_m": 60.0,
        "full_gap_penalty_m": 800.0,
        "p90_gap_penalty_m": 500.0,
        "turns_divisor": 4.0,
        "isolation_penalty_threshold_m": 500.0,
    }
}

COMPONENT_METADATA = {
    "open_places": {
        "number": 1,
        "display_name": "Open places along route",
        "description": "Establishments verified open at the exact time you pass"
    },
    "help_points": {
        "number": 2,
        "display_name": "Open help points",
        "description": "Emergency services, police, 24/7 pharmacies & hospitals"
    },
    "main_roads": {
        "number": 3,
        "display_name": "Distance on main roads",
        "description": "Well-trafficked arterial roads rather than isolated back alleys"
    },
    "transport": {
        "number": 4,
        "display_name": "Open transport locations",
        "description": "Active bus stops, metro entrances, and public transit hubs"
    },
    "gaps": {
        "number": 5,
        "display_name": "Fewer & shorter dark gaps",
        "description": "Continuous activity without long unmonitored blindspots"
    },
    "cameras": {
        "number": 6,
        "display_name": "Surveillance cameras",
        "description": "CCTV density and even spread across the corridor"
    },
    "lighting": {
        "number": 7,
        "display_name": "Street lighting",
        "description": "Lit road ways and physical street lamp density"
    },
    "turns": {
        "number": 8,
        "display_name": "Fewer turns / simple route",
        "description": "Direct, navigable path minimizing disorientation"
    },
    "surroundings": {
        "number": 9,
        "display_name": "Active surroundings",
        "description": "Absence of isolating industrial zones, dense woods, or vacant wasteland"
    }
}

DISCLAIMER_TEXT = (
    "NightWise AI provides deterministic environmental safety indicators based on OpenStreetMap "
    "and verified municipal data. The score reflects mapped social presence, lighting, and surveillance, "
    "not a guarantee of safety. The choice remains entirely yours."
)
