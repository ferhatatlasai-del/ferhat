#!/usr/bin/env python3
"""Anlat biçimi: yapay zekânın yazdığı "hikâye tahtası" (sahne listesi) için komut, doğrulama ve kelime vurgu işaretleri.

Hikâye tahtası = sıralı sahneler; her sahne video/anlat_sahneler.js içindeki bir animasyon tipidir (kanca, ekstruder, tikanma, karsilastir…).
Çeşitlilik kuralı: aynı tip arka arkaya gelmez, bir tip en çok iki kez kullanılır, en az 5 farklı tip bulunur; ilk sahne "kanca", son sahne "kapanis".
Anlatıdaki *kelime* turuncu, ~kelime~ mavi vurgulanır (her vurgulu kelime ayrı işaretlenir); işaretler seslendirmeye ve alt yazıya GİTMEZ.
"""
import re

TIPLER = ["kanca", "ekstruder", "sicak_uc", "katman", "tikanma", "ilk_katman", "sogutma", "nem", "stringing", "warping",
          "karsilastir", "sayi", "kontrol_listesi", "dolgu", "hiz", "destek", "kapanis"]
EN_AZ_SURE = {"tikanma": 5.0, "katman": 4.6, "sicak_uc": 4.0, "ilk_katman": 4.0, "sogutma": 4.0, "nem": 4.0, "stringing": 4.4, "warping": 4.4, "destek": 4.2,
              "karsilastir": 3.6, "sayi": 3.4, "kontrol_listesi": 4.0, "dolgu": 3.6, "hiz": 3.8, "ekstruder": 3.4, "kanca": 3.0, "kapanis": 3.4}

