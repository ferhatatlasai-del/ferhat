#!/usr/bin/env python3
"""Nöbetçi: otomatik çalışan ajanların bağımlı olduğu anahtarları ve servisleri günlük denetler.

Sessizce bozulmayı önler: Instagram anahtarı süresi dolarsa, YouTube izni iptal olursa, OpenAI anahtarı çalışmazsa
ya da ofis sunucusu yanıt vermezse bildirim gönderir ve panelde kırmızı gösterir.
Sonuç hikaye/saglik.json dosyasına yazılır. Anahtarları hiçbir yere yazdırmaz.
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(os.environ.get("HIKAYE_KOK") or pathlib.Path(__file__).resolve().parent.parent)
IG_API = os.environ.get("IG_API_ADRESI") or "https://graph.facebook.com/v21.0"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
YT_TOKEN = os.environ.get("YT_TOKEN_ADRESI") or "https://oauth2.googleapis.com/token"
SAGLIK = KOK / "hikaye" / "saglik.json"


def iste(istek, sure=30):
    try:
        with urllib.request.urlopen(istek, timeout=sure) as y:
            return y.status, y.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, type(e).__name__


def kontrol_instagram():
    tok, kim = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
    if not (tok and kim):
        return "atlandi", "IG_ACCESS_TOKEN ya da IG_USER_ID tanımlı değil"
    kod, govde = iste(urllib.request.Request(f"{IG_API}/{kim}?" + urllib.parse.urlencode({"fields": "username", "access_token": tok})))
    if kod == 200:
        return "iyi", "Instagram anahtarı çalışıyor"
    try:
        h = json.loads(govde).get("error", {})
        return "sorun", f"Instagram anahtarı reddedildi (kod {h.get('code')}): {str(h.get('message'))[:140]}. Anahtarı yenilemek gerekebilir."
    except Exception:
        return "sorun", f"Instagram yanıtı beklenmedik (HTTP {kod})"


def kontrol_youtube():
    ger = [os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")]
    if not all(ger):
        return "atlandi", "YouTube anahtarları tanımlı değil"
    veri = urllib.parse.urlencode({"client_id": ger[0], "client_secret": ger[1], "refresh_token": ger[2], "grant_type": "refresh_token"}).encode()
    kod, govde = iste(urllib.request.Request(YT_TOKEN, data=veri, method="POST"))
    if kod == 200:
        return "iyi", "YouTube izni çalışıyor"
    try:
        h = json.loads(govde).get("error", "")
        return "sorun", f"YouTube izni reddedildi ({h}). Yeni yenileme anahtarı alman gerekebilir."
    except Exception:
        return "sorun", f"YouTube yanıtı beklenmedik (HTTP {kod})"


def kontrol_openai():
    tok = os.environ.get("OPENAI_API_KEY")
    if not tok:
        return "atlandi", "OPENAI_API_KEY tanımlı değil"
    kod, _ = iste(urllib.request.Request(f"{OPENAI}/models", headers={"Authorization": f"Bearer {tok}"}))
    if kod == 200:
        return "iyi", "OpenAI anahtarı çalışıyor"
    if kod in (401, 403):
        return "sorun", f"OpenAI anahtarı reddedildi (HTTP {kod})"
    return "sorun", f"OpenAI yanıtı beklenmedik (HTTP {kod})"


def kontrol_ofis():
    ofis = os.environ.get("OFIS_ADRES")
    if not ofis:
        return "atlandi", "OFIS_ADRES tanımlı değil"
    kod, govde = iste(urllib.request.Request(ofis.rstrip("/") + "/api/ping"), 45)
    if kod == 200 and '"ok":true' in govde.replace(" ", ""):
        hazir = '"hazir":true' in govde.replace(" ", "")
        return ("iyi", "Ofis sunucusu çalışıyor") if hazir else ("sorun", "Ofis sunucusu çalışıyor ama GITHUB_TOKEN ya da PANEL_SIFRE eksik")
    return "sorun", f"Ofis sunucusu yanıt vermiyor (HTTP {kod})"


def kontrol_kuyruk():
    try:
        ayar = json.loads((KOK / "hikaye" / "ayar.json").read_text(encoding="utf-8"))
    except Exception:
        return "atlandi", "Hikaye ayarı yok"
    planli = sum(1 for y in (KOK / "hikaye" / "kuyruk").glob("h*.json") if json.loads(y.read_text(encoding="utf-8")).get("durum") == "planli")
    if ayar.get("aktif") and planli < ayar.get("gunluk_sayi", 4):
        return "sorun", f"Hikaye kuyruğu azaldı ({planli} planlı hikaye kaldı, günlük {ayar.get('gunluk_sayi', 4)}). Yeni fotoğraf ekle."
    return "iyi", f"Kuyrukta {planli} planlı hikaye var"


def bildir(baslik, govde):
    ofis, sir = os.environ.get("OFIS_ADRES"), os.environ.get("BILDIRIM_SIRRI")
    if not (ofis and sir):
        return
    try:
        istek = urllib.request.Request(ofis.rstrip("/") + "/api/bildir", method="POST", data=json.dumps({"baslik": baslik, "govde": govde, "adres": "/", "etiket": "nobetci"}).encode(),
                                       headers={"Content-Type": "application/json", "X-Bildirim": sir})
        with urllib.request.urlopen(istek, timeout=40):
            print("Bildirim gönderildi.")
    except Exception as e:
        print(f"Bildirim gönderilemedi: {type(e).__name__}")


def main():
    oncekiler = {}
    if SAGLIK.exists():
        try:
            oncekiler = {k["ad"]: k["durum"] for k in json.loads(SAGLIK.read_text(encoding="utf-8")).get("kontroller", [])}
        except Exception:
            pass
    sonuclar = []
    for ad, f in [("Instagram", kontrol_instagram), ("YouTube", kontrol_youtube), ("OpenAI", kontrol_openai), ("Ofis sunucusu", kontrol_ofis), ("Hikaye kuyruğu", kontrol_kuyruk)]:
        d, n = f()
        sonuclar.append({"ad": ad, "durum": d, "not": n})
        print(f"{ad}: {d} - {n}")
    SAGLIK.parent.mkdir(parents=True, exist_ok=True)
    SAGLIK.write_text(json.dumps({"tarih": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kontroller": sonuclar}, ensure_ascii=False, indent=2), encoding="utf-8")
    yeni_sorun = [s for s in sonuclar if s["durum"] == "sorun" and oncekiler.get(s["ad"]) != "sorun"]
    if yeni_sorun:   # aynı sorun için her gün bildirim gönderme
        bildir("Ajanlarda sorun var", "; ".join(f"{s['ad']}: {s['not']}" for s in yeni_sorun)[:240])
    sys.exit(1 if any(s["durum"] == "sorun" for s in sonuclar) else 0)


if __name__ == "__main__":
    main()
