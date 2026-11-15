#!/usr/bin/env python3
"""YouTube'a video yükler (YouTube Data API v3, OAuth yenileme anahtarıyla).

İKİ AŞAMALI ve güvenli:
  - Varsayılan "kontrol modu": yalnızca yetkilendirmenin çalıştığını sınar (anahtar yenileme), YÜKLEMEZ.
  - Gerçek yükleme için --yukle bayrağı gerekir.

Gerekli ortam değişkenleri: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Metin dosyası: ilk satır başlık, boş satırdan sonrası açıklama.

Kullanım:
    python3 ajan/youtube_yukle.py --video videolar/x.mp4 --metin-dosyasi yayin/x.txt
    ... --yukle --gizlilik public
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
TOKEN_ADRESI = "https://oauth2.googleapis.com/token"
YUKLEME_ADRESI = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
ETIKETLER = ["3D baskı", "3D yazıcı", "3d printing", "Doktor Filament", "yapay zeka"]


def http(yontem, url, basliklar=None, veri=None, zaman=600):
    istek = urllib.request.Request(url, data=veri, method=yontem, headers=basliklar or {})
    try:
        with urllib.request.urlopen(istek, timeout=zaman) as y:
            return y.status, y.headers, y.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def json_oku(govde):
    try:
        return json.loads(govde or b"{}")
    except ValueError:
        return {}


def erisim_anahtari():
    """Yenileme anahtarından kısa ömürlü erişim anahtarı alır. Gizli değerleri asla yazdırmaz."""
    durum, _, govde = http("POST", TOKEN_ADRESI, {"Content-Type": "application/x-www-form-urlencoded"},
                           urllib.parse.urlencode({
                               "client_id": os.environ["YT_CLIENT_ID"],
                               "client_secret": os.environ["YT_CLIENT_SECRET"],
                               "refresh_token": os.environ["YT_REFRESH_TOKEN"],
                               "grant_type": "refresh_token",
                           }).encode())
    veri = json_oku(govde)
    if durum != 200 or "access_token" not in veri:
        ipucu = ""
        if veri.get("error") == "invalid_grant":
            ipucu = " (yenileme anahtarı geçersiz ya da süresi dolmuş; OAuth Playground'dan yenisini al)"
        elif veri.get("error") == "invalid_client":
            ipucu = " (Client ID ya da Client secret yanlış)"
        print(f"Yetkilendirme başarısız: HTTP {durum} {veri.get('error', '')} {str(veri.get('error_description', ''))[:160]}{ipucu}")
        sys.exit(1)
    return veri["access_token"]


def metni_oku(yol):
    satirlar = (KOK / yol).read_text(encoding="utf-8").strip().splitlines()
    baslik = satirlar[0].strip().replace("<", "").replace(">", "")[:100]
    aciklama = "\n".join(satirlar[1:]).strip().replace("<", "").replace(">", "")[:4900]
    if not baslik:
        sys.exit("Başlık boş.")
    return baslik, aciklama


def yukle(erisim, video, baslik, aciklama, gizlilik):
    boyut = video.stat().st_size
    metadata = {
        "snippet": {"title": baslik, "description": aciklama, "categoryId": "28", "tags": ETIKETLER},
        "status": {"privacyStatus": gizlilik, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    basliklar = {"Authorization": f"Bearer {erisim}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(boyut), "X-Upload-Content-Type": "video/mp4"}
    durum, bas, govde = http("POST", YUKLEME_ADRESI, basliklar, json.dumps(metadata).encode("utf-8"))
    if durum == 400 and "containsSyntheticMedia" in govde.decode("utf-8", "ignore"):
        print("UYARI: API 'containsSyntheticMedia' alanını kabul etmedi; alansız yeniden deneniyor. "
              "YouTube Studio'da 'değiştirilmiş/sentetik içerik' beyanını elle işaretle.")
        del metadata["status"]["containsSyntheticMedia"]
        durum, bas, govde = http("POST", YUKLEME_ADRESI, basliklar, json.dumps(metadata).encode("utf-8"))
    if durum != 200 or not bas.get("Location"):
        hata = json_oku(govde).get("error", {})
        print(f"Yükleme başlatılamadı: HTTP {durum} {str(hata.get('message', ''))[:240]}")
        sys.exit(1)
    durum, _, govde = http("PUT", bas["Location"], {"Content-Type": "video/mp4", "Content-Length": str(boyut)}, video.read_bytes())
    veri = json_oku(govde)
    if durum not in (200, 201) or "id" not in veri:
        hata = veri.get("error", {})
        print(f"Video gönderilemedi: HTTP {durum} {str(hata.get('message', ''))[:240]}")
        sys.exit(1)
    return veri


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--metin-dosyasi", required=True)
    ap.add_argument("--gizlilik", default="public", choices=["public", "unlisted", "private"])
    ap.add_argument("--yukle", action="store_true", help="Gerçekten yükle (yoksa yalnızca kontrol)")
    a = ap.parse_args()

    for gerekli in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.environ.get(gerekli):
            sys.exit(f"{gerekli} tanımlı değil (GitHub'da gizli anahtar olarak eklenmeli).")
    video = KOK / a.video
    if not video.exists():
        sys.exit(f"Video bulunamadı: {a.video}")
    baslik, aciklama = metni_oku(a.metin_dosyasi)

    erisim = erisim_anahtari()
    print("Yetkilendirme çalışıyor (erişim anahtarı alındı).")
    if not a.yukle:
        print(f"KONTROL MODU: '{baslik}' ({video.stat().st_size // 1024} KB) yüklenmeye hazır. YÜKLENMEDİ.")
        return
    veri = yukle(erisim, video, baslik, aciklama, a.gizlilik)
    gercek = (veri.get("status") or {}).get("privacyStatus", "?")
    print(f"YÜKLENDİ. Video kimliği: {veri['id']}")
    print(f"Bağlantı: https://www.youtube.com/shorts/{veri['id']}")
    print(f"İstenen gizlilik: {a.gizlilik}, gerçek gizlilik: {gercek}")
    if gercek != a.gizlilik:
        print("UYARI: YouTube gizliliği değiştirdi (örneğin denetimden geçmemiş API projesi videoyu özel yapabilir). "
              "YouTube Studio'dan videoyu elle herkese açık yap.")


if __name__ == "__main__":
    main()
