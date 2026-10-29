import os
import sys
import time
import json
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLLAMA_DIR = PROJECT_ROOT / "models" / "ollama"
HF_DIR = PROJECT_ROOT / "models" / "hf"
OLLAMA_MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5:0.5b-instruct")
HF_MODEL_NAME = os.getenv("HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

def ensure_dirs():
    OLLAMA_DIR.mkdir(parents=True, exist_ok=True)
    HF_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Verified local model storage directories:")
    print(f"      - Ollama: {OLLAMA_DIR}")
    print(f"      - HuggingFace: {HF_DIR}")

def stop_existing_ollama():
    print("[2/4] Ensuring Ollama runs with project-isolated models directory...")
    # Terminate existing ollama processes so it restarts with OLLAMA_MODELS pointing to project
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "ollama app.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
    time.sleep(1.5)

def start_ollama():
    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(OLLAMA_DIR)
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    
    # Check if ollama binary is in PATH
    ollama_cmd = shutil.which("ollama")
    if not ollama_cmd and sys.platform == "win32":
        default_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if default_path.exists():
            ollama_cmd = str(default_path)
            
    if not ollama_cmd:
        raise RuntimeError("Ollama executable not found in PATH or standard installation path.")

    print(f"      Starting Ollama daemon with OLLAMA_MODELS={OLLAMA_DIR}...")
    proc = subprocess.Popen(
        [ollama_cmd, "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for server to respond
    import urllib.request
    started = False
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=1) as resp:
                if resp.status == 200:
                    started = True
                    break
        except Exception:
            time.sleep(0.5)

    if not started:
        print("      Warning: Ollama server ping timed out; proceeding to pull attempt.")
    else:
        print("      Ollama daemon is active and listening on port 11434.")
    return ollama_cmd, env

def pull_ollama_model(ollama_cmd, env):
    print(f"      Checking Ollama model '{OLLAMA_MODEL_NAME}' in {OLLAMA_DIR}...")
    # Check if already in manifests
    manifest_path = OLLAMA_DIR / "manifests" / "registry.ollama.ai" / "library" / OLLAMA_MODEL_NAME.split(":")[0] / (OLLAMA_MODEL_NAME.split(":")[1] if ":" in OLLAMA_MODEL_NAME else "latest")
    if manifest_path.exists():
        print(f"      Model '{OLLAMA_MODEL_NAME}' is already present in project models directory. Skipping pull.")
        return

    print(f"      Pulling '{OLLAMA_MODEL_NAME}' into project directory...")
    res = subprocess.run([ollama_cmd, "pull", OLLAMA_MODEL_NAME], env=env)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to pull {OLLAMA_MODEL_NAME} via Ollama.")
    print(f"      Successfully pulled '{OLLAMA_MODEL_NAME}'.")

def download_hf_model():
    print(f"[3/4] Checking Hugging Face model '{HF_MODEL_NAME}' in {HF_DIR}...")
    weight_file = HF_DIR / "model.safetensors"
    config_file = HF_DIR / "config.json"
    if weight_file.exists() and config_file.exists():
        print(f"      Model files already present in {HF_DIR}. Skipping download.")
        return

    print(f"      Downloading '{HF_MODEL_NAME}' using snapshot_download...")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id=HF_MODEL_NAME,
        local_dir=str(HF_DIR),
        local_dir_use_symlinks=False
    )
    print("      Hugging Face model successfully downloaded to project folder.")

def verify_models():
    print("[4/4] Verifying model execution...")
    import urllib.request
    
    # 1. Verify Ollama
    print("      Testing Ollama inference...")
    req_data = json.dumps({
        "model": OLLAMA_MODEL_NAME,
        "prompt": "Say 'Ollama operational'",
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            ollama_reply = data.get("response", "").strip()
            print(f"      [OK] Ollama responded: {ollama_reply[:60]}...")
    except Exception as e:
        print(f"      [WARN] Ollama test prompt error: {e}")

    # 2. Verify Hugging Face with eager attention
    print("      Testing Hugging Face eager attention loading...")
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        tokenizer = AutoTokenizer.from_pretrained(str(HF_DIR))
        model = AutoModelForCausalLM.from_pretrained(
            str(HF_DIR),
            torch_dtype=torch.float32,
            device_map="cpu",
            attn_implementation="eager"
        )
        inputs = tokenizer("Hello", return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs, output_attentions=True)
        num_layers = len(outputs.attentions)
        attn_shape = outputs.attentions[0].shape
        print(f"      [OK] Hugging Face loaded: {num_layers} layers, attention tensor shape per layer: {attn_shape}")
    except Exception as e:
        print(f"      [WARN] HF test prompt error: {e}")

def main():
    print("==================================================")
    print("   NightWise AI - Model Setup & Verification     ")
    print("==================================================")
    ensure_dirs()
    stop_existing_ollama()
    ollama_cmd, env = start_ollama()
    pull_ollama_model(ollama_cmd, env)
    download_hf_model()
    verify_models()
    print("==================================================")
    print("   Setup Complete: All Models Stored Locally!    ")
    print("==================================================")

if __name__ == "__main__":
    main()
