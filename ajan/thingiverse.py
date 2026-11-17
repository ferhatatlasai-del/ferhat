#!/usr/bin/env python3
"""Thingiverse resmi servisi (api.thingiverse.com) için küçük istemci.

Lisans, tasarımcı, popülerlik ve fotoğraf adresi sitenin kendi verisinden okunur (arama motoruna güvenilmez).
Erişim anahtarı THINGIVERSE_TOKEN ortam değişkeninden gelir; yoksa hazir() False döner ve ajanlar bu kaynağı atlar.
Hiçbir şey yayınlamaz, depoya yazmaz.

Anahtar almak: thingiverse.com -> Apps / Developers -> "Create an App" (ücretsiz) -> "App Token".
"""
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("THINGIVERSE_API") or "https://api.thingiverse.com"
BOT_ADI = "Mozilla/5.0 (compatible; DoktorFilamentBot/1.0; tasarim atfi icin)"


class ThingiverseHata(Exception):
    pass


def anahtar():
    return (os.environ.get("THINGIVERSE_TOKEN") or "").strip().strip('"').strip("'")


def hazir():
    return bool(anahtar())


def _al(yol, **sorgu):
    if not hazir():
        raise ThingiverseHata("THINGIVERSE_TOKEN tanımlı değil")
    adres = f"{API}{yol}" + (("?" + urllib.parse.urlencode({k: v for k, v in sorgu.items() if v is not None})) if sorgu else "")
    r = urllib.request.Request(adres, headers={"Authorization": f"Bearer {anahtar()}", "User-Agent": BOT_ADI, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as y:
            return json.load(y)
    except urllib.error.HTTPError as e:
        raise ThingiverseHata(f"servis HTTP {e.code}")
    except Exception as e:
        raise ThingiverseHata(f"servis ulaşılamadı ({type(e).__name__})")


def _liste(v):
    """Servis bazen düz liste, bazen {'hits': [...]} döndürür."""
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        for k in ("hits", "things", "results"):
            if isinstance(v.get(k), list):
                return v[k]
    return []


def populer(adet=30, sayfa=1):
    """Şu an popüler tasarımlar (özet kayıtlar)."""
    return _liste(_al("/popular", per_page=adet, page=sayfa))


def ara(terim, adet=15):
    """Terime göre en popüler tasarımlar (özet kayıtlar)."""
    return _liste(_al(f"/search/{urllib.parse.quote(terim)}", sort="popular", per_page=adet, page=1, type="things"))


def detay(kimlik):
    return _al(f"/things/{int(kimlik)}")


def duz_metin(h, en_cok=300):
    t = re.sub(r"<[^>]+>", " ", h or "")
    t = re.sub(r"[#*_`>\[\]()]", " ", html.unescape(t))
    return " ".join(t.split())[:en_cok]


def en_iyi_gorsel(d):
    """Detay kaydından büyük fotoğraf adresi (yoksa önizleme ya da küçük resim)."""
    di = d.get("default_image") or {}
    boyutlar = di.get("sizes") or []
    for tur, boy in (("display", "large"), ("display", "medium"), ("preview", "large"), ("preview", "featured")):
        for b in boyutlar:
            if b.get("type") == tur and b.get("size") == boy and b.get("url"):
                return b["url"]
    return di.get("url") or d.get("preview_image") or d.get("thumbnail")


def kayit_bilgisi(d):
    """Detay kaydından ajanların kullanacağı sade sözlük."""
    kimlik = d.get("id")
    return {
        "id": kimlik,
        "ad": (d.get("name") or "").strip(),
        "tasarimci": ((d.get("creator") or {}).get("name") or "").strip(),
        "lisans": (d.get("license") or "").strip(),
        "url": d.get("public_url") or (f"https://www.thingiverse.com/thing:{kimlik}" if kimlik else ""),
        "aciklama": duz_metin(d.get("description")),
        "gorsel": en_iyi_gorsel(d),
        "begeni": d.get("like_count") or 0,
    }


def ozet_bilgisi(d):
    """Liste kaydından (lisanssız) sade sözlük; yalnızca esin/örnek için."""
    kimlik = d.get("id")
    return {"id": kimlik, "ad": (d.get("name") or "").strip(), "begeni": d.get("like_count") or 0,
            "tasarimci": ((d.get("creator") or {}).get("name") or "").strip(),
            "url": d.get("public_url") or (f"https://www.thingiverse.com/thing:{kimlik}" if kimlik else "")}


if __name__ == "__main__":
    if not hazir():
        raise SystemExit("THINGIVERSE_TOKEN tanımlı değil.")
    for t in populer(10):
        o = ozet_bilgisi(t)
        print(o["id"], o["begeni"], o["ad"])
