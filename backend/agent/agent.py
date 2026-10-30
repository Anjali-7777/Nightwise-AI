import re
import json
import httpx
from typing import Optional
from .schemas import ParsedUserQuery, AgentChatResponse
from .prompts import AGENT_SYSTEM_PROMPT, EXPLANATION_SYSTEM_PROMPT
from .tools import execute_route_workflow
from ..config import OLLAMA_HOST, LLM_MODEL
from ..scoring.weights import DISCLAIMER_TEXT

def regex_fallback_parser(text: str) -> dict:
    """Deterministic regex and keyword parser if LLM extraction fails or is offline."""
    t = text.lower()
    
    # 1. Mode detection
    mode = "walking"
    if any(k in t for k in ["drive", "driving", "car", "cab", "auto", "taxi", "bike", "scooter"]):
        mode = "driving"

    # 2. Time detection
    dep_time = "now"
    night_time_match = re.search(r'(\d{1,2}(?::\d{2})?)\s*(?:at night|in the night|night|pm|p\.m\.|am|a\.m\.|baje|hrs|hours?)', t)
    if "midnight" in t or "aadhi raat" in t:
        dep_time = "00:00"
    elif night_time_match:
        num_part = night_time_match.group(1)
        if "at night" in t or "in the night" in t or "pm" in t or "p.m." in t:
            try:
                h = int(num_part.split(":")[0])
                m = num_part.split(":")[1] if ":" in num_part else "00"
                if h == 12:
                    dep_time = f"00:{m}" if "night" in t else f"12:{m}"
                elif h < 12 and ("night" in t or "pm" in t):
                    dep_time = f"{h+12:02d}:{m}"
                else:
                    dep_time = f"{h:02d}:{m}"
            except Exception:
                dep_time = night_time_match.group(0).strip()
        else:
            dep_time = night_time_match.group(0).strip()
    elif "night" in t or "raat" in t:
        dep_time = "23:00"
    else:
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|baje|hrs|hours?))', t)
        if time_match:
            dep_time = time_match.group(1).replace("baje", "").strip()

    # Pre-clean conversational intents and filler prefixes before extracting endpoints
    cleaned_t = t
    cleaned_t = re.sub(r'\b(?:it\'?s|it is)\s+\d{1,2}(?::\d{2})?\s*(?:at night|in the night|am|pm)?\b', '', cleaned_t)
    cleaned_t = re.sub(r'\b(?:i\s+)?(?:want|need|have|plan|wish|would like)\s+to\s+(?:go|travel|head|commute|reach|get|walk|drive)\s+from\b', 'from', cleaned_t)
    cleaned_t = re.sub(r'\b(?:i\s+)?(?:want|need|have|plan|wish|would like)\s+to\s+(?:go|travel|head|commute|reach|get|walk|drive)\s+to\b', 'to', cleaned_t)
    cleaned_t = re.sub(r'\b(?:show|give|find|navigate|take)\s+(?:me\s+)?(?:the\s+)?(?:route|safest route|way|directions)?\s+from\b', 'from', cleaned_t)
    cleaned_t = re.sub(r'\b(?:i want to|want to|need to|how to|can i|help me)\s+(?:go|travel|reach|walk|drive)\b', '', cleaned_t)

    # 3. Origin & Destination detection
    origin = ""
    destination = ""

    # Pattern A: "from X to Y"
    from_to = re.search(r'(?:from|starting at|leaving)\s+([^,]+?)\s+(?:to|heading to|towards)\s+([^,]+?)(?:\s+at|\s+by|\s+in|\s+walking|\s+driving|$)', cleaned_t)
    if from_to:
        origin = from_to.group(1).strip()
        destination = from_to.group(2).strip()

    # Pattern B: Hinglish "X se Y" (e.g., "office se ghar")
    if not origin or not destination:
        hinglish = re.search(r'([^,]+?)\s+se\s+([^,]+?)(?:\s+jaana|\s+raat|\s+at|\s+by|\s+walking|\s+driving|$)', cleaned_t)
        if hinglish:
            origin = hinglish.group(1).strip()
            destination = hinglish.group(2).strip()

    # Pattern C: "to Y from X"
    if not origin or not destination:
        to_from = re.search(r'(?:to|towards)\s+([^,]+?)\s+from\s+([^,]+?)(?:\s+around|\s+at|\s+by|\s+walking|\s+driving|$)', cleaned_t)
        if to_from:
            cand_dest = to_from.group(1).strip()
            cand_orig = to_from.group(2).strip()
            if cand_dest.lower() not in {"go", "reach", "travel", "head", "commute", "walk", "drive", "get"}:
                destination = cand_dest
                origin = cand_orig

    # Pattern D: "from X" alone
    if not origin:
        from_alone = re.search(r'from\s+([^,]+?)(?:\s+at|\s+around|\s+by|\s+walking|\s+driving|$)', cleaned_t)
        if from_alone:
            origin = from_alone.group(1).strip()

    # Pattern E: "X to Y"
    if not origin or not destination:
        to_pat = re.search(r'([^,]+?)\s+to\s+([^,]+?)(?:\s+at|\s+by|\s+around|\s+walking|\s+driving|$)', cleaned_t)
        if to_pat:
            if not origin: origin = to_pat.group(1).strip()
            if not destination: destination = to_pat.group(2).strip()

    # Clean recognized keywords out of origin/destination
    noise = ["walking", "driving", "safest", "safest way", "show me", "i am", "i'm", "going", "leave", "leaving", "need to", "want to", "go to", "go"]
    for n in noise:
        origin = re.sub(rf'\b{n}\b', '', origin).strip()
        destination = re.sub(rf'\b{n}\b', '', destination).strip()

    if not origin:
        origin = "office" if "office" in t else ("church street" if "church" in t else "Indiranagar")
    if not destination:
        destination = "home" if "home" in t or "ghar" in t else ("koramangala" if "koramangala" in t else "MG Road")

    # Map colloquial Hinglish synonyms
    if origin.lower() == "ghar":
        origin = "home"
    if destination.lower() == "ghar":
        destination = "home"

    return {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "departure_time": dep_time
    }

