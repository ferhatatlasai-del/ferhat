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
import hashlib
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
try:
    import basari as B  # noqa: E402
except Exception:   # başarı hafızası yoksa eski davranış (konu listesi)
    B = None
import hikaye_uret as U  # noqa: E402
import anlat_senaryo as AN  # noqa: E402
import ses_tasarim as SES  # noqa: E402

KOK = H.KOK
VIDEO = KOK / "video"
SENARYOLAR = VIDEO / "senaryolar"
DIZIN = KOK / "shorts"
AYAR = DIZIN / "viral_ayar.json"
KULLANILAN = DIZIN / "viral_kullanilan.json"
NOKTALAR = DIZIN / "viral_noktalar.json"   # önceki videolarda anlatılan noktalar (içerik tekrarını önlemek için) + son renk tonu
TONLAR = [0, -32, 38, 72, 150, 190, 250, 305]
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
import yz_model as YZ  # noqa: E402
MODEL = YZ.model("video", "gpt-4o-mini")
TTS_ADRES = os.environ.get("TTS_ADRES") or "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
GEMINI_ADRES = os.environ.get("GEMINI_ADRES") or "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = os.environ.get("GEMINI_TTS_MODEL") or "gemini-2.5-flash-preview-tts"
VARSAYILAN = {"bicim": "anlat", "gorsel_kalitesi": "medium", "gemini_ses": "Orus", "aktif": True, "en_cok_bekleyen": 3, "ses": "tr-TR-Wavenet-B", "konusma_hizi": 1.06, "perde": -1.5}
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


SECIM = {}      # bu çalışmanın konu kararı (taslağa yazılır): tur = turev | kesif | liste | elle
ILHAM = ""      # geçmiş performanstan çıkan örnek başlıklar (komuta eklenir); keşif/elle seçimde boş


def ilham_ekle(istem):
    """Örnek başlıkları, komutun 'YALNIZCA JSON' satırından hemen önce ekler (ilham yoksa komut aynen kalır)."""
    if not ILHAM:
        return istem
    i = istem.rfind("YALNIZCA JSON")
    return istem[:i] + ILHAM.strip() + "\n\n" + istem[i:] if i >= 0 else istem + "\n" + ILHAM


def turev_sec():
    """Her 4 videonun 3'ü en çok izlenenlerin kalıbını izleyen YENİ konu, her 4.'sü 'keşif' (listeden yeni alan). (konu, ipucu) ya da None."""
    global ILHAM
    ILHAM = ""
    if B is None:
        SECIM.update(tur="liste")
        return None
    if len(json_oku(KULLANILAN, [])) % 4 == 3:
        SECIM.update(tur="kesif")
        print("Konu seçimi: keşif sırası (listeden yeni bir alan; geçmiş performans komuta eklenmez)")
        return None
    try:
        ILHAM = B.ilham_metni()
        t = B.turev_konu()
    except Exception as e:
        print(f"UYARI: başarı hafızası kullanılamadı ({type(e).__name__}); konu listesi kullanılacak.")
        SECIM.update(tur="liste")
        return None
    if not t:
        SECIM.update(tur="liste", ilham=bool(ILHAM))
        return None
    SECIM.update(tur="turev", ilham=t[2])
    print(f"Konu seçimi: en çok izlenenlerden türetildi → {t[0]}")
    return t[0], t[1]


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
                          {"role": "user", "content": ilham_ekle(SENARYO_ISTEMI.format(konu=konu, ipucu=ipucu or "-"))}]}
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
        SECIM.update(tur="elle")
        return senaryo_dogrula(json_oku(a.senaryo, {})), pathlib.Path(a.senaryo).stem
    if a.konu:
        SECIM.update(tur="elle")
        kutuphane = SENARYOLAR / f"{slug(a.konu)}.json"
        if kutuphane.exists():
            return senaryo_dogrula(json_oku(kutuphane, {})), kutuphane.stem
        s = senaryo_uret_yz(a.konu, "")
        return (s, slug(a.konu)) if s else (None, "konu için senaryo üretilemedi (OPENAI_API_KEY yok ya da yanıt geçersiz)")
    t = turev_sec()
    if t:
        s = senaryo_uret_yz(t[0], t[1])
        if s:
            return s, "turev-" + slug(t[0])
        SECIM.update(tur="liste")   # türev konu yazılamadı: listeden devam
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



# ======================= LİSTE BİÇİMİ (geri sayım, konuya özel gerçekçi görseller) =======================
LISTE_ISTEMI = """3D yazıcı ve 3D baskı hakkında "geri sayım listesi" biçiminde, merak uyandıran TÜRKÇE bir YouTube Shorts / Instagram Reels senaryosu yaz.
Konu: {konu}
İpucu: {ipucu}

BİÇİM: Kısa bir kanca (giriş), sonra sondan başa {n} madde (sira: {n} … 1; 1 en iyisi/en yükseği), sonunda kısa kapanış. Toplam anlatı 120-160 kelime.
Her maddenin kartında bir SAYAÇ gösterilecek: tüm maddeler AYNI ölçüyü kullansın (ör. ısı dayanımı °C, tipik baskı sıcaklığı °C, yoğunluk g/cm³, Shore sertliği). Ölçü konuya uymuyorsa deger null olsun.
DOĞRULUK: Yalnızca sıradan bir masaüstü 3D yazıcıyla (ısıtmalı tabla, en çok yaklaşık 300 °C nozul) basılabilen malzemeleri/ürünleri listele; endüstriyel ya da özel donanım isteyen malzemeyi (ör. yüksek sıcaklık polimerleri) listeye koyma. Tüm maddelerin değeri aynı birimde ve aynı ölçüde (aynı tür ölçüm) olsun; sıralama bu değerlerle tutarlı olsun. Sayısal değerler 3D baskı topluluğunda ve üretici tablolarında yaygın kabul gören TİPİK değerler olsun; aralık varsa orta değeri yaz ve deger_yazi'da "≈" kullan. Emin değilsen deger null. Marka, fiyat, uydurma istatistik, kişisel deneyim yok. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları anlatıda yazıyla yaz (ör. "altmış derece").
Anlatıda her madde sırasıyla başlasın ("Beşinci sırada …", "Ve birinci sırada …"). Giriş merak uyandırsın (ör. "birincisi seni şaşırtabilir"). Kapanış yoruma davet + takip etsin.
GÖRSEL: her bölüm için İngilizce, gerçekçi bir fotoğraf sahnesi tarifi yaz (konuyla doğrudan ilgili nesne: filament makarası, basılmış parça, nozul, yazıcı tablası…). Metin, logo, marka, insan yüzü YOK.
YALNIZCA JSON: {{"konu":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["3dprinting","..."],
"liste_basligi":"EN ÇOK 32 KARAKTER BÜYÜK HARF","olcu":{{"ad":"EN ÇOK 16 KARAKTER BÜYÜK HARF","birim":"°C","ondalik":0}},
"giris":{{"anlati":"15-25 kelime","baslik":"ekranda iki satır büyük başlık; satırları \\n ile ayır","gorsel":"..."}},
"maddeler":[{{"sira":{n},"ad":"en çok 16 karakter","alt":"en çok 28 karakterlik kısa açıklama","deger":60,"deger_yazi":"≈60","anlati":"14-24 kelime","gorsel":"..."}}],
"kapanis":{{"anlati":"8-14 kelime","gorsel":"..."}}}}"""

