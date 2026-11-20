#!/usr/bin/env python3
"""Viral kısa video üreticisi (Shorts / Reels): 3D animasyonlu, Türkçe seslendirmeli, alt yazılı, ~60 sn dikey videolar.

Akış (hepsi depoda, ek hizmet gerekmez):
  1. Senaryo: `video/senaryolar/*.json` kütüphanesi ya da yapay zekâ (OPENAI_API_KEY) ile merak uyandıran bilgi senaryosu.
  2. Seslendirme: Google Cloud Text-to-Speech (GOOGLE_TTS_API_KEY; kelime zamanları SSML işaretleriyle) ya da kart gerektirmeyen Gemini TTS (GEMINI_API_KEY; zamanlar duraklamalardan çıkarılır).
  3. Zaman çizelgesi: sahne süreleri konuşmaya göre belirlenir, alt yazı kelime kelime vurgulanır.
  4. 3D çizim: video/render.js (Chromium + three.js) kareleri çizer, ffmpeg'e aktarır.
  5. Ses tasarımı: ajan/ses_tasarim.py müzik, geçiş/vurgu efektleri ve atmosferi kodla sentezler; konuşma varken müzik kısılır; −14 LUFS.
  6. Taslak: `shorts/s*.json` (durum "onay_bekliyor") + `videolar/yukleme_*.mp4`. YAYINLAMAZ; panelden onaylanınca mevcut YouTube/Instagram akışı yayınlar.

Kullanım:
    python3 ajan/viral_video.py [--konu "..."] [--senaryo dosya.json] [--hemen] [--git] [--olcek 1] [--cikti video.mp4]
"""
import argparse
import base64
import datetime
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from xml.sax.saxutils import escape

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402
import hikaye_uret as U  # noqa: E402
import ses_tasarim as SES  # noqa: E402

KOK = H.KOK
VIDEO = KOK / "video"
SENARYOLAR = VIDEO / "senaryolar"
DIZIN = KOK / "shorts"
AYAR = DIZIN / "viral_ayar.json"
KULLANILAN = DIZIN / "viral_kullanilan.json"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
TTS_ADRES = os.environ.get("TTS_ADRES") or "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
GEMINI_ADRES = os.environ.get("GEMINI_ADRES") or "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = os.environ.get("GEMINI_TTS_MODEL") or "gemini-2.5-flash-preview-tts"
VARSAYILAN = {"gemini_ses": "Orus", "aktif": True, "en_cok_bekleyen": 3, "ses": "tr-TR-Wavenet-B", "konusma_hizi": 1.06, "perde": -1.5}
GENISLIK, YUKSEKLIK, FPS = 1080, 1920, 30
SAHNE_TIPLERI = ["baski", "temizlik", "ilk_katman", "sicaklik", "hiz", "yapistirici", "sayi", "karsilastir", "ozet", "cta"]
# Türkçe konuşmada yanlış okunan kısaltmalar: yalnızca SESE uygulanır, alt yazıda özgün yazı kalır.
OKUNUS = {"PLA": "pe el a", "PETG": "pe e te ge", "ABS": "a be se", "TPU": "te pe u", "ASA": "a se a", "PVA": "pe ve a", "3D": "üç de",
          "mm": "milimetre", "mm/s": "milimetre bölü saniye", "CAD": "kad", "STL": "es te el", "G-code": "ci kod", "USB": "u es be"}
SAYI_BIRIMLERI = {"°C": "derece"}


_ILERLEME = {"t": 0.0, "y": -100}


def ilerleme(asama, yuzde, mesaj="", zorla=False):
    """Paneldeki ilerleme göstergesi için ofis sunucusuna aşama/yüzde bildirir (sessizce başarısız olur; üretimi bozmaz)."""
    print(f"İlerleme: {asama} %{yuzde}" + (f" — {mesaj}" if mesaj else ""), flush=True)
    ofis, sir = os.environ.get("OFIS_ADRES"), os.environ.get("BILDIRIM_SIRRI")
    if not (ofis and sir):
        return
    simdi = time.time()
    if not zorla and simdi - _ILERLEME["t"] < 15 and yuzde - _ILERLEME["y"] < 10:
        return
    _ILERLEME.update(t=simdi, y=yuzde)
    try:
        istek = urllib.request.Request(ofis.rstrip("/") + "/api/viral-ilerleme", method="POST",
                                       data=json.dumps({"asama": asama, "yuzde": int(yuzde), "mesaj": str(mesaj)[:160]}).encode(),
                                       headers={"Content-Type": "application/json", "X-Bildirim": sir})
        urllib.request.urlopen(istek, timeout=10).read()
    except Exception as e:
        print(f"(ilerleme bildirilemedi: {type(e).__name__})")


