#!/usr/bin/env python3
"""Carousel taslağından YouTube Shorts videosu üretir (slayt gösterisi + yapay zekâ sesi).

Girdi : taslaklar/<tarih>.md  (içerik ajanının carousel taslağı)
        gorseller/<taslak adı>/slayt1.png ... slayt7.png  (Gemini'de ürettiğin görseller)
        ya da --gorsel-uret ile OpenAI'dan üretilir (görsel başına küçük bir tutar)
Çıktı : videolar/<taslak adı>_shorts.mp4  (1080x1920, dikey)
        yayin/<taslak adı>_youtube.txt    (1. satır başlık, gerisi açıklama; youtube_yukle.py bunu okur)

Ses her slaytın yazısını okur. Videoda ve açıklamada sesin yapay zekâ olduğu yazılır.
Hiçbir şey yayınlanmaz; yalnızca dosya üretilir.
"""
import argparse
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
FONT_ADAYLARI = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
UZANTILAR = ("png", "jpg", "jpeg", "webp")
SES_NOTU = "🤖 Anlatım sesi yapay zekâ ile üretilmiştir."
SES_TALIMATI = (
    "Türkçe konuş. Genç, sıcak, meraklı ve enerjik bir anlatıcı gibi, doğal ve akıcı. "
    "Çok yavaş ya da robot gibi okuma; kısa cümlelerde net dur, sonda hafif vurgu yap."
)
GENISLIK, YUKSEKLIK, FPS = 1080, 1920, 30
SESSIZLIK_SN = 0.35


def hata(m):
    print(f"HATA: {m}", file=sys.stderr)
    sys.exit(1)


# ---------- Taslağı oku ----------

def bolum(metin, baslik):
    m = re.search(rf"^## {re.escape(baslik)}[^\n]*\n(.*?)(?=^## |\Z)", metin, re.S | re.M)
    return m.group(1).strip() if m else ""


def taslak_oku(yol):
    metin = pathlib.Path(yol).read_text(encoding="utf-8")
    if "- **Format:** carousel" not in metin:
        hata("Bu araç yalnızca carousel taslakları içindir (bu taslak video planı).")
    baslik = (re.search(r"^# (.+)$", metin, re.M) or [None, ""])[1].strip()
    slaytlar = re.findall(
        r"### Slayt (\d+): [^\n]*\n- \*\*Slayt metni:\*\* (.+)\n- \*\*Gemini promptu:\*\* (.+)", metin)
    if not slaytlar:
        hata("Taslakta slayt bulunamadı.")
    slaytlar = [{"no": int(n), "metin": t.strip(), "prompt": p.strip()} for n, t, p in slaytlar]

    yt = bolum(metin, "YouTube Shorts")
    yt_baslik = (re.search(r"\*\*Başlık:\*\*\s*(.+)", yt) or [None, baslik])[1].strip()
    yt_aciklama = "\n".join(
        s for s in yt.splitlines() if s.strip() and not s.startswith(("Not:", "**Başlık:**"))).strip()
    ig = bolum(metin, "Instagram caption")
    etiketler = " ".join(t for s in ig.splitlines() if s.startswith("#") for t in s.split())
    return {"baslik": baslik, "slaytlar": slaytlar, "yt_baslik": yt_baslik,
            "yt_aciklama": yt_aciklama, "etiketler": etiketler}


# ---------- OpenAI ----------

