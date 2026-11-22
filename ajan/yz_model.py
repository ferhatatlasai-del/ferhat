"""OpenAI metin modeli seçimi (panelden ayarlanır: yapay_zeka/ayar.json).

Öncelik: panelde seçilen rol modeli > OPENAI_MODEL ortam değişkeni (GitHub variable) > çağıran kodun varsayılanı.
Roller: yonetici (yönetici ajan + video izleme), video (viral video senaryosu), genel (hikâye metni, yorum, trend, akademi, başarı, taslak).
Boş bırakılan rol ortam değişkenine/varsayılana düşer.
"""
import json
import os
import pathlib
import re

KOK = pathlib.Path(__file__).resolve().parent.parent
DOSYA = KOK / "yapay_zeka" / "ayar.json"
GECERLI = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,47}$")


def ayar_oku():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8")).get("roller") or {}
    except Exception:
        return {}


def model(rol="genel", varsayilan="gpt-5.4-mini"):
    secilen = str(ayar_oku().get(rol) or "").strip()
    if secilen and GECERLI.match(secilen):
        return secilen
    return os.environ.get("OPENAI_MODEL") or varsayilan
