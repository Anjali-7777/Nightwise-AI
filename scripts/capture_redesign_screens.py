import os
import sys
import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs" / "screenshots"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARTIFACT_DIR = Path(r"C:\Users\adi\.gemini\antigravity\brain\b4164b27-a799-4364-8a7a-271e09627974")

# Locate msedge executable
CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\EdgeCore\*\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
]

browser_exe = None
for pat in CANDIDATES:
    matches = glob.glob(pat)
    if matches:
        browser_exe = matches[0]
        break

if not browser_exe:
    print("Error: Could not find msedge or chrome executable")
    sys.exit(1)

print(f"Using browser: {browser_exe}")

SHOTS = [
    {
        "name": "desktop_1440x900_dark.png",
        "url": "http://127.0.0.1:8000/?origin=RUB+College+Nagpur&dest=VR+Mall+Nagpur&theme=dark",
        "width": 1440,
        "height": 900
    },
    {
        "name": "desktop_1440x900_light.png",
        "url": "http://127.0.0.1:8000/?origin=RUB+College+Nagpur&dest=VR+Mall+Nagpur&theme=light",
        "width": 1440,
        "height": 900
    },
    {
        "name": "tablet_768x1024_dark.png",
        "url": "http://127.0.0.1:8000/?origin=Church+Street&dest=Indiranagar&theme=dark",
        "width": 768,
        "height": 1024
    },
    {
        "name": "mobile_390x844_dark.png",
        "url": "http://127.0.0.1:8000/?origin=Church+Street&dest=Indiranagar&theme=dark",
        "width": 390,
        "height": 844
    },
    {
        "name": "desktop_ai_lab.png",
        "url": "http://127.0.0.1:8000/?view=ai-lab",
        "width": 1440,
        "height": 900
    },
    {
        "name": "desktop_score_explainer.png",
        "url": "http://127.0.0.1:8000/?view=score",
        "width": 1440,
        "height": 900
    }
]

def run_captures():
    print("==================================================")
    print("  Capturing Multi-Screen Redesign Screenshots     ")
    print("==================================================")

    for item in SHOTS:
        out_path = DOCS_DIR / item["name"]
        temp_dir = tempfile.mkdtemp()

        args = [
            browser_exe,
            "--headless",
            "--disable-gpu",
            f"--window-size={item['width']},{item['height']}",
            f"--user-data-dir={temp_dir}",
            "--virtual-time-budget=9000",
            f"--screenshot={out_path}",
            item["url"]
        ]

        print(f"\nCapturing {item['name']} ({item['width']}x{item['height']})...")
        try:
            res = subprocess.run(args, timeout=20, capture_output=True)
            if out_path.exists():
                print(f"  [OK] Saved to {out_path} ({out_path.stat().st_size} bytes)")
            else:
                print(f"  [FAIL] Error: Output file not created for {item['name']}")
        except Exception as e:
            print(f"  ! Capture error: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Copy primary representations into conversation artifact directory
    dark_desk = DOCS_DIR / "desktop_1440x900_dark.png"
    ai_lab = DOCS_DIR / "desktop_ai_lab.png"

    if dark_desk.exists():
        target = ARTIFACT_DIR / "nightwise_app_ui.png"
        shutil.copy2(dark_desk, target)
        print(f"\nUpdated Artifact UI: {target}")

    if ai_lab.exists():
        target_attn = ARTIFACT_DIR / "nightwise_attention_ui.png"
        shutil.copy2(ai_lab, target_attn)
        print(f"Updated Artifact Attention: {target_attn}")

    print("\nAll screenshots captured successfully!")

if __name__ == "__main__":
    run_captures()