async def call_ollama_json(prompt: str, system: str, retries: int = 1) -> Optional[dict]:
    """Calls Ollama with temperature=0 and format='json' with fast context options."""
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={
                        "model": LLM_MODEL,
                        "system": system,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 128, "num_ctx": 1024}
                    }
                )
                if res.status_code == 200:
                    raw_text = res.json().get("response", "").strip()
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict) and "origin" in parsed and "destination" in parsed:
                        return parsed
        except Exception:
            pass
    return None

async def parse_user_request(text: str, saved_places: dict | None = None) -> ParsedUserQuery:
    """Parses user natural query using fast deterministic regex first, then Ollama + strict Pydantic validation."""
    fast_parsed = regex_fallback_parser(text)
    t = text.lower()
    
    # If the user query directly matches origin and destination, use fast parser (0.001s vs 5s)
    has_origin = fast_parsed["origin"].lower() in t or (saved_places and fast_parsed["origin"].lower() in saved_places)
    has_dest = fast_parsed["destination"].lower() in t or (saved_places and fast_parsed["destination"].lower() in saved_places)
    
    if has_origin and has_dest:
        extracted = fast_parsed
    else:
        extracted = await call_ollama_json(
            prompt=f'Extract navigation parameters from: "{text}"',
            system=AGENT_SYSTEM_PROMPT
        )
        if not extracted:
            extracted = fast_parsed

    # Resolve saved places
    saved = saved_places or {}
    orig = extracted.get("origin", "").strip()
    dest = extracted.get("destination", "").strip()

    orig_clean = saved.get(orig.lower(), orig)
    dest_clean = saved.get(dest.lower(), dest)

    return ParsedUserQuery(
        origin=orig_clean or "Office",
        destination=dest_clean or "Home",
        mode="driving" if extracted.get("mode") == "driving" else "walking",
        departure_time=extracted.get("departure_time", "now"),
        raw_query=text
    )

def validate_explanation_numbers(explanation: str, route_data: dict) -> bool:
    """
    Checks if numbers cited in the generated explanation match ground-truth route data.
    Prevents LLM hallucinations from reaching the user.
    """
    found_nums = [float(n) for n in re.findall(r'\b\d+(?:\.\d+)?\b', explanation)]
    if not found_nums:
        return True

    # Collect valid ground truth numbers
    valid_nums = set()
    for r in route_data.get("routes", []):
        valid_nums.add(round(r.get("distance_m", 0) / 1000.0, 1))
        valid_nums.add(round(r.get("duration_s", 0) / 60.0))
        valid_nums.add(round(r.get("duration_s", 0) / 60.0, 1))
        valid_nums.add(round(r.get("night_score", 0)))
        valid_nums.add(round(r.get("night_score", 0), 1))
        m = r.get("metrics", {})
        for v in m.values():
            if isinstance(v, (int, float)):
                valid_nums.add(round(float(v)))
                valid_nums.add(round(float(v), 1))
        b = r.get("breakdown", {})
        for comp in b.values():
            if isinstance(comp, dict):
                p = comp.get("points")
                if isinstance(p, (int, float)):
                    valid_nums.add(round(float(p)))
                    valid_nums.add(round(float(p), 1))

    t_off = route_data.get("trade_off", {})
    for v in t_off.values():
        if isinstance(v, (int, float)):
            valid_nums.add(round(float(v)))
            valid_nums.add(round(float(v), 1))

    # Common hours/integers allowed
    allowed_commons = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 100}
    for fn in found_nums:
        if fn not in valid_nums and fn not in allowed_commons:
            return False # Detected hallucinated figure
    return True