ISTEM = """3D yazıcı ve 3D baskı konusunda, YouTube Shorts / Instagram Reels için ~50-60 saniyelik, ANİMASYONLU ve görsel olarak ÇEŞİTLİ, TÜRKÇE bir bilgi videosunun HİKÂYE TAHTASINI yaz.
Konu: {konu}
İpucu: {ipucu}

Video, her biri bir ANİMASYON SAHNESİ olan sahnelerden oluşur. Sahne sayısını konunun gerektirdiği kadar seç (5 ile 10 arası; basit konu 5-6, çok adımlı konu 8-10 sahne).
SAHNE TİPLERİ (animasyon; tipin yanındaki params zorunlu/isteğe bağlı alanlardır):
- kanca: açılış (dönen makara, soru işaretleri). ZORUNLU ilk sahne. params: {{}}
- ekstruder: dişli filamenti nozula iter. params: {{}}
- sicak_uc: ısıtıcı blok filamenti eritir, sıcaklık sayacı. params: {{"derece": 210}}
- katman: nozul katman katman basar, katman sayacı. params: {{"sayi": 4}}  (2-6)
- tikanma: nozul tıkanması ve iğneyle açma. params: {{}}
- ilk_katman: ilk katman çok yüksek (✗) ve doğru yükseklik (✓) karşılaştırması. params: {{}}
- sogutma: parça soğutma fanı, taşan katmanlar, sıcaklık düşüşü. params: {{"bas": 230, "son": 60}}
- nem: filament nem çeker, nozulda çıtırtı/buhar. params: {{}}
- stringing: ince iplikler ve geri çekme (retraction). params: {{}}
- warping: köşelerin kalkması, sıcak tabla yapıştırır. params: {{}}
- karsilastir: iki değeri sütunla karşılaştırır. params: {{"a": {{"ad": "PLA", "deger": 210}}, "b": {{"ad": "PETG", "deger": 240}}, "birim": "°C"}}
- sayi: büyük halka sayaç. params: {{"deger": 65, "maks": 100, "birim": "%", "etiket": "kısa açıklama"}}
- kontrol_listesi: onay işaretli madde listesi (özet için). params: {{"maddeler": ["en çok 28 harf", "...", "..."]}}  (3-4 madde)
- dolgu: dolgu yoğunluğu animasyonu. params: {{"yuzde": 20}}
- hiz: baskı hızı ve titreşim (ringing). params: {{"hiz": 220}}
- destek: destek yapısı ve sarkma. params: {{}}
- kapanis: son sahne (takip et). ZORUNLU son sahne. params: {{}}

ÇEŞİTLİLİK KURALLARI: Konuya UYAN tipleri seç ve her sahneyi bir fikre ayır. Aynı tip arka arkaya gelmesin, bir tip en çok 2 kez kullanılsın, en az 5 farklı tip olsun. Konuyla ilgisi olmayan sahneyi zorla koyma.
ANLATI: sahne başına 1-2 kısa cümle (8-22 kelime), toplam 110-150 kelime. İlk sahne güçlü kanca (soru ya da yaygın hata). Cümleler kısa, konuşma dili, "sen" hitabı. Son sahne yoruma davet + takip et.
VURGU: anlatıda önemli kelimeleri işaretle: *kelime* turuncu, ~kelime~ mavi. Her sahnede en çok 2 vurgu; çok kelimeli vurguda HER kelimeyi ayrı işaretle (*katman* *katman*). Noktalama işaret dışında kalabilir ("*eritir*.").
EK ALANLAR (isteğe bağlı): "bolum": yeni bir bölüm başlıyorsa kısa başlık (en çok 28 harf; toplam 3-5 bölüm, ilk sahnede olmasın, "kanca"ya yazma); "baslik": ekrana büyük yazı olarak zıplayan TEK kısa kelime (en çok 10 harf, tüm videoda en çok 2 sahnede, örn. "ERİR!"); "etiketler": sahnedeki animasyon parçasını anlatan 0-2 kısa etiket (en çok 24 harf, örn. "210 °C", "0,4 mm nozul").
DOĞRULUK: Yalnızca 3D baskı topluluğunda yaygın kabul gören, doğru bilgileri yaz. Emin olmadığın sayı verme; sıcaklık/hızda tipik değer ya da aralık kullan. Marka karşılaştırması, fiyat, istatistik, kişisel deneyim UYDURMA. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları anlatıda yazıyla yaz ("iki yüz on derece"); PLA/PETG gibi kısaltmaları büyük harfle yaz.
YALNIZCA JSON döndür: {{"konu":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["3dprinting","..."],
"sahneler":[{{"tip":"kanca","anlati":"...","bolum":"","baslik":"","etiketler":[],"params":{{}}}}]}}"""


def isaretle(metin):
    """'*eritir*.' / '~katman~' işaretli anlatıyı (düz metin, kelime başına bayrak listesi) olarak ayırır. Bayrak: 0 normal, 1 turuncu, 2 mavi."""
    kel, bayrak = [], []
    for tok in str(metin or "").split():
        v = 1 if "*" in tok else 2 if "~" in tok else 0
        t = tok.replace("*", "").replace("~", "")
        if t:
            kel.append(t)
            bayrak.append(v)
    return kel, bayrak