def json_oku(yol, varsayilan):
    try:
        return json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(varsayilan))


def yaz(yol, veri):
    pathlib.Path(yol).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- senaryo ----------

def slug(metin):
    t = metin.lower().translate(str.maketrans("çğıöşü", "cgiosu"))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def buyuk(t):
    """Türkçe büyük harf (i→İ, ı→I)."""
    return t.replace("i", "İ").replace("ı", "I").upper()


def senaryo_dogrula(s):
    """Senaryoyu temizler; sorun varsa ValueError. Dönen: temiz senaryo."""
    sah = s.get("sahneler") or []
    if not 5 <= len(sah) <= 12:
        raise ValueError(f"sahne sayısı 5-12 olmalı ({len(sah)})")
    temiz = []
    for i, x in enumerate(sah):
        tip = x.get("tip")
        if tip not in SAHNE_TIPLERI:
            raise ValueError(f"{i + 1}. sahne tipi geçersiz: {tip}")
        anlati = " ".join(str(x.get("anlati") or "").split())
        if len(anlati.split()) < 3:
            raise ValueError(f"{i + 1}. sahnede anlatı yok")
        pr = x.get("params") if isinstance(x.get("params"), dict) else {}
        temiz.append({"tip": tip, "params": pr, "ekran": U.yazi_temizle(str(x.get("ekran") or ""))[:34].upper().replace("İ", "İ") if x.get("ekran") else "",
                      "rozet": str(x.get("rozet") or "")[:2], "anlati": anlati})
    kelime = sum(len(x["anlati"].split()) for x in temiz)
    if not 70 <= kelime <= 190:
        raise ValueError(f"anlatı {kelime} kelime; 70-190 olmalı")
    if temiz[-1]["tip"] != "cta":
        temiz.append({"tip": "cta", "params": {"ana": "TAKİP ET", "alt": "@gurtechs3d"}, "ekran": "", "rozet": "", "anlati": "Daha fazlası için takip et!"})
    return {"konu": str(s.get("konu") or "")[:140], "baslik": U.yazi_temizle(str(s.get("baslik") or ""))[:90],
            "aciklama": str(s.get("aciklama") or "")[:900].replace("http", ""), "etiketler": [re.sub(r"[^a-z0-9ığüşöç]", "", str(e).lower()) for e in (s.get("etiketler") or [])][:8], "sahneler": temiz}


SENARYO_ISTEMI = """3D yazıcı ve 3D baskı konusunda, YouTube Shorts / Instagram Reels için ~60 saniyelik, merak uyandıran, bilgi veren TÜRKÇE bir video senaryosu yaz.
Konu: {konu}
İpucu: {ipucu}

YAPI: (1) İlk sahne güçlü kanca: merak uyandıran bir soru, şaşırtıcı bir gerçek ya da yaygın bir hata ("çoğu kişi bunu yanlış yapıyor"). (2) 4-6 sahnede net, uygulanabilir bilgi (numaralı ipuçları). (3) Özet. (4) Son sahne CTA (yoruma davet + takip et).
Toplam anlatı 120-150 kelime (yaklaşık 55-62 sn). Cümleler kısa, konuşma dili, "sen" hitabı. Her sahne 12-26 kelime.
DOĞRULUK KURALLARI: Yalnızca 3D baskı topluluğunda yaygın kabul gören, doğru bilgileri yaz. Emin olmadığın sayı/rakam verme; sıcaklık ve hızlarda "genellikle", "civarı" gibi aralıklar kullan. Sağlık/güvenlik iddiası yalnızca genel ve doğru olsun. Marka karşılaştırması, fiyat, istatistik, kişisel deneyim ("ben denedim") UYDURMA. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları ve ölçüleri yazıyla yaz (ör. "elli beş ila altmış derece", "yirmi beş milimetre"); PLA/PETG gibi kısaltmaları büyük harfle yaz.
SAHNE TİPLERİ (animasyon): baski (nesne: vazo|disli|kule|warp), temizlik, ilk_katman, sicaklik (params: deger sayı, birim "°C", etiket kısa metin), hiz (params: deger sayı mm/s), yapistirici, sayi (params: deger sayı, birim "%", etiket kısa cümle), karsilastir (params: a:{{ad,deger}}, b:{{ad,deger}}), ozet (params: maddeler 3-4 kısa madde), cta.
Konuya uygun tipleri seç; konuyla ilgisi olmayan sahneyi (ör. sıcaklık) zorla koyma, bunun yerine "baski" ya da "sayi" kullan. İlk sahne "baski" ya da "sayi", son sahne "cta" olsun.
YALNIZCA JSON döndür: {{"konu":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["3dprinting","..."],
"sahneler":[{{"tip":"...","params":{{}},"ekran":"ekranda büyük görünen en çok 3-4 kelimelik başlık","rozet":"ipucu numarası ya da boş","anlati":"seslendirilecek metin"}}]}}"""


