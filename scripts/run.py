import os
import sys
import time
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import (
    OLLAMA_DIR, OLLAMA_HOST, NIGHTWISE_HOST, NIGHTWISE_PORT
)

def ensure_ollama_running():
    # Set isolated OLLAMA_MODELS to project folder
    os.environ["OLLAMA_MODELS"] = str(OLLAMA_DIR)
    
    # Check if Ollama is listening
    import urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=1) as resp:
            if resp.status == 200:
                print(f"[Ollama] Daemon already responsive at {OLLAMA_HOST}")
                return
    except Exception:
        pass

    ollama_cmd = shutil.which("ollama")
    if not ollama_cmd and sys.platform == "win32":
        default_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if default_path.exists():
            ollama_cmd = str(default_path)

    if ollama_cmd:
        print(f"[Ollama] Starting background daemon with OLLAMA_MODELS={OLLAMA_DIR}...")
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(OLLAMA_DIR)
        subprocess.Popen(
            [ollama_cmd, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    else:
        print("[Ollama] Ollama executable not found in PATH; proceeding with offline deterministic fallbacks.")

def main():
    print("==================================================")
    print("      NightWise AI - Safety Navigation Server     ")
    print("==================================================")
    ensure_ollama_running()
    
    import uvicorn
    print(f"\n[Server] Starting FastAPI application on http://{NIGHTWISE_HOST}:{NIGHTWISE_PORT}")
    print("[Server] Interactive map and attention explorer available in browser.\n")
    uvicorn.run(
        "backend.main:app",
        host=NIGHTWISE_HOST,
        port=NIGHTWISE_PORT,
        log_level="info"
    )

if __name__ == "__main__":
    main()
