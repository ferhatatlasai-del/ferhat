"""Instagram bağlantı ayarını anahtarın türüne göre belirler (tüm betikler ortak kullanır).

İki tür anahtar desteklenir:
  - Instagram girişli anahtar (Instagram API with Instagram Login): adres graph.instagram.com, hesap "me".
  - Facebook girişli anahtar (sayfa üzerinden): adres graph.facebook.com, hesap IG_USER_ID.

Anahtar türü, graph.instagram.com/me çağrısı kabul edilirse Instagram girişli sayılır; aksi hâlde Facebook girişli varsayılır
(eski davranış). IG_API_ADRESI tanımlıysa doğrudan o adres ve IG_USER_ID kullanılır (testler için).
Anahtar hiçbir yere yazılmaz.
"""
import json
import os
import urllib.parse
import urllib.request

FACEBOOK = "https://graph.facebook.com/v21.0"
INSTAGRAM = os.environ.get("IG_INSTAGRAM_ADRESI") or "https://graph.instagram.com/v21.0"
_onbellek = {}


def _belirle():
    ozel = os.environ.get("IG_API_ADRESI")
    if ozel:
        return ozel, os.environ.get("IG_USER_ID") or "me", "elle"
    tok = os.environ.get("IG_ACCESS_TOKEN")
    if tok:
        try:
            adres = f"{INSTAGRAM}/me?" + urllib.parse.urlencode({"fields": "user_id,username", "access_token": tok})
            with urllib.request.urlopen(urllib.request.Request(adres), timeout=30) as y:
                if y.status == 200 and json.load(y):
                    return INSTAGRAM, "me", "instagram"
        except Exception:
            pass
    return FACEBOOK, os.environ.get("IG_USER_ID"), "facebook"


def baglanti():
    """(api_adresi, hesap_kimligi, tur). Süreç boyunca bir kez belirlenir."""
    if not _onbellek:
        _onbellek["b"] = _belirle()
        print(f"Instagram bağlantısı: {_onbellek['b'][2]} girişli anahtar ({_onbellek['b'][0].split('//')[1].split('/')[0]})")
    return _onbellek["b"]


def api_adresi():
    return baglanti()[0]


def kimlik():
    return baglanti()[1]