def senaryo_uret_yz(konu, ipucu):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    govde = {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": 0.7,
             "messages": [{"role": "system", "content": "Sen Türkçe 3D baskı eğitim videoları yazan, doğruluğa önem veren bir içerik editörüsün. Yalnızca geçerli JSON döndür."},
                          {"role": "user", "content": SENARYO_ISTEMI.format(konu=konu, ipucu=ipucu or "-")}]}
    for deneme in range(2):
        try:
            r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                                       headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
            with urllib.request.urlopen(r, timeout=120) as y:
                s = json.loads(json.load(y)["choices"][0]["message"]["content"])
            s["konu"] = s.get("konu") or konu
            return senaryo_dogrula(s)
        except Exception as e:
            print(f"UYARI: senaryo üretimi/doğrulaması başarısız ({deneme + 1}/2): {type(e).__name__}: {str(e)[:160]}")
    return None


def senaryo_sec(a, ayar):
    """(senaryo, kaynak_adi) ya da (None, neden)"""
    kullanilan = set(json_oku(KULLANILAN, []))
    if a.senaryo:
        return senaryo_dogrula(json_oku(a.senaryo, {})), pathlib.Path(a.senaryo).stem
    if a.konu:
        kutuphane = SENARYOLAR / f"{slug(a.konu)}.json"
        if kutuphane.exists():
            return senaryo_dogrula(json_oku(kutuphane, {})), kutuphane.stem
        s = senaryo_uret_yz(a.konu, "")
        return (s, slug(a.konu)) if s else (None, "konu için senaryo üretilemedi (OPENAI_API_KEY yok ya da yanıt geçersiz)")
    # sırayla: kullanılmamış hazır senaryo, sonra konu listesi + yapay zekâ
    for f in sorted(SENARYOLAR.glob("*.json")):
        if f.stem not in kullanilan:
            return senaryo_dogrula(json_oku(f, {})), f.stem
    for k in json_oku(VIDEO / "konular.json", []):
        if slug(k["konu"]) in kullanilan:
            continue
        s = senaryo_uret_yz(k["konu"], k.get("ipucu"))
        if s:
            return s, slug(k["konu"])
        return None, f"'{k['konu']}' için senaryo üretilemedi"
    return None, "kullanılmamış konu kalmadı (video/konular.json'a yeni konu ekle)"


# ---------- seslendirme ----------

def kelime_okunusu(k):
    cekirdek = k.strip(".,;:!?\"'()")
    ek = k[len(k.rstrip(".,;:!?\"'()")):]
    on = k[:len(k) - len(k.lstrip(".,;:!?\"'()"))]
    if cekirdek in OKUNUS:
        return f'{escape(on)}<sub alias="{OKUNUS[cekirdek]}">{escape(cekirdek)}</sub>{escape(ek)}'
    return escape(k)


def ssml_olustur(metin):
    kel = metin.split()
    govde = "".join(f'<mark name="w{i}"/>{kelime_okunusu(k)} ' for i, k in enumerate(kel))
    return f"<speak>{govde.strip()}</speak>", kel


