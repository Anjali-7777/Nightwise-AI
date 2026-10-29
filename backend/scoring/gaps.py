"""
Dark gap detection and non-linear penalty calculation.
Identifies contiguous uncovered segments along the resampled route corridor.
"""

def analyze_dark_gaps(covered_mask: list[bool], sample_interval_m: float = 50.0, mode: str = "walking") -> dict:
    """
    Analyzes sequences of consecutive False values in covered_mask.
    Returns:
      {
        "longest_dark_gap_m": float,
        "gap_penalty": float,
        "dark_gaps": [{"start_m": float, "end_m": float, "length_m": float}, ...]
      }
    """
    if not covered_mask:
        return {
            "longest_dark_gap_m": 0.0,
            "gap_penalty": 0.0,
            "dark_gaps": []
        }

    gaps = []
    current_gap_len = 0
    start_idx = None

    for i, is_cov in enumerate(covered_mask):
        if not is_cov:
            if current_gap_len == 0:
                start_idx = i
            current_gap_len += 1
        else:
            if current_gap_len > 0:
                length_m = current_gap_len * sample_interval_m
                gaps.append({
                    "start_m": start_idx * sample_interval_m,
                    "end_m": (start_idx + current_gap_len) * sample_interval_m,
                    "length_m": length_m
                })
                current_gap_len = 0

    if current_gap_len > 0:
        gaps.append({
            "start_m": start_idx * sample_interval_m,
            "end_m": (start_idx + current_gap_len) * sample_interval_m,
            "length_m": current_gap_len * sample_interval_m
        })

    longest_gap_m = max([g["length_m"] for g in gaps], default=0.0)
    total_route_len_m = len(covered_mask) * sample_interval_m

    # Compute non-linear penalty based on mode and gap severity
    if mode == "walking":
        # Tolerable threshold: 100m.
        if longest_gap_m <= 100.0:
            penalty = 0.0
        else:
            # Scale penalty by gap length and relative fraction of route
            gap_fraction = min(1.0, longest_gap_m / max(500.0, total_route_len_m))
            penalty = round(min(15.0, 15.0 * (gap_fraction ** 1.2)), 1)
    else: # driving
        if longest_gap_m <= 250.0:
            penalty = 0.0
        else:
            gap_fraction = min(1.0, longest_gap_m / max(1000.0, total_route_len_m))
            penalty = round(min(10.0, 10.0 * (gap_fraction ** 1.2)), 1)

    return {
        "longest_dark_gap_m": longest_gap_m,
        "gap_penalty": penalty,
        "dark_gaps": gaps
    }