def openai_istek(url, govde, anahtar, ikili=False):
    istek = urllib.request.Request(
        url, data=json.dumps(govde).encode(), method="POST",
        headers={"Authorization": f"Bearer {anahtar}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(istek, timeout=180) as r:
            veri = r.read()
            return veri if ikili else json.loads(veri)
    except urllib.error.HTTPError as e:
        ayrinti = e.read().decode("utf-8", "ignore")
        try:
            ayrinti = json.loads(ayrinti)["error"]["message"]
        except Exception:
            ayrinti = ayrinti[:200]
        hata(f"OpenAI isteği reddedildi ({e.code}): {ayrinti}")


def ses_uret(metin, cikti, ses, anahtar):
    modeller = [m for m in [os.environ.get("OPENAI_TTS_MODEL"), "gpt-4o-mini-tts", "tts-1"] if m]
    for model in dict.fromkeys(modeller):
        govde = {"model": model, "voice": ses, "input": metin, "response_format": "mp3"}
        if model.startswith("gpt-4o"):
            govde["instructions"] = SES_TALIMATI
        istek = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech", data=json.dumps(govde).encode(), method="POST",
            headers={"Authorization": f"Bearer {anahtar}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(istek, timeout=180) as r:
                cikti.write_bytes(r.read())
            return model
        except urllib.error.HTTPError as e:
            ayrinti = e.read().decode("utf-8", "ignore")[:200]
            print(f"Ses modeli {model} olmadı ({e.code}): {ayrinti}")
    hata("Hiçbir ses modeli çalışmadı.")


def gorsel_uret(prompt, cikti, anahtar):
    model = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"
    kalite = os.environ.get("OPENAI_IMAGE_QUALITY") or "medium"
    j = openai_istek("https://api.openai.com/v1/images/generations",
                     {"model": model, "prompt": prompt, "size": "1024x1536", "quality": kalite, "n": 1}, anahtar)
    b64 = j["data"][0].get("b64_json")
    if not b64:
        hata("Görsel yanıtında veri yok.")
    cikti.write_bytes(base64.b64decode(b64))


# ---------- ffmpeg ----------

def calistir(komut):
    r = subprocess.run(komut, capture_output=True, text=True)
    if r.returncode != 0:
        hata("ffmpeg/ffprobe hatası:\n" + r.stderr[-1500:])
    return r.stdout


def sure_olc(dosya):
    return float(calistir(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "default=nw=1:nk=1", str(dosya)]).strip())


def sar(metin, genislik=20):
    """Metni satırlara böler (kelime ortasından bölmez)."""
    satirlar, mevcut = [], ""
    for k in metin.split():
        if mevcut and len(mevcut) + 1 + len(k) > genislik:
            satirlar.append(mevcut)
            mevcut = k
        else:
            mevcut = (mevcut + " " + k).strip()
    if mevcut:
        satirlar.append(mevcut)
    return "\n".join(satirlar)


def font_bul():
    for f in FONT_ADAYLARI:
        if pathlib.Path(f).exists():
            return f
    cikti = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"], capture_output=True, text=True).stdout
    if cikti and pathlib.Path(cikti).exists():
        return cikti
    hata("DejaVu Sans Bold yazı tipi bulunamadı (fonts-dejavu-core kurulu olmalı).")


def slayt_klibi(gorsel, ses, metin, sure, cikti, font, gecici):
    kare = max(1, int(round(sure * FPS)))
    metin_dosyasi = gecici / f"{cikti.stem}.txt"
    metin_dosyasi.write_text(sar(metin), encoding="utf-8")
    zoom = f"min(zoom+0.0006,1.10)"
    filtre = (
        f"[0:v]split[a][b];"
        f"[a]scale={GENISLIK}:{YUKSEKLIK}:force_original_aspect_ratio=increase,crop={GENISLIK}:{YUKSEKLIK},"
        f"boxblur=30:6,eq=brightness=-0.18[bg];"
        f"[b]scale=2160:-2,zoompan=z='{zoom}':d={kare}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={GENISLIK}x1350:fps={FPS}[fg];"
        f"[bg][fg]overlay=(W-w)/2:140[v0];"
        f"[v0]drawtext=fontfile={font}:textfile={metin_dosyasi}:fontsize=62:fontcolor=white:"
        f"line_spacing=14:box=1:boxcolor=black@0.6:boxborderw=30:x=(w-text_w)/2:y=1530,format=yuv420p[v]"
    )
    calistir([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(gorsel), "-i", str(ses),
        "-filter_complex", filtre, "-map", "[v]", "-map", "1:a",
        "-af", f"apad=pad_dur={SESSIZLIK_SN}", "-t", f"{sure:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", str(cikti),
    ])


def birlestir(klipler, cikti, gecici):
    liste = gecici / "liste.txt"
    liste.write_text("".join(f"file '{k}'\n" for k in klipler), encoding="utf-8")
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste),
              "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k",
              "-movflags", "+faststart", str(cikti)])


def gorsel_bul(klasor, no):
    for ad in (f"slayt{no}", f"{no}"):
        for uz in UZANTILAR:
            yol = klasor / f"{ad}.{uz}"
            if yol.exists():
                return yol
    return None


