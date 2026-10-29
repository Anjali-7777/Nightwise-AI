import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CACHE_DIR = BACKEND_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Load .env file
load_dotenv(PROJECT_ROOT / ".env")

# Model directories
MODELS_DIR = PROJECT_ROOT / "models"
OLLAMA_DIR = PROJECT_ROOT / "models" / "ollama"
HF_DIR = PROJECT_ROOT / "models" / "hf"
OLLAMA_DIR.mkdir(parents=True, exist_ok=True)
HF_DIR.mkdir(parents=True, exist_ok=True)

# Configuration keys
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
if GEOAPIFY_API_KEY == "your_key_here":
    GEOAPIFY_API_KEY = ""

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:0.5b-instruct")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

NIGHTWISE_HOST = os.getenv("NIGHTWISE_HOST", "127.0.0.1")
NIGHTWISE_PORT = int(os.getenv("NIGHTWISE_PORT", "8000"))

USER_AGENT = "NightWise-AI-SafetyNavigator/1.0 (academic student research project)"
