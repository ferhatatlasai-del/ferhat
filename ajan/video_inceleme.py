#!/usr/bin/env python3
"""Video inceleme: yönetici ajanın bir videoyu "izlemesi". Videodan kareler (kontak sayfaları) + anlatı metni + teknik ölçümler bir modele (Claude ya da OpenAI)
gösterilir; model yönergeye ve bilgi tabanına (yonetici/bilgi.md) göre yayınla/reddet kararı verir. Ses duyulmaz: anlatı metni ve zamanlama bilgisi verilir.
Kararı kod da denetler: teknik sorun (süre, ses yok, siyah kare) ya da puan < 7 ise model "yayınla" dese bile REDDEDİLİR."""
import base64
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
ANTHROPIC = os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
import yz_model as YZ  # noqa: E402
OPENAI_MODEL = YZ.model("yonetici", "gpt-5.4-mini")
CLAUDE_MODEL = os.environ.get("YONETICI_MODEL") or "claude-sonnet-5-5"


def sh(komut, **k):
    return subprocess.run(komut, capture_output=True, text=True, **k)


def teknik_kontrol(video):
    """(sorunlar, ölçümler): süre, çözünürlük, ses düzeyi, siyah kare, dosya boyutu."""
    sorunlar, o = [], {}
    p = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height", "-of", "json", str(video)])
    try:
        j = json.loads(p.stdout)
        o["sure"] = float(j["format"]["duration"])
        o["boyut_mb"] = round(int(j["format"]["size"]) / 1e6, 1)
        v = [s for s in j["streams"] if s.get("codec_type") == "video"]
        o["ses_izi"] = any(s.get("codec_type") == "audio" for s in j["streams"])
        o["cozunurluk"] = f"{v[0]['width']}x{v[0]['height']}" if v else "?"
    except Exception:
        return ["video okunamadı (ffprobe)"], o
    if not 25 <= o["sure"] <= 95:
        sorunlar.append(f"süre {o['sure']:.0f} sn (25-95 beklenir)")
    if not o["ses_izi"]:
        sorunlar.append("ses izi yok")
    else:
        v = sh(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "volumedetect", "-vn", "-f", "null", "-"])
        m = re.search(r"mean_volume: (-?[\d.]+) dB", v.stderr or "")
        if m:
            o["ortalama_ses_db"] = float(m.group(1))
            if o["ortalama_ses_db"] < -40:
                sorunlar.append(f"ses çok düşük/sessiz ({o['ortalama_ses_db']} dB)")
    b = sh(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=1.5:pix_th=0.04", "-an", "-f", "null", "-"])
    uzun = re.findall(r"black_duration:([\d.]+)", b.stderr or "")
    if uzun:
        sorunlar.append(f"{len(uzun)} yerde 1,5 sn'den uzun siyah ekran")
    if o["boyut_mb"] > 95:
        sorunlar.append(f"dosya çok büyük ({o['boyut_mb']} MB)")
    return sorunlar, o


def kareler(video, dizin, sure, parca=2, kare_basina=6):
    """Videoyu eşit aralıklı karelere bölüp 'parca' adet kontak sayfası (3x2) üretir; yollarını döndürür."""
    toplam = parca * kare_basina
    yollar = []
    for k in range(parca):
        liste = [round((k * kare_basina + i + 0.5) / toplam * sure, 2) for i in range(kare_basina)]
        ara = []
        for j, t in enumerate(liste):
            y = pathlib.Path(dizin) / f"k{k}_{j}.jpg"
            sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=360:-1", "-q:v", "4", str(y)])
            if y.exists():
                ara.append(y)
        if not ara:
            continue
        cikis = pathlib.Path(dizin) / f"sayfa{k}.jpg"
        girdi = sum([["-i", str(a)] for a in ara], [])
        sh(["ffmpeg", "-y", "-loglevel", "error", *girdi, "-filter_complex", f"xstack=inputs={len(ara)}:layout=" + "|".join(f"{(i % 3) * 360}_{(i // 3) * 640}" for i in range(len(ara))), "-frames:v", "1", str(cikis)])
        if cikis.exists():
            yollar.append((cikis, liste[:len(ara)]))
    return yollar


def model_sor(sistem, kullanici, gorseller):
    anth = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    b64 = [base64.b64encode(pathlib.Path(g).read_bytes()).decode() for g in gorseller]
    if anth:
        icerik = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": d}} for d in b64] + [{"type": "text", "text": kullanici}]
        govde = {"model": CLAUDE_MODEL, "max_tokens": 1500, "system": sistem, "messages": [{"role": "user", "content": icerik}]}
        r = urllib.request.Request(f"{ANTHROPIC}/v1/messages", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json", "x-api-key": anth, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(r, timeout=180) as y:
            metin = "".join(x.get("text", "") for x in json.load(y).get("content", []) if x.get("type") == "text")
        kaynak = f"Claude ({CLAUDE_MODEL})"
    else:
        anahtar = os.environ.get("OPENAI_API_KEY")
        if not anahtar:
            raise RuntimeError("ne ANTHROPIC_API_KEY ne OPENAI_API_KEY tanımlı")
        icerik = [{"type": "text", "text": kullanici}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + d}} for d in b64]
        govde = {"model": OPENAI_MODEL, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": icerik}]}
        r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
        with urllib.request.urlopen(r, timeout=180) as y:
            metin = json.load(y)["choices"][0]["message"]["content"]
        kaynak = f"OpenAI ({OPENAI_MODEL})"
    m = re.search(r"\{.*\}", metin, re.S)
    return json.loads(m.group(0)), kaynak


SISTEM = """Sen "Yönetici" ajansın ve yayına gidecek bir 3D baskı eğitim videosunu İZLİYORSUN (kareler + anlatı metni). Sahibinin yönergesi ve bilgi tabanı aşağıda. Videoyu YAYINLAMA ya da REDDETME kararını sen verirsin; şüphede REDDET (yanlış bilgi ya da bozuk video yayınlamaktan iyidir).
Sesi duyamazsın; anlatı metni ve zamanlama verilir. Kareler 3x2 kontak sayfalarıdır (soldan sağa, yukarıdan aşağı, zaman sırasıyla).
Değerlendir: teknik doğruluk (bilgi tabanındaki aralıklar ve genel bilginle), anlatı-görüntü uyumu, sahne bozukluğu/boşluk, yazı okunurluğu, tekrar, abartı/uydurma, yönergeye uygunluk.
Yalnızca JSON: {"karar": "yayinla" | "reddet", "puan": 1-10, "sorunlar": ["kısa, somut sorun", ...], "gerekce": "tek cümle", "kontrol_edilen_iddialar": ["videodaki sayısal/teknik iddia → doğru/şüpheli/yanlış", ...]}"""


def incele(video, bilgi, yonerge="", bilgi_tabani="", onceki_noktalar=()):
    """bilgi: {baslik, aciklama, anlati, sahneler, noktalar, konu}. Dönen: {karar, puan, sorunlar, gerekce, model, teknik, olcum}"""
    sorunlar_t, olcum = teknik_kontrol(video)
    sonuc = {"teknik": sorunlar_t, "olcum": olcum}
    with tempfile.TemporaryDirectory() as g:
        sayfalar = kareler(video, g, olcum.get("sure") or 50)
        if not sayfalar:
            return {**sonuc, "karar": "reddet", "puan": 0, "sorunlar": ["videodan kare alınamadı"] + sorunlar_t, "gerekce": "video işlenemedi", "model": "-"}
        kullanici = ("SAHİBİNİN YÖNERGESİ:\n" + (yonerge or "(yok)")[:3500] + "\n\nBİLGİ TABANI:\n" + (bilgi_tabani or "(yok)")[:5000] +
                     "\n\nVİDEO: " + str(bilgi.get("baslik")) + "\nKonu: " + str(bilgi.get("konu")) + "\nSüre: " + f"{olcum.get('sure', 0):.0f} sn" + "\nSahne tipleri (sırayla): " + ", ".join(bilgi.get("sahneler") or []) +
                     "\n\nANLATI METNİ:\n" + str(bilgi.get("anlati"))[:2200] + "\n\nAÇIKLAMA:\n" + str(bilgi.get("aciklama"))[:700] +
                     "\n\nBu videonun noktaları: " + "; ".join(bilgi.get("noktalar") or []) + "\nÖnceki videolarda anlatılan noktalar (tekrar mı?): " + "; ".join(list(onceki_noktalar)[-25:]) +
                     "\n\nTEKNİK ÖLÇÜMLER: " + json.dumps(olcum, ensure_ascii=False) + ("\nTEKNİK SORUNLAR: " + "; ".join(sorunlar_t) if sorunlar_t else "") +
                     "\n\nKareler zamanları (sn): " + " | ".join(", ".join(str(t) for t in ts) for _, ts in sayfalar))
        j, kaynak = model_sor(SISTEM, kullanici, [s for s, _ in sayfalar])
    try:
        puan = max(0.0, min(10.0, float(j.get("puan"))))
    except (TypeError, ValueError):
        puan = 0.0
    karar = "yayinla" if (j.get("karar") == "yayinla" and puan >= 7 and not sorunlar_t) else "reddet"
    sorunlar = [str(x)[:200] for x in (j.get("sorunlar") or [])][:8] + [f"teknik: {x}" for x in sorunlar_t]
    return {**sonuc, "karar": karar, "puan": puan, "sorunlar": sorunlar, "gerekce": str(j.get("gerekce") or "")[:300], "iddialar": [str(x)[:160] for x in (j.get("kontrol_edilen_iddialar") or [])][:8], "model": kaynak}