def wav_coz(ham):
    with wave.open(io.BytesIO(ham), "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        veri = w.readframes(n)
    x = np.frombuffer(veri, dtype="<i2").astype(np.float64) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def tahmini_sure(kel):
    """TTS yokken kelime başına tahmini süre (sn)."""
    t, sure = 0.0, []
    for k in kel:
        d = 0.10 + 0.058 * len(k)
        sure.append((t, d))
        t += d + (0.28 if k[-1:] in ".!?" else 0.12 if k[-1:] in ",;:" else 0.0)
    return sure, t


def sahne_seslendir(metin, ayar, anahtar):
    """{'ses': np.array (SES.SR mono) ya da None, 'sure': sn, 'baslangic': [kelime başlangıçları]}"""
    ssml, kel = ssml_olustur(metin)
    if not anahtar:
        zamanlar, toplam = tahmini_sure(kel)
        return {"ses": None, "sure": toplam, "baslangic": [z[0] for z in zamanlar], "tahmini": True}
    govde = {"input": {"ssml": ssml}, "voice": {"languageCode": "tr-TR", "name": ayar["ses"]},
             "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SES.SR, "speakingRate": ayar["konusma_hizi"], "pitch": ayar["perde"],
                             "effectsProfileId": ["headphone-class-device"]},
             "enableTimePointing": ["SSML_MARK"]}
    son = None
    for deneme in range(3):
        try:
            r = urllib.request.Request(f"{TTS_ADRES}?key={anahtar}", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r, timeout=90) as y:
                j = json.load(y)
            x, sr = wav_coz(base64.b64decode(j["audioContent"]))
            if sr != SES.SR:
                x = np.interp(np.arange(int(len(x) * SES.SR / sr)) / SES.SR, np.arange(len(x)) / sr, x)
            tp = {t["markName"]: float(t["timeSeconds"]) for t in (j.get("timepoints") or [])}
            bas = [tp.get(f"w{i}") for i in range(len(kel))]
            return {"ses": x, "sure": len(x) / SES.SR, "baslangic": tamamla(bas, len(x) / SES.SR, kel)}
        except urllib.error.HTTPError as e:
            son = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code in (400, 401, 403):
                break
        except Exception as e:
            son = f"{type(e).__name__}: {e}"
    raise RuntimeError(f"Google TTS başarısız: {son}")


def sessizlikler(x, en_az=0.09):
    """Konuşmadaki duraklamalar: [(başlangıç, bitiş)] sn. 10 ms RMS çerçeveleri; eşik tepe düzeyin ~%4'ü."""
    blok = int(0.01 * SES.SR)
    n = len(x) // blok
    if n < 5:
        return []
    r = np.sqrt((x[:n * blok].reshape(n, blok) ** 2).mean(axis=1))
    sessiz = r < max(r.max() * 0.04, 1e-4)
    sonuc, b = [], None
    for i, v in enumerate(sessiz):
        if v and b is None:
            b = i
        if (not v or i == n - 1) and b is not None:
            e = i if not v else i + 1
            if (e - b) * 0.01 >= en_az:
                sonuc.append((b * 0.01, e * 0.01))
            b = None
    return sonuc


def gemini_zamanla(x, kel):
    """Kelime zamanı vermeyen TTS için: konuşma baş/son sessizliğini kırp, noktalama sonrası gerçek duraklamalara çapa at, kalanını uzunlukla dağıt.
    Dönen: (kırpılmış ses, kelime başlangıçları)"""
    sess = sessizlikler(x)
    bas_kirp = sess[0][1] if sess and sess[0][0] < 0.02 else 0.0
    son_kirp = sess[-1][0] if sess and sess[-1][1] > len(x) / SES.SR - 0.03 else len(x) / SES.SR
    a, b = int(max(bas_kirp - 0.04, 0) * SES.SR), int(min(son_kirp + 0.12, len(x) / SES.SR) * SES.SR)
    x = x[a:b]
    sess = sessizlikler(x)
    sure = len(x) / SES.SR
    tah, toplam = tahmini_sure(kel)
    olcek = sure / toplam if toplam else 1.0
    bas = [None] * len(kel)
    bas[0] = 0.0
    son_anca = 0.0
    for i in range(1, len(kel)):
        if kel[i - 1][-1:] not in ".!?;:,":
            continue
        tahmin = tah[i][0] * olcek
        aday = [e for (s0, e) in sess if abs(e - tahmin) < 0.4 and e > son_anca + 0.1 and s0 > 0.05]
        if aday:
            bas[i] = min(aday, key=lambda e: abs(e - tahmin))
            son_anca = bas[i]
    return x, tamamla(bas, sure, kel)


def okunus_uygula(metin):
    for k, v in sorted(OKUNUS.items(), key=lambda kv: -len(kv[0])):
        metin = re.sub(r"(?<![\wİıÇçĞğÖöŞşÜü])" + re.escape(k) + r"(?![\wİıÇçĞğÖöŞşÜü])", v, metin)
    return metin