GORSEL_SABLONU = ("Photorealistic professional product photograph, {sahne}. Cozy maker workshop background softly out of focus, shallow depth of field, "
                  "soft cinematic lighting with warm highlights, high detail, vertical 9:16 composition, main subject centered slightly above the middle of the frame, "
                  "empty darker area in the lower third. No text, no letters, no logos, no brand names, no watermark, no human faces.")


def liste_dogrula(s):
    m = [x for x in (s.get("maddeler") or []) if isinstance(x, dict)]
    if not 4 <= len(m) <= 8:
        raise ValueError(f"madde sayısı 4-8 olmalı ({len(m)})")
    m = sorted(m, key=lambda x: -int(x.get("sira") or 0))
    n = len(m)
    temiz = lambda v, k: U.yazi_temizle(str(v or ""))[:k].strip()
    # birim ve değer yazısında ölçü işaretleri korunur (°, ≈, %, ³, /, ±); yazı tipinde bulunan karakterler
    isaretli = lambda v, k: "".join(c for c in str(v or "") if c.isalnum() or c in "°≈%³²/±.,-+ ")[:k].strip()
    olcu = s.get("olcu") if isinstance(s.get("olcu"), dict) else {}
    maddeler = []
    for i, x in enumerate(m):
        anlati = " ".join(str(x.get("anlati") or "").split())
        if len(anlati.split()) < 5:
            raise ValueError(f"{i + 1}. maddede anlatı yok")
        deger = x.get("deger")
        try:
            deger = None if deger in (None, "", "null") else float(deger)
        except (TypeError, ValueError):
            deger = None
        maddeler.append({"sira": n - i, "ad": temiz(x.get("ad"), 18), "alt": temiz(x.get("alt"), 30), "deger": deger,
                         "deger_yazi": isaretli(x.get("deger_yazi"), 10) or None, "anlati": anlati, "gorsel": str(x.get("gorsel") or x.get("ad") or "3D printed part")[:300]})
    giris = s.get("giris") or {}
    kapanis = s.get("kapanis") or {}
    if len(str(giris.get("anlati") or "").split()) < 5:
        raise ValueError("giriş anlatısı yok")
    kelime = sum(len(x["anlati"].split()) for x in maddeler) + len(str(giris.get("anlati")).split()) + len(str(kapanis.get("anlati") or "").split())
    if not 70 <= kelime <= 200:
        raise ValueError(f"anlatı {kelime} kelime; 70-200 olmalı")
    degerler = [x["deger"] for x in maddeler if x["deger"] is not None]
    olcu_temiz = None
    if degerler and olcu.get("ad"):
        en = max(maddeler, key=lambda x: x["deger"] if x["deger"] is not None else -1e9)
        olcu_temiz = {"ad": buyuk(temiz(olcu.get("ad"), 18)), "birim": isaretli(olcu.get("birim"), 8), "ondalik": 1 if olcu.get("ondalik") else 0,
                      "en_buyuk": en["deger"], "en_buyuk_ad": en["ad"]}
    return {"bicim": "liste", "konu": str(s.get("konu") or "")[:140], "baslik": temiz(s.get("baslik"), 90), "aciklama": str(s.get("aciklama") or "")[:900].replace("http", ""),
            "etiketler": [re.sub(r"[^a-z0-9ığüşöç]", "", str(e).lower()) for e in (s.get("etiketler") or [])][:8],
            "liste_basligi": buyuk(temiz(s.get("liste_basligi"), 34)) or buyuk(temiz(s.get("konu"), 34)), "olcu": olcu_temiz,
            "giris": {"anlati": " ".join(str(giris.get("anlati")).split()), "baslik": buyuk(str(giris.get("baslik") or s.get("liste_basligi") or "")[:60]), "gorsel": str(giris.get("gorsel") or "3D printer workshop")[:300]},
            "maddeler": maddeler,
            "kapanis": {"anlati": " ".join(str(kapanis.get("anlati") or "Hangisini kullanıyorsun? Yorumlara yaz, takip et!").split()), "gorsel": str(kapanis.get("gorsel") or "colorful 3D printed parts on a workbench")[:300]}}


def liste_senaryo_uret(konu, ipucu, n=5):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    govde = {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": 0.7,
             "messages": [{"role": "system", "content": "Sen Türkçe 3D baskı eğitim videoları yazan, doğruluğa önem veren bir içerik editörüsün. Yalnızca geçerli JSON döndür."},
                          {"role": "user", "content": ilham_ekle(LISTE_ISTEMI.format(konu=konu, ipucu=ipucu or "-", n=n))}]}
    for deneme in range(2):
        try:
            r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                                       headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
            with urllib.request.urlopen(r, timeout=150) as y:
                s = json.loads(json.load(y)["choices"][0]["message"]["content"])
            s["konu"] = s.get("konu") or konu
            return liste_dogrula(s)
        except Exception as e:
            print(f"UYARI: liste senaryosu üretimi/doğrulaması başarısız ({deneme + 1}/2): {type(e).__name__}: {str(e)[:160]}")
    return None