def _sayi(v, varsayilan, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = float(varsayilan)
    return max(lo, min(hi, f))


def _kisa(v, n):
    return re.sub(r"\s+", " ", "".join(c for c in str(v or "") if c.isprintable() and c not in "<>{}")).strip()[:n]


def params_temizle(tip, p):
    p = p if isinstance(p, dict) else {}
    if tip == "sicak_uc":
        return {"derece": int(_sayi(p.get("derece"), 210, 100, 320))}
    if tip == "katman":
        return {"sayi": int(_sayi(p.get("sayi"), 4, 2, 6))}
    if tip == "sogutma":
        return {"bas": int(_sayi(p.get("bas"), 230, 100, 320)), "son": int(_sayi(p.get("son"), 60, 20, 200))}
    if tip == "karsilastir":
        a, b = (p.get("a") if isinstance(p.get("a"), dict) else {}), (p.get("b") if isinstance(p.get("b"), dict) else {})
        return {"a": {"ad": _kisa(a.get("ad") or "A", 10), "deger": _sayi(a.get("deger"), 60, 0, 100000)}, "b": {"ad": _kisa(b.get("ad") or "B", 10), "deger": _sayi(b.get("deger"), 40, 0, 100000)},
                "birim": _kisa(p.get("birim"), 8)}
    if tip == "sayi":
        return {"deger": _sayi(p.get("deger"), 65, 0, 100000), "maks": _sayi(p.get("maks"), 100, 1, 100000), "birim": _kisa(p.get("birim") or "%", 8), "etiket": _kisa(p.get("etiket"), 34)}
    if tip == "kontrol_listesi":
        m = [_kisa(x, 28) for x in (p.get("maddeler") or []) if _kisa(x, 28)][:4]
        return {"maddeler": m if len(m) >= 2 else ["Ayarı kontrol et", "Küçük bir deneme yap", "Sonucu karşılaştır"]}
    if tip == "dolgu":
        return {"yuzde": int(_sayi(p.get("yuzde"), 20, 5, 100))}
    if tip == "hiz":
        return {"hiz": int(_sayi(p.get("hiz"), 220, 20, 500))}
    return {}


def dogrula(s, temizle=lambda x: x):
    """Hikâye tahtasını temizler; sorun varsa ValueError. temizle: metin temizleyici (U.yazi_temizle)."""
    sah = [x for x in (s.get("sahneler") or []) if isinstance(x, dict)]
    if not 5 <= len(sah) <= 12:
        raise ValueError(f"sahne sayısı 5-12 olmalı ({len(sah)})")
    temiz, onceki, sayac = [], None, {}
    for i, x in enumerate(sah):
        tip = x.get("tip")
        if tip not in TIPLER:
            raise ValueError(f"{i + 1}. sahne tipi geçersiz: {tip}")
        if tip == onceki:
            raise ValueError(f"{i + 1}. sahne bir öncekiyle aynı tip ({tip}); çeşitlilik gerekli")
        sayac[tip] = sayac.get(tip, 0) + 1
        if sayac[tip] > 2:
            raise ValueError(f"'{tip}' tipi 2'den fazla kullanılmış")
        onceki = tip
        kel, bayrak = isaretle(" ".join(str(x.get("anlati") or "").split()))
        if len(kel) < 4:
            raise ValueError(f"{i + 1}. sahnede anlatı yok ya da çok kısa")
        et = [_kisa(e, 24) for e in (x.get("etiketler") or []) if _kisa(e, 24)][:2] if isinstance(x.get("etiketler"), list) else []
        temiz.append({"tip": tip, "anlati": " ".join(kel), "isaret": bayrak, "params": params_temizle(tip, x.get("params")), "etiketler": et,
                      "bolum": _kisa(temizle(str(x.get("bolum") or "")), 28) if i > 0 and tip != "kanca" else "", "baslik": _kisa(temizle(str(x.get("baslik") or "")), 10) if tip != "kanca" else ""})
    if temiz[0]["tip"] != "kanca":
        raise ValueError("ilk sahne 'kanca' olmalı")
    if temiz[-1]["tip"] != "kapanis":
        raise ValueError("son sahne 'kapanis' olmalı")
    if len(sayac) < 5:
        raise ValueError(f"en az 5 farklı sahne tipi gerekli ({len(sayac)})")
    kelime = sum(len(x["anlati"].split()) for x in temiz)
    if not 90 <= kelime <= 190:
        raise ValueError(f"anlatı {kelime} kelime; 90-190 olmalı")
    # en çok 2 büyük başlık kartı
    sirali = [x for x in temiz if x["baslik"]]
    for x in sirali[2:]:
        x["baslik"] = ""
    return {"bicim": "anlat", "konu": str(s.get("konu") or "")[:140], "baslik": temizle(str(s.get("baslik") or ""))[:90],
            "aciklama": str(s.get("aciklama") or "")[:900].replace("http", ""),
            "etiketler": [re.sub(r"[^a-z0-9ığüşöç]", "", str(e).lower()) for e in (s.get("etiketler") or [])][:8], "sahneler": temiz}
