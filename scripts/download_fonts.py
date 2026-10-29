import os
import re
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

FONT_URLS = [
    # Instrument Serif (Regular & Italic)
    "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap",
    # Bricolage Grotesque
    "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..700&display=swap",
    # Martian Mono
    "https://fonts.googleapis.com/css2?family=Martian+Mono:wght@400;600&display=swap"
]

def fetch_and_save():
    print(f"Downloading self-hosted fonts to: {FONTS_DIR}")
    downloaded = 0

    for css_url in FONT_URLS:
        try:
            req = urllib.request.Request(css_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                css_content = resp.read().decode("utf-8")

            # Extract @font-face blocks
            blocks = css_content.split("@font-face")
            for block in blocks:
                if "latin" not in block and "/* latin */" not in block and "unicode-range" in block and "U+0000" not in block:
                    continue # Prefer standard latin subset

                fam_match = re.search(r"font-family:\s*['\"]([^'\"]+)['\"]", block)
                weight_match = re.search(r"font-weight:\s*([^;]+);", block)
                style_match = re.search(r"font-style:\s*([^;]+);", block)
                url_match = re.search(r"url\((https://[^)]+\.woff2)\)", block)

                if fam_match and url_match:
                    family = fam_match.group(1).replace(" ", "")
                    weight = (weight_match.group(1).strip() if weight_match else "400").replace(" ", "")
                    style = (style_match.group(1).strip() if style_match else "normal")
                    font_url = url_match.group(1)

                    # Create clean local filename
                    filename = f"{family}-{style}-{weight}.woff2"
                    dest_path = FONTS_DIR / filename

                    if not dest_path.exists():
                        font_req = urllib.request.Request(font_url, headers=HEADERS)
                        with urllib.request.urlopen(font_req, timeout=10) as f_resp:
                            dest_path.write_bytes(f_resp.read())
                        print(f"  [OK] Downloaded {filename} ({dest_path.stat().st_size} bytes)")
                        downloaded += 1
                    else:
                        print(f"  [-] Already present: {filename}")
        except Exception as e:
            print(f"  ! Warning: could not download from {css_url}: {e}")

    print(f"\nFont download complete. Total files in {FONTS_DIR}: {len(list(FONTS_DIR.glob('*.woff2')))}")

if __name__ == "__main__":
    fetch_and_save()