def liste_senaryo_sec(a):
    kullanilan = set(json_oku(KULLANILAN, []))
    if a.senaryo:
        SECIM.update(tur="elle")
        return liste_dogrula(json_oku(a.senaryo, {})), pathlib.Path(a.senaryo).stem
    if a.konu:
        SECIM.update(tur="elle")
        s = liste_senaryo_uret(a.konu, "")
        return (s, "liste-" + slug(a.konu)) if s else (None, "liste senaryosu üretilemedi (OPENAI_API_KEY yok ya da yanıt geçersiz)")
    t = turev_sec()
    if t:
        s = liste_senaryo_uret(t[0], t[1])
        if s:
            return s, "turev-" + slug(t[0])
        SECIM.update(tur="liste")   # türev konu yazılamadı: listeden devam
    for k in json_oku(VIDEO / "liste_konulari.json", []):
        kim = "liste-" + slug(k["konu"])
        if kim in kullanilan:
            continue
        s = liste_senaryo_uret(k["konu"], k.get("ipucu"), int(k.get("n") or 5))
        return (s, kim) if s else (None, f"'{k['konu']}' için liste senaryosu üretilemedi")
    return None, "kullanılmamış liste konusu kalmadı (video/liste_konulari.json'a yeni konu ekle)"


SERBEST = False      # bu çalışmada 3D baskı dışı serbest konu mu (yalnızca elle yazılan konuda)
SON_HATA = ""        # senaryo üretilemediyse kullanıcıya gösterilecek neden (ör. konu uygunsuz)
UYGUNSUZ = RuntimeError
_3D_KOKLER = ("3d", "yazıcı", "yazici", "filament", "nozul", "baskı", "baski", "pla ", "petg", "abs ", "tpu", "bambu", "ender", "prusa", "slicer", "cura", "stl", "reçine", "recine", "fdm", "extruder", "ekstruder", "tabla", "katman", "warping", "stringing", "retraction")


def konu_3d_mu(konu):
    k = " " + str(konu).lower().replace("İ", "i").replace("I", "ı") + " "
    return any(x in k for x in _3D_KOKLER)


def anlat_senaryo_uret(konu, ipucu):
    global SON_HATA
    SON_HATA = ""
    """Yapay zekâ hikâye tahtasını (çeşitli animasyon sahneleri) yazar; doğrulama (çeşitlilik kuralları) geçmezse hata ile yeniden dener."""
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    gecmis_kayit = [[k.get("konu", ""), k.get("noktalar", [])] for k in json_oku(NOKTALAR, {}).get("videolar", [])]
    gecmis_noktalar = [n for _, ns in gecmis_kayit for n in ns]
    gecmis_konular = []
    for f in sorted(DIZIN.glob("s*.json"))[-12:]:
        o = json_oku(f, {})
        if o.get("tur") == "viral" and (o.get("konu") or o.get("baslik")):
            gecmis_konular.append(str(o.get("konu") or o.get("baslik")))
    govde = {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": 0.8,
             "messages": [{"role": "system", "content": ("Sen Türkçe kısa bilgi videoları yazan, animasyonla anlatan, doğruluğa önem veren bir içerik editörüsün. Yalnızca geçerli JSON döndür." if SERBEST else "Sen Türkçe 3D baskı eğitim videoları yazan, animasyonla anlatan, doğruluğa önem veren bir içerik editörüsün. Yalnızca geçerli JSON döndür.")},
                          {"role": "user", "content": ilham_ekle((AN.ISTEM_SERBEST if SERBEST else AN.ISTEM).format(konu=konu, ipucu=ipucu or "-", onceki=AN.onceki_metni(gecmis_kayit, gecmis_konular)))}]}
    for deneme in range(3):
        try:
            r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                                       headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
            with urllib.request.urlopen(r, timeout=150) as y:
                j = json.loads(json.load(y)["choices"][0]["message"]["content"])
            if SERBEST and j.get("uygunsuz"):
                SON_HATA = "konu uygun değil: " + str(j.get("uygunsuz"))[:120]
                print("Karar: " + SON_HATA)
                return None
            j["konu"] = j.get("konu") or konu
            return AN.dogrula(j, U.yazi_temizle, gecmis_noktalar, serbest=SERBEST)
        except Exception as e:
            print(f"UYARI: anlat hikâye tahtası üretimi/doğrulaması başarısız ({deneme + 1}/3): {type(e).__name__}: {str(e)[:160]}")
            if deneme == 1:
                govde["messages"].append({"role": "user", "content": "Önceki yanıt şu kurala uymadı: " + str(e)[:200] + ". Kuralları düzelterek JSON'u yeniden yaz."})
    return None


def anlat_senaryo_sec(a):
    kullanilan = set(json_oku(KULLANILAN, []))
    if a.senaryo:
        SECIM.update(tur="elle")
        return AN.dogrula(json_oku(a.senaryo, {}), U.yazi_temizle, serbest=SERBEST), pathlib.Path(a.senaryo).stem
    if a.konu:
        SECIM.update(tur="elle")
        s = anlat_senaryo_uret(a.konu, "")
        return (s, "anlat-" + slug(a.konu)) if s else (None, SON_HATA or "anlat senaryosu üretilemedi (OPENAI_API_KEY yok ya da yanıt geçersiz)")
    # öncelikli seri: shorts/viral_ayar.json içindeki "oncelikli" konular (sırayla, her biri bir kez) başarı hafızasından ve listeden önce gelir
    for k in (json_oku(AYAR, {}).get("oncelikli") or []):
        kim = "anlat-" + slug(k["konu"])
        if kim in kullanilan:
            continue
        SECIM.update(tur="seri")
        s = anlat_senaryo_uret(k["konu"], k.get("ipucu"))
        if s:
            if k.get("not"):
                s["aciklama"] = (s["aciklama"].rstrip() + "\n\n" + str(k["not"])[:300]).strip()   # ör. marka bağlantısı olmadığı notu
            return s, kim
        return None, f"'{k['konu']}' için anlat senaryosu üretilemedi"
    t = turev_sec()
    if t:
        s = anlat_senaryo_uret(t[0], t[1])
        if s:
            return s, "turev-" + slug(t[0])
        SECIM.update(tur="liste")
    for k in json_oku(VIDEO / "konular.json", []):
        kim = "anlat-" + slug(k["konu"])
        if kim in kullanilan or slug(k["konu"]) in kullanilan:
            continue
        s = anlat_senaryo_uret(k["konu"], k.get("ipucu"))
        return (s, kim) if s else (None, f"'{k['konu']}' için anlat senaryosu üretilemedi")
    return None, "kullanılmamış konu kalmadı (video/konular.json'a yeni konu ekle)"