async def generate_explanation(workflow_res: dict) -> str:
    """
    Synthesizes a 3-4 sentence trade-off explanation using Ollama,
    verified with numerical validation against raw data and biggest difference component.
    """
    routes = workflow_res["routes"]
    fastest = next(r for r in routes if r["id"] == workflow_res["fastest_route_id"])
    safest = next(r for r in routes if r["id"] == workflow_res["safest_route_id"])
    trade_off = workflow_res["trade_off"]

    fastest_min = round(fastest["duration_s"] / 60.0, 1)
    safest_min = round(safest["duration_s"] / 60.0, 1)
    diff_comp = trade_off.get("biggest_diff_component", "social presence")
    diff_pts = trade_off.get("biggest_diff_points", 0.0)

    # Deterministic template explanation
    if fastest["id"] == safest["id"]:
        template_exp = (
            f"{fastest['name']} is both the fastest ({fastest_min} min) and highest-scoring route "
            f"(Night Score {safest['night_score']}/100), passing {safest['metrics']['open_places_count']} "
            f"open establishments and {safest['metrics']['cameras_count']} active surveillance cameras. "
            f"It maximizes mapped visibility while keeping travel time minimal. "
            f"The choice is entirely yours."
        )
    else:
        template_exp = (
            f"Fastest option ({fastest['name']}) takes {fastest_min} min with a Night Score of {fastest['night_score']}/100. "
            f"Safest option ({safest['name']}) takes {safest_min} min ({trade_off['time_diff_min']} min extra) "
            f"and achieves a Night Score of {safest['night_score']}/100 (+{trade_off['score_diff']} pts), "
            f"mainly because of higher {diff_comp.lower()} (+{diff_pts} pts) and {safest['metrics']['cameras_count']} cameras. "
            f"You choose whether the extra minutes are worth the higher mapped environmental support."
        )

    # Attempt LLM generation
    prompt = f"""
    Route Data:
    - Fastest Route: {fastest['name']}, Duration: {fastest_min} min, Night Score: {fastest['night_score']}, Open Places: {fastest['metrics']['open_places_count']}, Cameras: {fastest['metrics']['cameras_count']}
    - Safest Route: {safest['name']}, Duration: {safest_min} min, Night Score: {safest['night_score']}, Open Places: {safest['metrics']['open_places_count']}, Cameras: {safest['metrics']['cameras_count']}
    - Trade-off: +{trade_off['time_diff_min']} min extra for +{trade_off['score_diff']} score points, primary factor: {diff_comp}.
    Write a 3-sentence grounded trade-off summary according to your instructions.
    """
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            res = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "system": EXPLANATION_SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 80, "num_ctx": 1024}
                }
            )
            if res.status_code == 200:
                candidate = res.json().get("response", "").strip()
                if candidate and validate_explanation_numbers(candidate, workflow_res):
                    return candidate
    except Exception:
        pass

    return template_exp

async def run_agent(message: str, saved_places: dict | None = None) -> AgentChatResponse:
    """
    Full GenAI Agent pipeline:
    1. Parse natural language request into structured fields.
    2. Execute deterministic route and scoring tools.
    3. Synthesize validated trade-off explanation.
    """
    trace = ["Understood natural language request."]
    
    # 1. Parsing
    parsed = await parse_user_request(message, saved_places)
    trace.append(f"Extracted parameters: Origin='{parsed.origin}', Destination='{parsed.destination}', Mode='{parsed.mode}', Departure='{parsed.departure_time}'")

    # 2. Tool calling
    trace.append("Executing navigation & scoring tools: Geocoding -> Routing -> Corridor Data -> Night Activity Score.")
    workflow_res = await execute_route_workflow(
        origin_query=parsed.origin,
        destination_query=parsed.destination,
        mode=parsed.mode,
        departure_time_str=parsed.departure_time,
        saved_places=saved_places
    )
    trace.append(f"Scored {len(workflow_res['routes'])} alternative routes. Identified Safest={workflow_res['safest_route_id']} and Fastest={workflow_res['fastest_route_id']}.")

    # 3. Grounded explanation
    explanation = await generate_explanation(workflow_res)
    trace.append("Synthesized validated, grounded trade-off explanation.")

    return AgentChatResponse(
        parsed=parsed,
        routes=workflow_res["routes"],
        recommendation=workflow_res["safest_route_id"],
        safest_route_id=workflow_res["safest_route_id"],
        fastest_route_id=workflow_res["fastest_route_id"],
        trade_off_summary=explanation,
        trace=trace,
        disclaimer=DISCLAIMER_TEXT,
        origin=workflow_res.get("origin"),
        destination=workflow_res.get("destination"),
        data_confidence=workflow_res.get("data_confidence"),
        confidence_warning=workflow_res.get("confidence_warning"),
        trade_off=workflow_res.get("trade_off"),
        corridor_places=workflow_res.get("corridor_places", []),
        corridor_cameras=workflow_res.get("corridor_cameras", [])
    )