def gemini_istegi(okunacak, ayar, anahtar):
    """Gemini TTS'ten konuşma ister. Dönen: np.array (SES.SR, mono). Günlük kota dolduysa beklemeden hata verir."""
    istem = ("Aşağıdaki metni Türkçe olarak, güven veren, enerjik ve akıcı bir bilgi videosu anlatıcısı gibi, biraz hızlı tempoda, doğal vurgu ve kısa duraklamalarla oku. "
             "Boş satırlarda biraz daha uzun dur. Yalnızca metni oku, başka bir şey ekleme:\n\n" + okunacak)
    govde = {"contents": [{"parts": [{"text": istem}]}],
             "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": ayar.get("gemini_ses") or "Orus"}}}}}
    son = None
    for deneme in range(5):
        try:
            r = urllib.request.Request(f"{GEMINI_ADRES}/{GEMINI_MODEL}:generateContent", data=json.dumps(govde).encode(), method="POST",
                                       headers={"Content-Type": "application/json", "x-goog-api-key": anahtar})
            with urllib.request.urlopen(r, timeout=180) as y:
                j = json.load(y)
            parca = j["candidates"][0]["content"]["parts"][0]["inlineData"]
            ham = base64.b64decode(parca["data"])
            m = re.search(r"rate=(\d+)", parca.get("mimeType") or "")
            sr = int(m.group(1)) if m else 24000
            x = np.frombuffer(ham[:len(ham) // 2 * 2], dtype="<i2").astype(np.float64) / 32768
            x = np.interp(np.arange(int(len(x) * SES.SR / sr)) / SES.SR, np.arange(len(x)) / sr, x)
            if len(x) < SES.SR * 0.8:
                raise ValueError("ses çok kısa")
            return x
        except urllib.error.HTTPError as e:
            son = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}"
            if e.code in (400, 401, 403):
                break
            if e.code == 429 and re.search(r"PerDay|per day|daily", son, re.I):
                raise RuntimeError("Gemini TTS günlük ücretsiz kotası doldu (yaklaşık yarın tekrar denenebilir ya da Google Cloud TTS/ücretli plan gerekir). " + son[:200])
            time.sleep(20 * (deneme + 1))   # dakika sınırı: bekleyip yeniden dene
        except Exception as e:
            son = f"{type(e).__name__}: {e}"
            time.sleep(4)
    raise RuntimeError(f"Gemini TTS başarısız: {son}")


def gemini_seslendir(metin, ayar, anahtar):
    """Tek sahne için Gemini TTS. Kelime zamanı vermez; gemini_zamanla ile çıkarılır."""
    x, bas = gemini_zamanla(gemini_istegi(okunus_uygula(metin), ayar, anahtar), metin.split())
    return {"ses": x, "sure": len(x) / SES.SR, "baslangic": bas}


def gemini_hepsi(sahneler, ayar, anahtar):
    """Tüm anlatıyı TEK istekte seslendirir (ücretsiz katman günlük istek sınırı düşük), sahnelere duraklamalardan böler.
    Dönen: sahne başına {'ses','sure','baslangic'} listesi."""
    metinler = [s["anlati"] for s in sahneler]
    x = gemini_istegi("\n\n".join(okunus_uygula(m) for m in metinler), ayar, anahtar)
    kelimeler = [w for m in metinler for w in m.split()]
    x, bas = gemini_zamanla(x, kelimeler)
    sure = len(x) / SES.SR
    ilk, n = [], 0
    for m in metinler:
        ilk.append(n)
        n += len(m.split())
    kes = [0.0]
    for k in range(1, len(metinler)):
        kes.append(max(kes[-1] + 0.6, bas[ilk[k]] - 0.14))   # sahne başlangıcından hemen önce, duraklamanın içinde
    kes.append(sure)
    sonuc = []
    for k, m in enumerate(metinler):
        a, b = int(kes[k] * SES.SR), int(kes[k + 1] * SES.SR)
        parca = x[a:b]
        n_k = len(m.split())
        sonuc.append({"ses": parca, "sure": len(parca) / SES.SR, "baslangic": [max(0.0, t - kes[k]) for t in bas[ilk[k]:ilk[k] + n_k]]})
    return sonuc


def tamamla(bas, sure, kel):
    """Eksik kelime zamanlarını komşulardan/uzunluktan doldur; artan sırayı garanti et."""
    n = len(bas)
    agirlik = [0.1 + 0.058 * len(k) for k in kel]
    for i in range(n):
        if bas[i] is None:
            sol = max((j for j in range(i) if bas[j] is not None), default=None)
            sag = min((j for j in range(i + 1, n) if bas[j] is not None), default=None)
            t0 = bas[sol] if sol is not None else 0.0
            t1 = bas[sag] if sag is not None else sure
            a, b = (sol if sol is not None else 0), (sag if sag is not None else n)
            toplam = sum(agirlik[a:b]) or 1
            bas[i] = t0 + (t1 - t0) * sum(agirlik[a:i]) / toplam
    for i in range(1, n):
        bas[i] = max(bas[i], bas[i - 1] + 0.04)
    return [min(b, max(sure - 0.05, 0)) for b in bas]


def fixture_seslendir(dizin, i, metin):
    """Test için önceden üretilmiş konuşma (wav + kelime zamanları)."""
    d = pathlib.Path(dizin)
    j = json.loads((d / f"s{i}.json").read_text())
    x, sr = wav_coz((d / f"s{i}.wav").read_bytes())
    if sr != SES.SR:
        x = np.interp(np.arange(int(len(x) * SES.SR / sr)) / SES.SR, np.arange(len(x)) / sr, x)
    kel = metin.split()
    bas = [t["timeSeconds"] for t in j["timepoints"]][:len(kel)]
    return {"ses": x, "sure": len(x) / SES.SR, "baslangic": tamamla(bas + [None] * (len(kel) - len(bas)), len(x) / SES.SR, kel)}


# ---------- zaman çizelgesi ----------

def parcala_altyazi(kelimeler, en_cok_kelime=5, en_cok_harf=30):
    """Kelime listesinden (k, t0, t1, sahne) alt yazı parçaları: noktalamada ya da uzunlukta bölünür."""
    parcalar, cur = [], []
    for w in kelimeler:
        cur.append(w)
        harf = sum(len(x["k"]) + 1 for x in cur)
        if w["k"][-1:] in ".!?;:" or (w["k"][-1:] == "," and len(cur) >= 3) or len(cur) >= en_cok_kelime or harf >= en_cok_harf:
            parcalar.append(cur)
            cur = []
    if cur:
        parcalar.append(cur)
    cikti = []
    for i, p in enumerate(parcalar):
        t0, t1 = p[0]["t0"], p[-1]["t1"] + 0.2
        if i + 1 < len(parcalar):
            t1 = min(t1, parcalar[i + 1][0]["t0"] - 0.02)
        cikti.append({"t0": round(t0, 3), "t1": round(max(t1, t0 + 0.3), 3), "kelimeler": [{"k": x["k"], "t0": round(x["t0"], 3), "t1": round(x["t1"], 3)} for x in p]})
    return cikti


def cizelge_kur(senaryo, sesler):
    t, sahneler, kelimeler, parcalar_ses = 0.0, [], [], []
    n = len(senaryo["sahneler"])
    for i, (s, v) in enumerate(zip(senaryo["sahneler"], sesler)):
        on = 0.6 if i == 0 else 0.42
        son = 1.1 if i == n - 1 else 0.38
        v0 = t + on
        t1 = v0 + v["sure"] + son
        kel = s["anlati"].split()
        for k, (w, b) in enumerate(zip(kel, v["baslangic"])):
            bitis = v["baslangic"][k + 1] if k + 1 < len(kel) else v["sure"]
            kelimeler.append({"k": w, "t0": v0 + b, "t1": v0 + max(bitis - 0.02, b + 0.08), "sahne": i})
        if v["ses"] is not None:
            parcalar_ses.append((v0, v["ses"]))
        sahneler.append({"tip": s["tip"], "t0": round(t, 3), "t1": round(t1, 3), "ekran": s["ekran"], "rozet": s["rozet"], "params": s["params"]})
        t = t1
    plan = {"genislik": GENISLIK, "yukseklik": YUKSEKLIK, "fps": FPS, "sure": round(t, 3), "sahneler": sahneler, "altyazi": parcala_altyazi(kelimeler)}
    return plan, parcalar_ses


def konusma_dosyasi(parcalar_ses, sure, yol):
    n = int(sure * SES.SR)
    x = np.zeros(n)
    for v0, ses in parcalar_ses:
        i = int(v0 * SES.SR)
        x[i:i + len(ses)] += ses[:max(0, n - i)]
    SES.yaz_wav(yol, np.stack([x, x], axis=1) * 0.9)
    gecici = pathlib.Path(str(yol) + ".ham.wav")
    pathlib.Path(yol).replace(gecici)
    # konuşma işleme: alçak kesim, hafif sıkıştırma, netlik
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gecici), "-af",
                        "highpass=f=75,acompressor=threshold=-21dB:ratio=3:attack=6:release=90:makeup=3,equalizer=f=3200:t=q:w=1.1:g=2,alimiter=limit=0.9",
                        "-ar", str(SES.SR), "-ac", "2", str(yol)], capture_output=True, text=True)
    gecici.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError("konuşma işlenemedi: " + (r.stderr or "")[-200:])


