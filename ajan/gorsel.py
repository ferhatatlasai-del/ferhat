#!/usr/bin/env python3
"""OpenAI görsel API'siyle görsel üretir ve gorseller/ klasörüne PNG olarak kaydeder.

Kullanım:
    OPENAI_API_KEY=... python3 ajan/gorsel.py --n 3                  # Doktor Filament ana görseli
    OPENAI_API_KEY=... python3 ajan/gorsel.py --prompt "..." --ad kapak --n 2
    python3 ajan/gorsel.py --dry-run                                  # API çağırmadan prompt'u gösterir
"""
import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
CIKTI = KOK / "gorseller"
MODEL = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"
YEDEK_MODEL = "gpt-image-1"

PERSONA_PROMPT_SONU = (
    " Waist-up portrait, facing the camera, warm friendly smile, soft studio lighting, photorealistic."
    " No text, no letters, no readable text on clothing, no logos, no watermark."
)


def persona_prompt():
    """Doktor Filament tarifini kanal.md'den alır (tek kaynak)."""
    metin = (KOK / "ajan" / "kanal.md").read_text(encoding="utf-8")
    m = re.search(r'"(Doctor Filament: [^"]+)"', metin)
    tarif = m.group(1) if m else "Doctor Filament: a fictional, eccentric but friendly inventor character"
    return tarif + PERSONA_PROMPT_SONU


def uret(model, prompt, n, boyut, kalite):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        sys.exit("OPENAI_API_KEY ortam değişkeni tanımlı değil.")
    govde = json.dumps({"model": model, "prompt": prompt, "n": n, "size": boyut, "quality": kalite}).encode()
    istek = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=govde,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"},
    )
    with urllib.request.urlopen(istek, timeout=300) as yanit:
        return json.load(yanit)["data"]


def kisa(yol):
    try:
        return yol.relative_to(KOK)
    except ValueError:
        return yol


def hata_ozeti(e):
    try:
        return json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:220]
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="", help="Boşsa Doktor Filament ana görseli promptu kullanılır")
    ap.add_argument("--ad", default="doktor-filament", help="Dosya adı öneki")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--boyut", default="1024x1536", help="1024x1024 | 1024x1536 | 1536x1024")
    ap.add_argument("--kalite", default="medium", help="low | medium | high")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    prompt = a.prompt.strip() or persona_prompt()
    n = max(1, min(a.n, 6))
    if a.dry_run:
        print(f"model={MODEL} n={n} boyut={a.boyut} kalite={a.kalite}\n{prompt}")
        return

    try:
        veri = uret(MODEL, prompt, n, a.boyut, a.kalite)
        kullanilan = MODEL
    except urllib.error.HTTPError as e:
        if MODEL == YEDEK_MODEL or e.code not in (400, 404):
            print(f"Görsel API hatası: HTTP {e.code} {hata_ozeti(e)}")
            sys.exit(1)
        print(f"UYARI: '{MODEL}' kullanılamadı (HTTP {e.code}: {hata_ozeti(e)}). Yedek: {YEDEK_MODEL}")
        try:
            veri = uret(YEDEK_MODEL, prompt, n, a.boyut, a.kalite)
            kullanilan = YEDEK_MODEL + " (yedek)"
        except urllib.error.HTTPError as e2:
            print(f"Görsel API hatası: HTTP {e2.code} {hata_ozeti(e2)}")
            sys.exit(1)

    CIKTI.mkdir(exist_ok=True)
    damga = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    yazilan = 0
    for i, oge in enumerate(veri, 1):
        if not oge.get("b64_json"):
            continue
        yol = CIKTI / f"{a.ad}-{damga}-{i}.png"
        yol.write_bytes(base64.b64decode(oge["b64_json"]))
        print(f"Yazıldı: {kisa(yol)}")
        yazilan += 1
    print(f"Model: {kullanilan}, {yazilan} görsel.")
    if not yazilan:
        sys.exit(1)


if __name__ == "__main__":
    main()
