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
import re
import subprocess
import sys
import tempfile
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


SHORT_EN_FAZLA_SN = 180   # YouTube Shorts üst sınırı (3 dakika)


def video_bilgisi(video):
    """(genislik, yukseklik, sure_sn, kodek) ya da None (ffprobe yoksa/okunamazsa). Telefon dönüklüğü hesaba katılır."""
    try:
        c = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,codec_name:stream_tags=rotate:stream_side_data=rotation:format=duration",
                            "-of", "json", str(video)], capture_output=True, text=True, timeout=60)
        v = json.loads(c.stdout or "{}")
        st = (v.get("streams") or [{}])[0]
        g, y = int(st["width"]), int(st["height"])
        dondur = 0
        for sd in st.get("side_data_list") or []:
            if "rotation" in sd:
                dondur = int(sd["rotation"])
        dondur = dondur or int((st.get("tags") or {}).get("rotate", 0) or 0)
        if abs(dondur) % 180 == 90:
            g, y = y, g
        return g, y, float((v.get("format") or {}).get("duration") or 0), st.get("codec_name", "?")
    except Exception:
        return None


def siyah_kenar_kirp(video, g, y):
    """Videonun kendi içindeki siyah şeritleri (letterbox) bulur; belirgin biçimde varsa 'crop=...' filtresini döndürür."""
    try:
        c = subprocess.run(["ffmpeg", "-v", "info", "-ss", "1", "-t", "6", "-i", str(video), "-vf", "cropdetect=24:2:0", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
        bulunan = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", c.stderr or "")
        if not bulunan:
            return ""
        sayac = {}
        for t in bulunan:
            sayac[t] = sayac.get(t, 0) + 1
        en_sik = max(sayac, key=lambda k: (sayac[k], -int(k[0]) * int(k[1])))   # çoğunlukla ölçülen kırpma (parlak sahnelerdeki tam kare ölçümü yanıltmasın)
        w, h, x, yy = (int(v) for v in en_sik)
        w, h = w - w % 2, h - h % 2
        if w < g * 0.5 or h < y * 0.5:   # ölçüm güvenilmez (neredeyse tamamen karanlık video vb.)
            return ""
        if (g * y - w * h) / (g * y) < 0.04:   # kayda değer siyah şerit yok
            return ""
        return f"crop={w}:{h}:{x}:{yy}"
    except Exception:
        return ""


def dikey_hazirla(video, klasor):
    """YouTube bir videoyu yalnızca kare ya da dikey (9:16) ve en çok 3 dk ise Short sayar; '#Shorts' yazısı tek başına yetmez.
    Yatay (ör. 4:3 ya da 16:9) video, bulanık arka planlı 1080x1920 dikey videoya çevrilir. Zaten dikey/kare ise olduğu gibi gönderilir."""
    b = video_bilgisi(video)
    if not b:
        print("UYARI: video bilgisi okunamadı (ffprobe yok olabilir); video olduğu gibi gönderilecek.")
        return video
    g, y, sure, kodek = b
    print(f"Video: {g}x{y}, {sure:.0f} sn, {kodek}")
    if sure > SHORT_EN_FAZLA_SN:
        print(f"UYARI: video {SHORT_EN_FAZLA_SN} sn'den uzun; YouTube bunu Short saymaz, normal video olarak yüklenecek.")
        return video
    if y >= g:
        print("Video kare ya da dikey: Short olarak sayılır, olduğu gibi gönderilecek.")
        return video
    cikis = pathlib.Path(klasor) / "short_dikey.mp4"
    print("Video yatay: YouTube Short saymaz. Bulanık arka planlı 1080x1920 dikey videoya çevriliyor…")
    kirp = siyah_kenar_kirp(video, g, y)
    if kirp:
        print(f"Siyah kenarlar kırpılıyor: {kirp}")
    on = (kirp + ",") if kirp else ""
    filtre = (f"[0:v]{on}split[a][b];"
              "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:6[bg];"
              "[b]scale=1080:-2:force_original_aspect_ratio=decrease[on];"
              "[bg][on]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    c = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-filter_complex", filtre, "-map", "[v]", "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", "30", "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart", str(cikis)], capture_output=True, text=True, timeout=900)
    if c.returncode != 0 or not cikis.exists() or cikis.stat().st_size < 1024:
        print("UYARI: dikeye çevirme başarısız (" + (c.stderr or "")[-200:].strip() + "); video olduğu gibi gönderilecek.")
        return video
    ny = video_bilgisi(cikis)
    print(f"Dönüştürüldü: {ny[0]}x{ny[1]}, {cikis.stat().st_size // 1024} KB" if ny else "Dönüştürüldü.")
    return cikis


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
        b = video_bilgisi(video)
        if b:
            print(f"Video: {b[0]}x{b[1]}, {b[2]:.0f} sn. " + ("Short sayılır." if b[1] >= b[0] and b[2] <= SHORT_EN_FAZLA_SN else "Yatay/uzun: yüklemede dikeye çevrilecek (3 dk üstü çevrilmez)."))
        print(f"KONTROL MODU: '{baslik}' ({video.stat().st_size // 1024} KB) yüklenmeye hazır. YÜKLENMEDİ.")
        return
    with tempfile.TemporaryDirectory() as gecici:
        gonderilecek = dikey_hazirla(video, gecici)
        veri = yukle(erisim, gonderilecek, baslik, aciklama, a.gizlilik)
    gercek = (veri.get("status") or {}).get("privacyStatus", "?")
    print(f"YÜKLENDİ. Video kimliği: {veri['id']}")
    print(f"Bağlantı: https://www.youtube.com/shorts/{veri['id']}")
    print(f"İstenen gizlilik: {a.gizlilik}, gerçek gizlilik: {gercek}")
    if gercek != a.gizlilik:
        print("UYARI: YouTube gizliliği değiştirdi (örneğin denetimden geçmemiş API projesi videoyu özel yapabilir). "
              "YouTube Studio'dan videoyu elle herkese açık yap.")


if __name__ == "__main__":
    main()
