import asyncio
import json
import subprocess
import time
import httpx
import websockets
from pathlib import Path

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACT_DIR = Path(r"C:\Users\adi\.gemini\antigravity\brain\b4164b27-a799-4364-8a7a-271e09627974")

async def capture():
    print("[Chrome CDP] Launching Headless Chrome with Remote Debugging...")
    import tempfile
    temp_dir = tempfile.mkdtemp()
    proc = subprocess.Popen([
        CHROME_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={temp_dir}",
        "--window-size=1280,850",
        "--disable-gpu",
        "--no-sandbox"
    ])

    await asyncio.sleep(2.0)

    try:
        async with httpx.AsyncClient() as client:
            # Poll until Chrome CDP is ready
            ws_url = None
            for _ in range(10):
                try:
                    v_resp = await client.get("http://127.0.0.1:9222/json/version")
                    if v_resp.status_code == 200:
                        v_data = v_resp.json()
                        ws_url = v_data.get("webSocketDebuggerUrl")
                        break
                except Exception:
                    await asyncio.sleep(0.5)

            # Get page target
            tab_resp = await client.get("http://127.0.0.1:9222/json/list")
            tabs = tab_resp.json()
            if tabs:
                ws_url = tabs[0]["webSocketDebuggerUrl"]
            else:
                new_tab = (await client.put("http://127.0.0.1:9222/json/new?http://127.0.0.1:8000")).json()
                ws_url = new_tab["webSocketDebuggerUrl"]

            if not ws_url:
                raise RuntimeError("Could not find page target WebSocket URL")

        print(f"[Chrome CDP] Connected to WebSocket: {ws_url}")
        async with websockets.connect(ws_url) as ws:
            msg_id = 1

            async def send_cmd(method, params=None):
                nonlocal msg_id
                cid = msg_id
                msg_id += 1
                payload = {"id": cid, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    raw = await ws.recv()
                    data = json.loads(raw)
                    if data.get("id") == cid:
                        return data

            # Enable Page & Runtime
            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000"})

            print("[Chrome CDP] Waiting for page load...")
            await asyncio.sleep(4.0)

            # Trigger Route Search: Nagpur
            print("[Chrome CDP] Filling inputs and executing route search...")
            search_script = """
            (async () => {
                const originInput = document.getElementById('origin-input');
                const destInput = document.getElementById('dest-input');
                if (originInput) originInput.value = 'RUB College Nagpur';
                if (destInput) destInput.value = 'VR Mall Nagpur';
                const submitBtn = document.getElementById('submit-btn') || document.querySelector('.btn-primary');
                if (submitBtn) submitBtn.click();
            })();
            """
            await send_cmd("Runtime.evaluate", {"expression": search_script, "awaitPromise": True})

            # Wait 5 seconds for OSRM routes, Overpass data & MapLibre layers to draw
            print("[Chrome CDP] Waiting for map and routes to render...")
            await asyncio.sleep(5.0)

            # Capture Screenshot of App UI
            print("[Chrome CDP] Capturing nightwise_app_ui.png...")
            res_app = await send_cmd("Page.captureScreenshot", {"format": "png"})
            import base64
            img_bytes = base64.b64decode(res_app["result"]["data"])
            app_ui_path = ARTIFACT_DIR / "nightwise_app_ui.png"
            with open(app_ui_path, "wb") as f:
                f.write(img_bytes)
            print(f"[Chrome CDP] Saved: {app_ui_path} ({len(img_bytes)} bytes)")

            # Now switch to Attention view
            print("[Chrome CDP] Switching to Transformer Attention Explorer...")
            attn_script = """
            (async () => {
                const attnTab = document.getElementById('tab-attention') || document.querySelector('a[href="#attention"]') || document.querySelector('[data-view="attention"]');
                if (attnTab) {
                    attnTab.click();
                } else {
                    window.location.hash = '#attention';
                }
                const inspectBtn = document.getElementById('inspect-attn-btn') || document.querySelector('.btn-attention');
                if (inspectBtn) inspectBtn.click();
            })();
            """
            await send_cmd("Runtime.evaluate", {"expression": attn_script, "awaitPromise": True})
            await asyncio.sleep(4.0)

            print("[Chrome CDP] Capturing nightwise_attention_ui.png...")
            res_attn = await send_cmd("Page.captureScreenshot", {"format": "png"})
            img_attn_bytes = base64.b64decode(res_attn["result"]["data"])
            attn_ui_path = ARTIFACT_DIR / "nightwise_attention_ui.png"
            with open(attn_ui_path, "wb") as f:
                f.write(img_attn_bytes)
            print(f"[Chrome CDP] Saved: {attn_ui_path} ({len(img_attn_bytes)} bytes)")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()
        print("[Chrome CDP] Chrome process terminated cleanly.")

if __name__ == "__main__":
    asyncio.run(capture())
