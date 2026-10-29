import re
from datetime import datetime, time, timedelta

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}

LATE_NIGHT_CATEGORIES = {
    "fuel", "petrol_pump", "pharmacy", "chemist", "hospital", "clinic",
    "doctors", "police", "emergency_phone", "bus_stop", "bus_station",
    "transport", "station"
}

def parse_time(t_str: str) -> time:
    parts = t_str.strip().split(":")
    return time(int(parts[0]), int(parts[1]))

def is_time_in_range(check_t: time, start_t: time, end_t: time) -> bool:
    if start_t <= end_t:
        return start_t <= check_t <= end_t
    else:
        # Spans midnight, e.g. 18:00 - 02:00
        return check_t >= start_t or check_t <= end_t

def check_opening_hours(raw_hours: str | None, check_dt: datetime, category: str | None = None) -> dict:
    """
    Evaluates whether an establishment is open at check_dt based on OSM opening_hours syntax.
    Returns:
      {
        "status": "open" | "closed" | "unknown",
        "is_open": bool,
        "is_24x7": bool,
        "weight": float (1.0 for verified/24/7, 0.3 for late categories/unknown, 0.1 for general daytime, 0.0 for closed)
      }
    """
    if category is None:
        unknown_weight = 0.3
    else:
        cat_lower = (category or "").lower()
        is_late_cat = any(c in cat_lower for c in LATE_NIGHT_CATEGORIES)
        unknown_weight = 0.3 if is_late_cat else 0.1

    if not raw_hours or not isinstance(raw_hours, str) or not raw_hours.strip() or raw_hours.lower() in ["not mapped", "none", "null", "unknown"]:
        return {
            "status": "unknown",
            "is_open": False,
            "is_24x7": False,
            "weight": unknown_weight
        }

    s = raw_hours.strip().lower()
    if any(k in s for k in ["24/7", "24 / 7", "24 hours", "24 hrs", "all day", "open 24 hours"]):
        return {
            "status": "open",
            "is_open": True,
            "is_24x7": True,
            "weight": 1.0
        }

    if s in ["off", "closed", "never"] or "ph off" in s:
        return {
            "status": "closed",
            "is_open": False,
            "is_24x7": False,
            "weight": 0.0
        }

    # "sunset-sunrise" pattern
    if "sunset-sunrise" in s or "sunrise-sunset" in s:
        cur_h = check_dt.hour
        # Sunset to sunrise typically ~18:00 to 06:00
        is_night = (cur_h >= 18 or cur_h < 6)
        if "sunset-sunrise" in s:
            return {
                "status": "open" if is_night else "closed",
                "is_open": is_night,
                "is_24x7": False,
                "weight": 1.0 if is_night else 0.0
            }
        else:
            return {
                "status": "closed" if is_night else "open",
                "is_open": not is_night,
                "is_24x7": False,
                "weight": 0.0 if is_night else 1.0
            }

    cur_day_idx = check_dt.weekday() # 0 = Monday, 6 = Sunday
    cur_time = check_dt.time()
    yesterday_idx = (cur_day_idx - 1) % 7

    # Split semicolon-delimited rules
    rules = [r.strip() for r in raw_hours.split(";") if r.strip()]
    parsed_any_rule = False

    for rule in rules:
        day_match = re.search(r'([A-Za-z,\s-]+)?\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}(?:,\s*\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})*)', rule)
        if not day_match:
            continue

        parsed_any_rule = True
        days_part = day_match.group(1).strip() if day_match.group(1) else ""
        times_part = day_match.group(2).strip()

        applicable_days = set()
        if not days_part:
            applicable_days = set(range(7))
        else:
            tokens = [t.strip() for t in days_part.replace(",", " ").split() if t.strip()]
            for tok in tokens:
                if "-" in tok:
                    range_parts = tok.split("-")
                    if len(range_parts) == 2 and range_parts[0] in DAY_INDEX and range_parts[1] in DAY_INDEX:
                        s_idx = DAY_INDEX[range_parts[0]]
                        e_idx = DAY_INDEX[range_parts[1]]
                        if s_idx <= e_idx:
                            applicable_days.update(range(s_idx, e_idx + 1))
                        else:
                            applicable_days.update(range(s_idx, 7))
                            applicable_days.update(range(0, e_idx + 1))
                elif tok in DAY_INDEX:
                    applicable_days.add(DAY_INDEX[tok])

        for time_range in times_part.split(","):
            tr = time_range.strip()
            if "-" not in tr:
                continue
            parts = tr.split("-")
            try:
                start_t = parse_time(parts[0])
                end_t = parse_time(parts[1])
            except Exception:
                continue

            # Standard daytime range
            if start_t <= end_t:
                if cur_day_idx in applicable_days and start_t <= cur_time <= end_t:
                    return {"status": "open", "is_open": True, "is_24x7": False, "weight": 1.0}
            else:
                # Overnight range (e.g. 18:00 - 02:00)
                if cur_day_idx in applicable_days and cur_time >= start_t:
                    return {"status": "open", "is_open": True, "is_24x7": False, "weight": 1.0}
                if yesterday_idx in applicable_days and cur_time <= end_t:
                    return {"status": "open", "is_open": True, "is_24x7": False, "weight": 1.0}

    if parsed_any_rule:
        return {"status": "closed", "is_open": False, "is_24x7": False, "weight": 0.0}

    return {"status": "unknown", "is_open": False, "is_24x7": False, "weight": unknown_weight}
