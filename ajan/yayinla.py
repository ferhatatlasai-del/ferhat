#!/usr/bin/env python3
"""Instagram'a Reels yayınlar (Instagram Graph API, Facebook girişi anahtarıyla).

İKİ AŞAMALI ve güvenli:
  - Varsayılan "kontrol modu": videoyu Instagram'a işlettirir, durumu bekler, ama YAYINLAMAZ.
  - Gerçek yayın için --yayinla bayrağı gerekir.

Kullanım:
    IG_ACCESS_TOKEN=... IG_USER_ID=... python3 ajan/yayinla.py --video-url URL --aciklama-dosyasi yayin/x.txt
    ... --yayinla        # gerçekten yayınlar
Video, Instagram'ın indirebileceği herkese açık bir adreste olmalıdır.
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
API = "https://graph.facebook.com/v21.0"


def api(yontem, yol, **parametre):
    parametre["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    govde = urllib.parse.urlencode(parametre)
    if yontem == "GET":
        istek = urllib.request.Request(f"{API}/{yol}?{govde}")
    else:
        istek = urllib.request.Request(f"{API}/{yol}", data=govde.encode(), method="POST")
    with urllib.request.urlopen(istek, timeout=120) as yanit:
        return json.load(yanit)


def hata_ozeti(e):
    """Meta'nın hata kodunu ve mesajını gösterir (anahtarı değil)."""
    try:
        h = json.loads(e.read().decode("utf-8")).get("error", {})
        return f"HTTP {e.code} kod={h.get('code')} alt={h.get('error_subcode')}: {str(h.get('message'))[:260]}"
    except Exception:
        return f"HTTP {e.code}"


def bekle(kapsayici, deneme=30, aralik=10):
    """Instagram videoyu işleyene kadar durumu sorar."""
    son = ""
    for i in range(deneme):
        veri = api("GET", kapsayici, fields="status_code,status")
        kod = veri.get("status_code", "")
        if kod != son:
            print(f"Durum: {kod} {veri.get('status', '')}".strip())
            son = kod
        if kod == "FINISHED":
            return True
        if kod in ("ERROR", "EXPIRED"):
            print(f"Instagram videoyu işleyemedi: {veri.get('status', '')}")
            return False
        time.sleep(aralik)
    print("Zaman aşımı: video hâlâ işleniyor.")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url", required=True, help="Videonun herkese açık adresi")
    ap.add_argument("--aciklama-dosyasi", required=True, help="Açıklama metni dosyası")
    ap.add_argument("--kapak-ms", type=int, default=7000, help="Kapak karesi (milisaniye)")
    ap.add_argument("--yayinla", action="store_true", help="Gerçekten yayınla (yoksa yalnızca kontrol)")
    a = ap.parse_args()

    for gerekli in ("IG_ACCESS_TOKEN", "IG_USER_ID"):
        if not os.environ.get(gerekli):
            sys.exit(f"{gerekli} tanımlı değil.")
    kimlik = os.environ["IG_USER_ID"]
    aciklama = (KOK / a.aciklama_dosyasi).read_text(encoding="utf-8").strip()
    if not aciklama:
        sys.exit("Açıklama dosyası boş.")

    try:
        kap = api("POST", f"{kimlik}/media", media_type="REELS", video_url=a.video_url,
                  caption=aciklama, share_to_feed="true", thumb_offset=str(a.kapak_ms))
        kapsayici = kap["id"]
        print(f"Kapsayıcı oluşturuldu: {kapsayici}")
        if not bekle(kapsayici):
            sys.exit(1)
        if not a.yayinla:
            print("KONTROL MODU: Video Instagram tarafından kabul edildi. YAYINLANMADI.")
            return
        sonuc = api("POST", f"{kimlik}/media_publish", creation_id=kapsayici)
        medya = sonuc["id"]
        print(f"YAYINLANDI. Medya kimliği: {medya}")
        try:
            print("Bağlantı:", api("GET", medya, fields="permalink").get("permalink", "?"))
        except urllib.error.HTTPError:
            pass
    except urllib.error.HTTPError as e:
        print(f"Instagram API hatası: {hata_ozeti(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