# ---------- görüntü + montaj ----------

def goruntu_ciz(plan_yolu, cikti, olcek=1.0):
    node = os.environ.get("NODE") or "node"
    komut = [node, str(VIDEO / "render.js"), str(plan_yolu), "--cikti", str(cikti), "--olcek", str(olcek)]
    p = subprocess.Popen(komut, cwd=str(VIDEO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for satir in p.stdout:
        print(satir, end="", flush=True)
        m = re.search(r"Kare (\d+)/(\d+)", satir)
        if m and int(m.group(2)):
            oran = int(m.group(1)) / int(m.group(2))
            ilerleme("3D animasyon çiziliyor", 25 + int(oran * 70), f"kare {m.group(1)}/{m.group(2)}")
    p.wait()
    if p.returncode != 0 or not pathlib.Path(cikti).exists():
        raise RuntimeError("3D çizim başarısız (render.js)")


def birlestir(sessiz, ses, cikti):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sessiz), "-i", str(ses), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(cikti)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("birleştirme başarısız: " + (r.stderr or "")[-300:])


def aciklama_olustur(s, tts_gercek):
    etiket = " ".join(f"#{e}" for e in dict.fromkeys(s["etiketler"] + ["3dprinting", "3dbaski", "shorts"]))[:300]
    return (s["aciklama"].strip() + "\n\n" + ("Seslendirme yapay zekâ (Google) ile üretilmiştir. " if tts_gercek else "") +
            "Animasyon ve ses tasarımı yapay zekâ ile kodla üretilmiştir.\n\n" + etiket)


def hata(mesaj):
    print(f"HATA: {mesaj}")
    ilerleme("Hata", 100, mesaj, zorla=True)
    return 1


def calis(a):
    ayar = dict(VARSAYILAN)
    ayar.update(json_oku(AYAR, {}))
    if not ayar["aktif"] and not (a.hemen or a.senaryo or a.konu):
        print("Karar: bekle (viral video üretimi kapalı)")
        ilerleme("beklemede", 100, "viral video üretimi kapalı", zorla=True)
        return 0
    bekleyen = sum(1 for f in DIZIN.glob("s*.json") if json_oku(f, {}).get("durum") == "onay_bekliyor")
    if bekleyen >= ayar["en_cok_bekleyen"] and not (a.hemen or a.senaryo or a.konu):
        print(f"Karar: bekle ({bekleyen} taslak onay bekliyor; yenisi üretilmez)")
        ilerleme("beklemede", 100, f"{bekleyen} taslak onay bekliyor; yenisi üretilmedi", zorla=True)
        return 0
    anahtar = os.environ.get("GOOGLE_TTS_API_KEY")
    gemini = os.environ.get("GEMINI_API_KEY")
    if not (anahtar or gemini) and not (a.tts_dizin or a.sessiz):
        return hata("seslendirme anahtarı yok. İkisinden biri gerekli (GitHub Secrets): 'GEMINI_API_KEY' (aistudio.google.com/apikey, kart gerekmez) ya da 'GOOGLE_TTS_API_KEY' (Google Cloud Text-to-Speech).")
    try:
        senaryo, kaynak = senaryo_sec(a, ayar)
    except ValueError as e:
        return hata(f"senaryo geçersiz: {e}")
    if not senaryo:
        print(f"Karar: bekle ({kaynak})")
        ilerleme("beklemede", 100, kaynak, zorla=True)
        return 0
    print(f"Konu: {senaryo['konu']} ({kaynak}); {len(senaryo['sahneler'])} sahne")
    ilerleme("Senaryo hazır", 5, senaryo["konu"][:100], zorla=True)
    H.ffmpeg_hazir()
    sesler = []
    if gemini and not anahtar and not a.sessiz and not a.tts_dizin:
        try:
            ilerleme("Seslendirme (Gemini, tek istek)", 8, "", zorla=True)
            sesler = gemini_hepsi(senaryo["sahneler"], ayar, gemini)
        except RuntimeError as e:
            return hata(str(e))
    for i, s in enumerate(senaryo["sahneler"] if not sesler else []):
        ilerleme("Seslendirme", 5 + int(15 * i / len(senaryo["sahneler"])), f"sahne {i + 1}/{len(senaryo['sahneler'])}")
        sesler.append(fixture_seslendir(a.tts_dizin, i, s["anlati"]) if a.tts_dizin else gemini_seslendir(s["anlati"], ayar, gemini) if (gemini and not anahtar and not a.sessiz) else sahne_seslendir(s["anlati"], ayar, None if a.sessiz else anahtar))
    plan, parcalar = cizelge_kur(senaryo, sesler)
    print(f"Süre: {plan['sure']:.1f} sn, {len(plan['altyazi'])} alt yazı parçası")
    if plan["sure"] > 175:
        return hata("video 175 sn'den uzun (Shorts sınırı 3 dk); anlatıyı kısalt.")
    z = H.simdi().astimezone(datetime.timezone.utc)
    damga = z.strftime("%Y%m%d%H%M%S")
    cikti = pathlib.Path(a.cikti) if a.cikti else KOK / f"videolar/yukleme_{damga}.mp4"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        yaz(g / "plan.json", plan)
        konusma = None
        if parcalar:
            konusma_dosyasi(parcalar, plan["sure"], g / "konusma.wav")
            konusma = g / "konusma.wav"
        ilerleme("Müzik ve ses efektleri", 22, "", zorla=True)
        SES.uret(plan, g / "ses_ham.wav", konusma)
        SES.normalize(g / "ses_ham.wav", g / "ses.wav")
        goruntu_ciz(g / "plan.json", g / "sessiz.mp4", a.olcek)
        ilerleme("Ses ve görüntü birleştiriliyor", 96, "", zorla=True)
        birlestir(g / "sessiz.mp4", g / "ses.wav", cikti)
        if a.plan_kaydet:
            yaz(a.plan_kaydet, plan)
    print(f"Video hazır: {cikti} ({cikti.stat().st_size / 1e6:.1f} MB)")
    if a.git or not a.cikti:
        kimlik = f"s{z.strftime('%Y%m%d-%H%M%S')}"
        gercek = bool(anahtar or gemini) and not a.tts_dizin and not a.sessiz
        taslak = {"id": kimlik, "olusturma": z.strftime("%Y-%m-%dT%H:%M:%SZ"), "durum": "onay_bekliyor", "tur": "viral", "video": f"videolar/{cikti.name}", "sure": round(plan["sure"], 1),
                  "baslik": senaryo["baslik"], "aciklama": aciklama_olustur(senaryo, gercek), "muzik": "Sentez (kodla üretildi)", "konu": senaryo["konu"], "tasarimlar": [], "hikayeler": []}
        yaz(DIZIN / f"{kimlik}.json", taslak)
        yaz(KULLANILAN, sorted(set(json_oku(KULLANILAN, [])) | {kaynak}))
        print(f"Taslak hazır: {kimlik}; başlık: {senaryo['baslik']}")
        if a.git:
            H.git_kaydet(f"Viral video: {kimlik} taslağı ({senaryo['konu'][:60]})", [DIZIN, KOK / "videolar"])
            ilerleme("Hazır", 100, senaryo["baslik"][:100], zorla=True)
            H.bildir("Yeni viral video taslağı hazır", f"{senaryo['baslik']} — panelde onayını bekliyor.", adres="/", etiket="shorts")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konu", help="belirli bir konu (hazır senaryo yoksa yapay zekâ yazar)")
    ap.add_argument("--senaryo", help="senaryo JSON dosyası")
    ap.add_argument("--hemen", action="store_true", help="kapalı ya da taslak limiti dolu olsa bile bir kez üret")
    ap.add_argument("--git", action="store_true", help="sonucu depoya yaz ve it")
    ap.add_argument("--olcek", type=float, default=1.0, help="çizim ölçeği (test için 0.5)")
    ap.add_argument("--cikti", help="videoyu bu dosyaya yaz (taslak kaydı oluşturmaz, --git ile birlikte kullanılmadıkça)")
    ap.add_argument("--tts-dizin", help="test: önceden üretilmiş konuşma dizini (s0.wav, s0.json…)")
    ap.add_argument("--sessiz", action="store_true", help="test: seslendirme olmadan (tahmini zamanlama)")
    ap.add_argument("--plan-kaydet", help="plan.json'u bu yola da yaz")
    try:
        kod = calis(ap.parse_args())
    except Exception as e:
        ilerleme("Hata", 100, f"{type(e).__name__}: {str(e)[:140]}", zorla=True)
        raise
    sys.exit(kod)


if __name__ == "__main__":
    main()