def sahte_ses(metin, cikti):
    sn = max(1.8, 0.33 * len(metin.split()))
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={sn:.2f}",
              "-c:a", "libmp3lame", str(cikti)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taslak", required=True, help="taslaklar/....md")
    ap.add_argument("--gorseller", help="Slayt görsellerinin klasörü (varsayılan: gorseller/<taslak adı>)")
    ap.add_argument("--gorsel-uret", action="store_true", help="Eksik görselleri OpenAI ile üret (ücretli)")
    ap.add_argument("--ses", default="ash", help="OpenAI ses adı (ash, coral, onyx, nova...)")
    ap.add_argument("--sahte-ses", action="store_true", help="Yalnızca deneme: gerçek ses yerine bip")
    args = ap.parse_args()

    taslak_yolu = (KOK / args.taslak) if not pathlib.Path(args.taslak).is_absolute() else pathlib.Path(args.taslak)
    if not taslak_yolu.exists():
        hata(f"Taslak bulunamadı: {args.taslak}")
    ad = taslak_yolu.stem
    t = taslak_oku(taslak_yolu)
    klasor = pathlib.Path(args.gorseller) if args.gorseller else KOK / "gorseller" / ad
    klasor = klasor if klasor.is_absolute() else KOK / klasor
    anahtar = os.environ.get("OPENAI_API_KEY", "")

    # Görselleri hazırla
    klasor.mkdir(parents=True, exist_ok=True)
    eksik = [s for s in t["slaytlar"] if not gorsel_bul(klasor, s["no"])]
    if eksik and args.gorsel_uret:
        if not anahtar:
            hata("OPENAI_API_KEY yok; görsel üretilemez.")
        for s in eksik:
            print(f"Görsel üretiliyor: slayt {s['no']}")
            gorsel_uret(s["prompt"], klasor / f"slayt{s['no']}.png", anahtar)
        eksik = []
    if eksik:
        beklenen = ", ".join(f"slayt{s['no']}.png" for s in eksik)
        hata(f"Eksik görsel: {beklenen}. Bunları {klasor.relative_to(KOK)}/ klasörüne koy "
             "ya da --gorsel-uret ile üret.")

    if not args.sahte_ses and not anahtar:
        hata("OPENAI_API_KEY yok; ses üretilemez.")
    font = font_bul()

    cikti_video = KOK / "videolar" / f"{ad}_shorts.mp4"
    cikti_video.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as g:
        gecici = pathlib.Path(g)
        klipler, toplam = [], 0.0
        for s in t["slaytlar"]:
            ses_dosyasi = gecici / f"ses{s['no']}.mp3"
            if args.sahte_ses:
                sahte_ses(s["metin"], ses_dosyasi)
            else:
                ses_uret(s["metin"], ses_dosyasi, args.ses, anahtar)
            sure = sure_olc(ses_dosyasi) + SESSIZLIK_SN
            klip = gecici / f"klip{s['no']:02d}.mp4"
            slayt_klibi(gorsel_bul(klasor, s["no"]), ses_dosyasi, s["metin"], sure, klip, font, gecici)
            klipler.append(klip)
            toplam += sure
            print(f"Slayt {s['no']}: {sure:.1f} sn")
        birlestir(klipler, cikti_video, gecici)

    sure = sure_olc(cikti_video)
    if sure > 175:
        print(f"UYARI: video {sure:.0f} sn; Shorts için en fazla 3 dakika olmalı.")

    # YouTube metni
    etiketler = "#Shorts " + t["etiketler"]
    aciklama = "\n".join([t["yt_aciklama"].strip(), SES_NOTU, "", etiketler.strip()]).strip()
    # Doktor Filament satırı yinelenmesin
    satirlar, goruldu = [], set()
    for s in aciklama.splitlines():
        if s.strip() and s in goruldu:
            continue
        goruldu.add(s)
        satirlar.append(s)
    yt_dosyasi = KOK / "yayin" / f"{ad}_youtube.txt"
    yt_dosyasi.parent.mkdir(exist_ok=True)
    yt_dosyasi.write_text(t["yt_baslik"][:100] + "\n" + "\n".join(satirlar) + "\n", encoding="utf-8")

    print(f"Video hazır: {cikti_video.relative_to(KOK)} ({sure:.1f} sn, {cikti_video.stat().st_size // 1024} KB)")
    print(f"YouTube metni: {yt_dosyasi.relative_to(KOK)}")
    print("Hiçbir şey yayınlanmadı.")


if __name__ == "__main__":
    main()
