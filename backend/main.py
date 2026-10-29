import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx

from .config import (
    BACKEND_DIR, PROJECT_ROOT, GEOAPIFY_API_KEY,
    OLLAMA_HOST, LLM_MODEL, HF_DIR
)
from .agent.schemas import (
    AgentChatRequest, AgentChatResponse,
    StructuredRouteRequest
)
from .agent.agent import run_agent
from .agent.tools import execute_route_workflow
from .services.geocode import geocode
from .attention.hf_attention import extract_attention
from .scoring.weights import (
    WALKING_WEIGHTS, DRIVING_WEIGHTS, SATURATION_K,
    SCORING_PARAMS, COMPONENT_METADATA, DISCLAIMER_TEXT
)

app = FastAPI(
    title="NightWise AI",
    description="Safety-first navigation assistant with custom Transformer attention visualization",
    version="2.0.0"
)

# CORS setup for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"

@app.get("/api/health")
async def health_check():
    """Reports health status of Ollama, HF model weights, and Geoapify."""
    # Check Ollama
    ollama_ok = False
    ollama_models = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                data = resp.json()
                ollama_models = [m.get("name") for m in data.get("models", [])]
    except Exception:
        pass

    # Check HuggingFace local directory
    hf_weights_present = (HF_DIR / "config.json").exists() and (
        (HF_DIR / "model.safetensors").exists() or (HF_DIR / "pytorch_model.bin").exists()
    )

    return {
        "status": "healthy",
        "ollama": {
            "connected": ollama_ok,
            "host": OLLAMA_HOST,
            "configured_model": LLM_MODEL,
            "available_models": ollama_models
        },
        "huggingface": {
            "cached_locally": hf_weights_present,
            "model_path": str(HF_DIR)
        },
        "geoapify": {
            "configured": bool(GEOAPIFY_API_KEY),
            "key_present": bool(GEOAPIFY_API_KEY)
        }
    }

@app.get("/api/config")
async def get_app_config():
    """Returns runtime client configuration for OpenFreeMap vector styles and fallbacks."""
    return {
        "primary_map_style": "https://tiles.openfreemap.org/styles/dark",
        "fallback_map_style": "https://tiles.openfreemap.org/styles/liberty",
        "carto_dark_tiles": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "map_style_url": "https://tiles.openfreemap.org/styles/dark",
        "geoapify_key": GEOAPIFY_API_KEY,
        "geoapify_configured": bool(GEOAPIFY_API_KEY)
    }

@app.get("/api/weights")
async def api_get_weights():
    """Returns dynamic scoring configuration for frontend explainers."""
    return {
        "walking": WALKING_WEIGHTS,
        "driving": DRIVING_WEIGHTS,
        "saturation_k": SATURATION_K,
        "params": SCORING_PARAMS,
        "metadata": COMPONENT_METADATA,
        "disclaimer": DISCLAIMER_TEXT
    }

@app.get("/api/geocode")
async def api_geocode(q: str = Query(..., min_length=1, description="Location search text")):
    """Geocode autocomplete endpoint biased to India."""
    try:
        results = await geocode(q)
        return {"query": q, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/routes")
async def api_plan_routes(req: StructuredRouteRequest):
    """
    Direct structured route planning and scoring endpoint.
    Runs without the LLM as a reliable fallback.
    """
    try:
        workflow_res = await execute_route_workflow(
            origin_query=req.origin,
            destination_query=req.destination,
            mode=req.mode,
            departure_time_str=req.departure_time or "now"
        )
        return workflow_res
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")

@app.post("/api/agent", response_model=AgentChatResponse)
async def api_agent_chat(req: AgentChatRequest):
    """
    Natural language GenAI Agent endpoint.
    Parses request with Qwen2.5, runs tools, returns scored routes and grounded trade-off explanation.
    """
    try:
        resp = await run_agent(req.message, req.saved_places)
        return resp
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow error: {str(e)}")

@app.post("/api/attention")
async def api_attention(payload: dict):
    """
    Self-Attention visualization endpoint.
    Returns token sequence, layer/head attention tensors, and Qwen2.5 architecture parameters.
    """
    text = payload.get("text", "I'm leaving office and walking home at 2 AM, show me the safest way.")
    try:
        data = extract_attention(text)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attention extraction failed: {str(e)}")

# Mount frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "NightWise AI backend active. Frontend index.html not found."}

    @app.get("/{full_path:path}")
    async def serve_frontend_assets(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="File not found")