def liste_bolumleri(ls):
    """Seslendirme ve zaman çizelgesi için bölümler: giriş, maddeler, kapanış."""
    b = [{"tip": "liste_giris", "anlati": ls["giris"]["anlati"], "ekran": "", "rozet": "", "params": {"baslik": ls["giris"]["baslik"]}, "gorsel": ls["giris"]["gorsel"]}]
    for m in ls["maddeler"]:
        b.append({"tip": "liste_madde", "anlati": m["anlati"], "ekran": "", "rozet": "", "gorsel": m["gorsel"],
                  "params": {k: m[k] for k in ("sira", "ad", "alt", "deger", "deger_yazi")}})
    b.append({"tip": "liste_kapanis", "anlati": ls["kapanis"]["anlati"], "ekran": "", "rozet": "", "params": {"ana": "TAKİP ET", "alt": "@gurtechs3d"}, "gorsel": ls["kapanis"]["gorsel"]})
    return b


def odak_bul(yol, ad):
    """Görseldeki ana nesnenin üst-orta noktasını (iğnenin halkası için) yapay zekâya sorar; olmazsa orta nokta."""
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return [.5, .45]
    try:
        kucuk = pathlib.Path(str(yol) + ".k.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(yol), "-vf", "scale=384:-1", "-q:v", "4", str(kucuk)], check=True)
        b64 = base64.b64encode(kucuk.read_bytes()).decode()
        govde = {"model": MODEL, "response_format": {"type": "json_object"},
                 "messages": [{"role": "user", "content": [
                     {"type": "text", "text": f"Bu fotoğraftaki ana nesnenin ({ad}) en üst orta noktasının konumunu ver. Yalnızca JSON: {{\"x\": 0-1 arası yatay oran, \"y\": 0-1 arası dikey oran}}"},
                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]}
        r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
        with urllib.request.urlopen(r, timeout=90) as y:
            j = json.loads(json.load(y)["choices"][0]["message"]["content"])
        return [min(.85, max(.15, float(j["x"]))), min(.62, max(.22, float(j["y"])))]
    except Exception as e:
        print(f"  (odak bulunamadı: {type(e).__name__}; orta nokta kullanılıyor)")
        return [.5, .45]


def liste_gorselleri(bolumler, dizin, kalite, hazir_dizin=None):
    """Her bölüm için konuya özel gerçekçi görsel üretir (ya da test için hazır dizinden alır). Dönen: [(yol, odak)]"""
    dizin = pathlib.Path(dizin)
    sonuc = []
    for i, b in enumerate(bolumler):
        ilerleme("Görseller üretiliyor", 10 + int(14 * i / len(bolumler)), f"{i + 1}/{len(bolumler)}")
        if hazir_dizin:
            adaylar = sorted(pathlib.Path(hazir_dizin).glob("*.jpg")) + sorted(pathlib.Path(hazir_dizin).glob("*.png"))
            yol = adaylar[i % len(adaylar)]
            sonuc.append((str(yol.resolve()), [.5, .45]))
            continue
        yol = dizin / f"g{i}.png"
        b64 = U.gorsel_uret(GORSEL_SABLONU.format(sahne=b["gorsel"]), kalite)
        yol.write_bytes(base64.b64decode(b64))
        ad = (b["params"].get("ad") if b["tip"] == "liste_madde" else "") or b["gorsel"][:60]
        sonuc.append((str(yol.resolve()), odak_bul(yol, ad) if b["tip"] == "liste_madde" else [.5, .45]))
    return sonuc
# =====================================================================================================

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


def sessiz_kesim(x, hedef, yaricap=0.7):
    """Tahmini sahne sınırı (hedef, sn) çevresinde konuşmanın en sessiz noktasını bulur: kesim kelimenin ortasına denk gelmesin (son söz bölünmesin).
    Eşik altı sessizlik varsa hedefe en yakın olanın ortasını, yoksa en sessiz 80 ms'yi seçer."""
    blok = SES.SR // 50                       # 20 ms
    n = len(x) // blok
    r = np.sqrt((x[:n * blok].reshape(n, blok) ** 2).mean(axis=1))
    pen = np.convolve(r, np.ones(4) / 4, mode="same")   # 80 ms kayan ortalama
    h = hedef * 50
    a, b = int(max(0, h - yaricap * 50)), int(min(n - 1, h + yaricap * 50))
    if b <= a:
        return float(min(max(hedef, 0.0), len(x) / SES.SR))
    esik = max(r.max() * 0.04, 1e-4)
    aday = [i for i in range(a, b + 1) if pen[i] < esik]
    if aday:
        # hedefe en yakın sessiz bölge; o bölgenin (bitişik kareler) ortası
        en_yakin = min(aday, key=lambda i: abs(i - h))
        sol = en_yakin
        while sol - 1 >= 0 and pen[sol - 1] < esik:
            sol -= 1
        sag = en_yakin
        while sag + 1 < n and pen[sag + 1] < esik:
            sag += 1
        return float((sol + sag + 1) / 2 * 0.02)
    i = a + int(np.argmin(pen[a:b + 1]))
    return float((i + 0.5) * 0.02)


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
        kes.append(max(kes[-1] + 0.6, sessiz_kesim(x, bas[ilk[k]])))   # tahmini sahne başlangıcı çevresindeki en sessiz nokta (kelime ortasında kesilmez)
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
        cikti.append({"t0": round(t0, 3), "t1": round(max(t1, t0 + 0.3), 3), "kelimeler": [{"k": x["k"], "t0": round(x["t0"], 3), "t1": round(x["t1"], 3), "v": x.get("v", 0)} for x in p]})
    return cikti


GECIS_ARASI = 0.5      # son kelimeden sahne sınırına kadar (geçiş efektleri bu aralıkta, konuşmadan SONRA çalar)
KAPANIS_KUYRUGU = 2.4  # son kelimeden videonun sonuna (müzik konuşma bitince yavaşça söner)


def konusma_sonu(v, kel):
    """Sahne konuşmasının bittiği an (sahne dilimi başına göre sn): sesten ölçülür, ses yoksa kelime uzunluğundan tahmin edilir."""
    if v.get("ses") is not None and len(v["ses"]) > SES.SR * 0.5:
        x = np.abs(v["ses"])
        blok = SES.SR // 100
        n = len(x) // blok
        r = x[:n * blok].reshape(n, blok).max(axis=1)
        esik = max(r.max() * 0.02, 1e-4)   # -34 dB: son hecenin sönen kuyruğu da konuşma sayılır
        idx = np.nonzero(r > esik)[0]
        if len(idx):
            return float(min(v["sure"], (idx[-1] + 1) * 0.01 + 0.12))   # +0,12 sn güvenlik payı
    son = v["baslangic"][-1] + 0.1 + 0.058 * len(kel[-1])
    return float(min(v["sure"], son))


def cizelge_kur(senaryo, sesler, alt_kelime=5, alt_harf=30):
    t, sahneler, kelimeler, parcalar_ses = 0.0, [], [], []
    n = len(senaryo["sahneler"])
    for i, (s, v) in enumerate(zip(senaryo["sahneler"], sesler)):
        kel = s["anlati"].split()
        v0 = t + (0.6 if i == 0 else 0.25)   # sonraki sahnenin konuşması sınırdan 0,25 sn sonra başlar: geçiş efektinin zirvesi konuşmanın üstüne binmesin
        ses_son = v0 + konusma_sonu(v, kel)
        t1 = ses_son + (KAPANIS_KUYRUGU if i == n - 1 else GECIS_ARASI)
        son_rel = konusma_sonu(v, kel)
        for k, (w, b) in enumerate(zip(kel, v["baslangic"])):
            bitis = v["baslangic"][k + 1] if k + 1 < len(kel) else son_rel   # son kelime: gerçek konuşma sonu (dilimin sessiz kuyruğu değil)
            kelimeler.append({"k": w, "t0": v0 + b, "t1": v0 + max(bitis - 0.02, b + 0.08), "sahne": i})
        if v["ses"] is not None:
            parcalar_ses.append((v0, v["ses"]))
        sahneler.append({"tip": s["tip"], "t0": round(t, 3), "t1": round(t1, 3), "ekran": s.get("ekran", ""), "rozet": s.get("rozet", ""), "params": dict(s.get("params") or {}), "ses_son": round(ses_son, 3)})
        t = t1
    plan = {"genislik": GENISLIK, "yukseklik": YUKSEKLIK, "fps": FPS, "sure": round(t, 3), "sahneler": sahneler, "altyazi": parcala_altyazi(kelimeler, alt_kelime, alt_harf)}
    return plan, parcalar_ses


GECISLER = ["kay", "yakin", "daire", "cevir", "parlama"]


def anlat_cizelge_kur(senaryo, sesler, alt_kelime=5, alt_harf=30):
    """Anlat biçimi: sahne süreleri konuşmaya göre; geçiş efekti çeşitli; bölüm etiketleri, başlık kartları, vurgulu alt yazı ve ses efekti olayları."""
    tohum = int(hashlib.md5(senaryo["konu"].encode()).hexdigest()[:6], 16)
    t, sahneler, kelimeler, parcalar_ses, bolumler, basliklar, olaylar = 0.0, [], [], [], [], [], []
    n = len(senaryo["sahneler"])
    for i, (s, v) in enumerate(zip(senaryo["sahneler"], sesler)):
        kel = s["anlati"].split()
        v0 = t + (0.6 if i == 0 else 0.25)
        son_rel = konusma_sonu(v, kel)
        ses_son = v0 + son_rel
        t1 = max(ses_son + (KAPANIS_KUYRUGU if i == n - 1 else GECIS_ARASI), t + AN.EN_AZ_SURE.get(s["tip"], 3.4))   # animasyon bitebilsin diye sahne en az bu kadar sürer
        for k, (w, b) in enumerate(zip(kel, v["baslangic"])):
            bitis = v["baslangic"][k + 1] if k + 1 < len(kel) else son_rel
            kelimeler.append({"k": w, "t0": v0 + b, "t1": v0 + max(bitis - 0.02, b + 0.08), "sahne": i, "v": s["isaret"][k] if k < len(s["isaret"]) else 0})
        if v["ses"] is not None:
            parcalar_ses.append((v0, v["ses"]))
        sahneler.append({"tip": s["tip"], "t0": round(t, 3), "t1": round(t1, 3), "params": dict(s.get("params") or {}), "etiketler": list(s.get("etiketler") or []), "anlati": s.get("anlati", ""), "nokta": s.get("nokta", ""),
                         "gecis": GECISLER[(tohum + i * 2) % 5] if i else "kay", "ses_son": round(ses_son, 3)})
        if s.get("bolum"):
            if bolumler:
                bolumler[-1]["t1"] = round(t, 3)
            bolumler.append({"no": len(bolumler) + 1, "ad": s["bolum"], "t0": round(t, 3), "t1": 0})
        if s.get("baslik"):
            basliklar.append({"t": round(v0 + 0.5, 3), "metin": s["baslik"], "sure": 1.2})
            olaylar.append((round(v0 + 0.5, 3), "darbe"))
        for k in range(len(s.get("etiketler") or [])):
            olaylar.append((round(t + 1.0 + k * 0.9, 3), "pop"))
        if i:
            olaylar.append((round(t, 3), "gecis"))
        t = t1
    if bolumler:
        bolumler[-1]["t1"] = round(t, 3)
    son_ton = json_oku(NOKTALAR, {}).get("son_ton")
    ix = tohum % len(TONLAR)
    if TONLAR[ix] == son_ton:
        ix = (ix + 3) % len(TONLAR)   # art arda iki videoda aynı renk tonu olmasın
    plan = {"konu": senaryo.get("konu", ""), "genislik": GENISLIK, "yukseklik": YUKSEKLIK, "fps": FPS, "sure": round(t, 3), "sahneler": sahneler, "bolumler": bolumler, "basliklar": basliklar,
            "altyazi": parcala_altyazi(kelimeler, alt_kelime, alt_harf), "olaylar": sorted(olaylar), "ton": TONLAR[ix], "tema_kaydir": (tohum >> 4) % 5}
    return plan, parcalar_ses


def genel_liste(sh):
    """Çizim kullanılamazsa serbest konudaki özel sahne yerine, anlatıdan çıkarılan 3 maddelik genel liste sahnesi."""
    parca = [x.strip(" ,;") for x in re.split(r"[.,;!?]", str(sh.get("anlati") or "")) if len(x.strip()) > 3][:3]
    return {"maddeler": [q[:28] for q in parca] if len(parca) >= 2 else [str(sh.get("nokta") or "Önemli nokta")[:28], "Dikkat et"]}


def ozel_tasarla(sahne, konu, sure, elestiri="", onceki=None):
    """Serbest konudaki bir özel sahnenin DETAYLI çizimini ayrı bir 'ressam' çağrısıyla yazar (ozel_params biçiminde); elestiri verilirse önceki çizimi düzeltir. Başarısızsa None."""
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    istem = AN.ISTEM_TASARIM.format(konu=konu, anlati=sahne.get("anlati", ""), tasarim=(sahne.get("params") or {}).get("tasarim_notu", "") or sahne.get("nokta", ""), sure=int(round(sure)))
    if elestiri and onceki:
        istem += "\n\nÖNCEKİ ÇİZİMİN ELEŞTİRİSİ (düzelt, daha DETAYLI ve katmanlı yap; ögeler okunur, ekran içinde olsun): " + str(elestiri)[:300] + "\nÖnceki çizim (özet): " + json.dumps({"elemanlar": [{k: v for k, v in e.items() if k in ("tur", "x", "y", "metin", "ad")} for e in (onceki.get("elemanlar") or [])[:30]]}, ensure_ascii=False)[:1500]
    govde = {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": 0.7, "messages": [
        {"role": "system", "content": "Sen detaylı, katmanlı düz illüstrasyon tarzında hareketli grafik tasarlayan bir ressamsın. Yalnızca geçerli JSON döndür."}, {"role": "user", "content": istem}]}
    for deneme in range(2):
        try:
            r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
            with urllib.request.urlopen(r, timeout=240) as y:
                j = json.loads(json.load(y)["choices"][0]["message"]["content"])
            p = AN.ozel_params({**j, "yedek": "kontrol_listesi"})
            if p["eleman_sayisi"] < 16:
                raise ValueError(f"çizim yetersiz detaylı ({p['eleman_sayisi']} eleman; en az 16 gerekli)")
            p["tasarim_notu"] = (sahne.get("params") or {}).get("tasarim_notu", "")
            return p
        except Exception as e:
            print(f"UYARI: özel sahne çizimi başarısız ({deneme + 1}/2): {type(e).__name__}: {str(e)[:140]}")
            if deneme == 0:
                govde["messages"].append({"role": "user", "content": "Önceki yanıt kullanılamadı: " + str(e)[:200] + ". Biçime uyarak JSON'u yeniden yaz; en az 24 eleman."})
    return None


def serbest_tasarla(senaryo):
    """Serbest konuda her özel sahne için çizimi (ressam çağrısı) üretir; olmazsa o sahne genel listeye döner. Dönen: yedeğe düşen sahne sayısı."""
    dusen = 0
    ozeller = [i for i, x in enumerate(senaryo["sahneler"]) if x["tip"] == "ozel"]
    for n, i in enumerate(ozeller):
        sh = senaryo["sahneler"][i]
        ilerleme("Özel sahneler çiziliyor", 6 + int(2 * n / max(1, len(ozeller))), f"{n + 1}/{len(ozeller)}", zorla=True)
        sure = max(6.0, len(sh["anlati"].split()) / 2.3 + 1.0)
        p = ozel_tasarla(sh, senaryo["konu"], sure)
        if p:
            sh["params"] = p
            print(f"Özel sahne {i + 1} çizildi: {p['eleman_sayisi']} eleman")
        else:
            sh["tip"], sh["params"] = "kontrol_listesi", genel_liste(sh)
            dusen += 1
            print(f"Özel sahne {i + 1}: çizim üretilemedi → genel liste sahnesi")
    # ardışık aynı tip oluşmasın (düşen sahne komşusuyla aynı tip olabilir)
    for i in range(1, len(senaryo["sahneler"])):
        if senaryo["sahneler"][i]["tip"] == senaryo["sahneler"][i - 1]["tip"] == "kontrol_listesi":
            senaryo["sahneler"][i]["tip"], senaryo["sahneler"][i]["params"] = "sayi", {"deger": 100, "maks": 100, "birim": "%", "etiket": str(senaryo["sahneler"][i].get("nokta") or "")[:34]}
    return dusen


def ozel_kontrol(plan, dizin, plan_yolu):
    """Özel (yapay zekâ tarifli) sahnelerden birkaç kare çizip görsel modele gösterir; boş/bozuk/okunmaz ise sahneyi 'yedek' hazır tiple değiştirir.
    Serbest konuda ayrıca DETAY puanı istenir; yetersizse ressam çağrısı eleştiriyle bir kez yeniden çizer."""
    anahtar = os.environ.get("OPENAI_API_KEY")
    degisen = 0
    if not anahtar:
        return 0

    def bak(i, sh, tur):
        d = sh["t1"] - sh["t0"]
        ts = [round(sh["t0"] + d * f, 2) for f in (0.3, 0.6, 0.95)]
        klasor = pathlib.Path(dizin) / f"onizleme{i}_{tur}"
        r = subprocess.run([os.environ.get("NODE") or "node", str(VIDEO / "render.js"), str(plan_yolu), "--kareler", ",".join(map(str, ts)), "--dizin", str(klasor), "--olcek", "0.3"],
                           cwd=str(VIDEO), capture_output=True, text=True)
        kareler = sorted(klasor.glob("k_*.jpg"), key=lambda f: float(f.stem[2:].replace("_", ".")))
        if r.returncode != 0 or len(kareler) < 3:
            return False, "önizleme çizilemedi: " + (r.stderr or "")[-120:], 0
        try:
            soru = ("Bu 3 kare, " + ("bir bilgi videosundaki" if SERBEST else "3D yazıcı hakkında bir") + " animasyon sahnesinin farklı anlarıdır (dikey video). Sahne: " + str(sh.get("params", {}).get("yedek", "")) + ". Değerlendir: sahne boş ya da neredeyse boş mu, yazılar okunamıyor ya da üst üste biniyor mu, ögeler ekran dışına taşıyor ya da çok küçük/bozuk mu, kareler arasında hareket var mı?"
                    + (" AYRICA DETAY: arka plan, ana nesnelerin ayrıntıları (parçalar, gölge, renk geçişi), katmanlar ve süreç hareketi var mı (1-10; 6 altı = çok sade/boş/genel)? Sahne anlatısı: " + str(sh.get("anlati", ""))[:200] if SERBEST else "")
                    + " Yalnızca JSON: {\"gecti\": true/false, \"sorun\": \"kısa, somut\"" + (", \"detay\": 1-10" if SERBEST else "") + "}. Küçük kusurlar için true de.")
            icerik = [{"type": "text", "text": soru}]
            for k in kareler:
                icerik.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(k.read_bytes()).decode()}})
            govde = {"model": MODEL, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": icerik}]}
            rq = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
            with urllib.request.urlopen(rq, timeout=120) as y:
                j = json.loads(json.load(y)["choices"][0]["message"]["content"])
            try:
                detay = float(j.get("detay"))
            except (TypeError, ValueError):
                detay = 10.0
            gecti = bool(j.get("gecti")) and (detay >= 6 or not SERBEST)
            return gecti, str(j.get("sorun") or "")[:140] + (f" (detay {detay:g}/10)" if SERBEST else ""), detay
        except Exception as e:
            print(f"UYARI: özel sahne kontrolü yapılamadı ({type(e).__name__}); sahne korunuyor.")
            return True, "", 10.0

    for i, sh in enumerate(plan["sahneler"]):
        if sh["tip"] != "ozel":
            continue
        gecti, sorun, _ = bak(i, sh, "a")
        if not gecti and SERBEST:   # bir kez eleştiriyle yeniden çiz
            yeni = ozel_tasarla(sh, plan.get("konu", ""), sh["t1"] - sh["t0"], elestiri=sorun, onceki=sh.get("params"))
            if yeni:
                sh["params"] = yeni
                yaz(plan_yolu, plan)
                gecti, sorun, _ = bak(i, sh, "b")
                print(f"Özel sahne {i + 1}: yeniden çizildi ({yeni['eleman_sayisi']} eleman)")
        print(f"Özel sahne {i + 1}: {'GEÇTİ' if gecti else 'GEÇMEDİ → yedek sahne'} {sorun}")
        if not gecti:
            if SERBEST:
                sh["tip"], sh["params"] = "kontrol_listesi", genel_liste(sh)
            else:
                sh["tip"], sh["params"] = (sh.get("params") or {}).get("yedek") or "ekstruder", {}
            degisen += 1
    return degisen


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
    etiket = " ".join(f"#{e}" for e in dict.fromkeys(s["etiketler"] + (["shorts"] if SERBEST else ["3dprinting", "3dbaski", "shorts"])))[:300]
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
    if not (a.hemen or a.senaryo or a.konu):
        # zamanlanmış çalışma: sunucu yeniden başlayınca tetik tekrarlanabilir; bugün (TR) zaten bir viral video üretildiyse üretme
        bugun = H.simdi().astimezone(H.TR).strftime("%Y-%m-%d")
        for f in DIZIN.glob("s*.json"):
            o = json_oku(f, {})
            try:
                gun = datetime.datetime.fromisoformat(str(o.get("olusturma", "")).replace("Z", "+00:00")).astimezone(H.TR).strftime("%Y-%m-%d")
            except Exception:
                continue
            if o.get("tur") == "viral" and gun == bugun:
                print(f"Karar: bekle (bugün zaten bir viral video üretildi: {o.get('id')}; zamanlanmış çalışma ikinciyi üretmez)")
                ilerleme("beklemede", 100, "bugün zaten bir viral video üretildi", zorla=True)
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
    global SERBEST
    SERBEST = a.konu_turu == "serbest" or (bool(a.konu) and a.konu_turu in (None, "", "otomatik") and not konu_3d_mu(a.konu))
    if SERBEST:
        print("Konu türü: SERBEST (3D baskı dışı); genel sahne kalıpları kullanılacak")
    bicim = a.bicim or ayar.get("bicim") or "anlat"
    if SERBEST and bicim != "anlat":
        bicim = "anlat"
    if a.senaryo and "maddeler" in json_oku(a.senaryo, {}):
        bicim = "liste"
    try:
        if bicim == "anlat":
            senaryo, kaynak = anlat_senaryo_sec(a)
        elif bicim == "liste":
            ls, kaynak = liste_senaryo_sec(a)
            senaryo = None
            if ls:
                senaryo = {"bicim": "liste", "konu": ls["konu"], "baslik": ls["baslik"], "aciklama": ls["aciklama"], "etiketler": ls["etiketler"], "sahneler": liste_bolumleri(ls), "liste": ls}
        else:
            senaryo, kaynak = senaryo_sec(a, ayar)
    except ValueError as e:
        return hata(f"senaryo geçersiz: {e}")
    if not senaryo:
        print(f"Karar: bekle ({kaynak})")
        ilerleme("beklemede", 100, kaynak, zorla=True)
        return 0
    print(f"Konu: {senaryo['konu']} ({kaynak}); {len(senaryo['sahneler'])} sahne")
    ilerleme("Senaryo hazır", 5, senaryo["konu"][:100], zorla=True)
    if SERBEST and senaryo.get("bicim") == "anlat":
        serbest_tasarla(senaryo)
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
    if senaryo.get("bicim") == "liste":
        ls = senaryo["liste"]
        plan, parcalar = cizelge_kur(senaryo, sesler, 11, 64)
        plan.update(sayfa="liste.html", bicim="liste", baslik_ust=ls["liste_basligi"], toplam=len(ls["maddeler"]), olcu=ls["olcu"], tohum=int(hashlib.md5(ls["konu"].encode()).hexdigest()[:6], 16))
    elif senaryo.get("bicim") == "anlat":
        plan, parcalar = anlat_cizelge_kur(senaryo, sesler)
        plan.update(sayfa="anlat.html", bicim="anlat", tohum=int(hashlib.md5(senaryo["konu"].encode()).hexdigest()[:6], 16))
    else:
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
        if plan.get("bicim") == "liste":
            gorseller = liste_gorselleri(senaryo["sahneler"], g, ayar.get("gorsel_kalitesi") or "medium", a.gorsel_dizin)
            for sh, (yol, odak) in zip(plan["sahneler"], gorseller):
                sh["params"]["gorsel"], sh["params"]["odak"] = "file://" + yol, odak
        yaz(g / "plan.json", plan)
        if plan.get("bicim") == "anlat" and any(sh["tip"] == "ozel" for sh in plan["sahneler"]):
            ilerleme("Özel sahneler kontrol ediliyor", 23, "", zorla=True)
            if ozel_kontrol(plan, g, g / "plan.json"):
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
        taslak = {"id": kimlik, "olusturma": z.strftime("%Y-%m-%dT%H:%M:%SZ"), "durum": "otomatik" if a.otomatik else "onay_bekliyor", "tur": "viral", "video": "" if a.otomatik else f"videolar/{cikti.name}", "sure": round(plan["sure"], 1),
                  "baslik": senaryo["baslik"], "aciklama": aciklama_olustur(senaryo, gercek), "muzik": "Sentez (kodla üretildi)", "konu": senaryo["konu"], "tasarimlar": [], "hikayeler": [], "secim": dict(SECIM),
                  "zamanlama": [{"tip": x["tip"], "t0": x["t0"], "t1": x["t1"], "ses_son": x.get("ses_son")} for x in plan["sahneler"]]}   # sahne/konuşma zamanları: ses sorunlarını sonradan ayıklamak için
        if SERBEST:
            taslak["serbest"] = True
            taslak["anlati"] = " ".join(x["anlati"] for x in senaryo["sahneler"])[:1500]
        if a.otomatik:
            taslak["otomatik"] = True
            taslak["anlati"] = " ".join(x["anlati"] for x in senaryo["sahneler"])[:1500]
        yaz(DIZIN / f"{kimlik}.json", taslak)
        if a.sonuc_dosyasi:
            yaz(a.sonuc_dosyasi, {"id": kimlik, "baslik": senaryo["baslik"], "aciklama": taslak["aciklama"], "konu": senaryo["konu"], "sure": round(plan["sure"], 1), "anlati": " ".join(x["anlati"] for x in senaryo["sahneler"]),
                                  "sahneler": [x["tip"] for x in plan["sahneler"]], "noktalar": [x.get("nokta") for x in senaryo["sahneler"] if x.get("nokta")], "video": str(cikti)})
        yaz(KULLANILAN, sorted(set(json_oku(KULLANILAN, [])) | {kaynak}))
        if plan.get("bicim") == "anlat":
            hafiza = json_oku(NOKTALAR, {})
            hafiza.setdefault("videolar", []).append({"id": kimlik, "konu": senaryo["konu"], "noktalar": [x.get("nokta") for x in senaryo["sahneler"] if x.get("nokta")]})
            hafiza["videolar"] = hafiza["videolar"][-40:]
            hafiza["son_ton"] = plan.get("ton")
            yaz(NOKTALAR, hafiza)
        print(f"Taslak hazır: {kimlik}; başlık: {senaryo['baslik']}")
        if a.git:
            H.git_kaydet(f"Viral video: {kimlik} taslağı ({senaryo['konu'][:60]})", [DIZIN] if a.otomatik else [DIZIN, KOK / "videolar"])
            ilerleme("Hazır", 100, senaryo["baslik"][:100], zorla=True)
            if not a.otomatik:
                H.bildir("Yeni viral video taslağı hazır", f"{senaryo['baslik']} — panelde onayını bekliyor.", adres="/", etiket="shorts")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konu", help="belirli bir konu (hazır senaryo yoksa yapay zekâ yazar)")
    ap.add_argument("--senaryo", help="senaryo JSON dosyası")
    ap.add_argument("--konu-turu", dest="konu_turu", choices=["otomatik", "3d", "serbest"], help="elle yazılan konunun türü: otomatik (3D baskı sözcükleri varsa 3d, yoksa serbest), 3d ya da serbest (3D baskı dışı)")
    ap.add_argument("--hemen", action="store_true", help="kapalı ya da taslak limiti dolu olsa bile bir kez üret")
    ap.add_argument("--git", action="store_true", help="sonucu depoya yaz ve it")
    ap.add_argument("--olcek", type=float, default=1.0, help="çizim ölçeği (test için 0.5)")
    ap.add_argument("--cikti", help="videoyu bu dosyaya yaz (taslak kaydı oluşturmaz, --git ile birlikte kullanılmadıkça)")
    ap.add_argument("--tts-dizin", help="test: önceden üretilmiş konuşma dizini (s0.wav, s0.json…)")
    ap.add_argument("--sessiz", action="store_true", help="test: seslendirme olmadan (tahmini zamanlama)")
    ap.add_argument("--plan-kaydet", help="plan.json'u bu yola da yaz")
    ap.add_argument("--bicim", choices=["anlat", "liste", "3d"], help="video biçimi: anlat (çeşitli animasyonlu sahneler, varsayılan), liste (geri sayım + gerçekçi görseller) ya da 3d")
    ap.add_argument("--gorsel-dizin", help="test: görsel üretmek yerine bu dizindeki görselleri kullan")
    ap.add_argument("--otomatik", action="store_true", help="otomatik hat: video depoya yazılmaz (--cikti ile dışarı), taslak kaydı 'otomatik' durumunda açılır, yalnızca küçük kayıt dosyaları commit edilir")
    ap.add_argument("--sonuc-dosyasi", help="üretim sonucunu (taslak kimliği, başlık, anlatı…) bu JSON dosyasına yaz")
    try:
        kod = calis(ap.parse_args())
    except Exception as e:
        ilerleme("Hata", 100, f"{type(e).__name__}: {str(e)[:140]}", zorla=True)
        raise
    sys.exit(kod)


if __name__ == "__main__":
    main()
