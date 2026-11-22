#!/usr/bin/env python3
"""Anlat biçimi: yapay zekânın yazdığı "hikâye tahtası" (sahne listesi) için komut, doğrulama ve kelime vurgu işaretleri.

Hikâye tahtası = sıralı sahneler; her sahne video/anlat_sahneler.js içindeki bir animasyon tipidir (kanca, ekstruder, tikanma, karsilastir…).
Çeşitlilik kuralı: aynı tip arka arkaya gelmez, bir tip en çok iki kez kullanılır, en az 5 farklı tip bulunur; ilk sahne "kanca", son sahne "kapanis".
Anlatıdaki *kelime* turuncu, ~kelime~ mavi vurgulanır (her vurgulu kelime ayrı işaretlenir); işaretler seslendirmeye ve alt yazıya GİTMEZ.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    import basari as B   # kelime benzerliği (aynı noktayı tekrar anlatmayı yakalamak için)
except Exception:   # pragma: no cover
    B = None

TIPLER = ["ozel", "kanca", "ekstruder", "sicak_uc", "katman", "tikanma", "ilk_katman", "sogutma", "nem", "stringing", "warping",
          "karsilastir", "sayi", "kontrol_listesi", "dolgu", "hiz", "destek", "kapanis"]
EN_AZ_SURE = {"ozel": 4.2, "tikanma": 5.0, "katman": 4.6, "sicak_uc": 4.0, "ilk_katman": 4.0, "sogutma": 4.0, "nem": 4.0, "stringing": 4.4, "warping": 4.4, "destek": 4.2,
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
- ozel: SENİN bu konu için ÖZEL TASARLADIĞIN sahne (hazır şablonlar konuyu anlatmaya yetmediğinde; videonun en ayırt edici kavramı için). params: {{"yedek": "ekstruder", "tema": "mavi", "kamera": [[540,760,1.0],[540,760,1.1]], "elemanlar": [...], "etiket_noktalari": []}}
  "yedek": çizim bozuk çıkarsa yerine kullanılacak hazır tip. Koordinat: yatay 0-1080, dikey 350-1250 görünür alan (merkez 540,760). Elemanlar alttan üste sırayla çizilir; olayları zamanla (önce parçalar belirir, sonra oklar ve yazılar). Bir özel sahnede 6-18 eleman; yazılar kısa (en çok 24 harf) ve üst üste binmesin.
  Eleman: {{"tur": ..., alanlar, "t": [giriş_sn, çıkış_sn] (isteğe bağlı), "hareket": [{{"o": "x|y|olcek|donus|opaklik|w|h|doluluk|cizim", "den": a, "a": b, "t0": sn, "t1": sn, "egri": "yumusak|ziplama|cikis|lineer"}}], "dongu": {{"titre": n, "yuz": n, "dondur": n, "salin": n, "nabiz": n}}}}
  turler: dikdortgen {{x,y,w,h,r,renk,kenar,doluluk(0-1),yon:"yatay|dikey"}}; daire {{x,y,r,renk,halka,cizim}}; cizgi {{x,y,x1,y1,x2,y2,renk,kalinlik,kesikli,cizim(0-1)}}; ok (cizgi gibi, ucu ok); yazi {{x,y,metin,boyut,renk}}; ikon {{x,y,ad,olcek,renk,doluluk}}; parcacik {{x,y,w,h,sayi,yon:"yukari|asagi|sag|sol|daire",renk,boyut,hiz}}
  ikon adları: nozul, nozul_tikali, makara, disli, fan, termometre, damla, alev, duman, tik, carpi, uyari, saat, lupa, yildiz, parca, filament, yatak, kilit. Renkler: turuncu, mavi, yesil, kirmizi, sari, mor, pembe, beyaz, koyu, gri, kahve, siyah ya da #rrggbb.
  Örnek mini özel sahne: [{{"tur":"ikon","ad":"termometre","x":300,"y":760,"olcek":2.2,"doluluk":0.2,"hareket":[{{"o":"doluluk","den":0.2,"a":0.95,"t0":0.3,"t1":2.5}}]}},{{"tur":"ikon","ad":"alev","x":300,"y":1040,"olcek":1.4,"dongu":{{"nabiz":0.06}},"t":[0.3,99]}},{{"tur":"ok","x1":420,"y1":760,"x2":720,"y2":760,"renk":"sari","kalinlik":12,"hareket":[{{"o":"cizim","den":0,"a":1,"t0":1.0,"t1":1.6}}]}},{{"tur":"yazi","x":760,"y":700,"metin":"ISI YUKARI ÇIKAR","boyut":52,"renk":"sari","t":[1.6,99]}}]

ÇEŞİTLİLİK KURALLARI: Konuya UYAN tipleri seç ve her sahneyi bir fikre ayır. Aynı tip arka arkaya gelmesin, bir tip en çok 2 kez kullanılsın (ozel en çok 3), en az 5 farklı tip olsun. Konuyla ilgisi olmayan sahneyi zorla koyma. Videoda EN AZ 1, en çok 3 "ozel" sahne tasarla (ZORUNLU): bu konunun kendine özgü kavramını çizen, başka videoda kullanılamayacak sahneler; diğerleri hazır tiplerden olsun. Hazır tiplerin hepsini seçip "ozel" sahne koymazsan yanıt reddedilir.
TEKRARA DÜŞME: Her sahnenin "nokta" alanına o sahnede anlattığın TEK somut bilgiyi 3-8 kelimeyle yaz (örn. "nem nozulda buharlaşır"). Aşağıdaki, daha önceki videolarda ZATEN anlatılmış noktaları ve konuları TEKRAR ETME; aynı genel fikri farklı bir açıdan, yeni bilgiyle anlat. Bu videonun noktaları da birbirinden farklı olsun (aynı bilgiyi iki sahnede söyleme).
{onceki}
ANLATI: sahne başına 1-2 kısa cümle (8-22 kelime), toplam 110-150 kelime. İlk sahne güçlü kanca (soru ya da yaygın hata). Cümleler kısa, konuşma dili, "sen" hitabı. Son sahne yoruma davet + takip et.
VURGU: anlatıda önemli kelimeleri işaretle: *kelime* turuncu, ~kelime~ mavi. Her sahnede en çok 2 vurgu; çok kelimeli vurguda HER kelimeyi ayrı işaretle (*katman* *katman*). Noktalama işaret dışında kalabilir ("*eritir*.").
EK ALANLAR (isteğe bağlı): "bolum": yeni bir bölüm başlıyorsa kısa başlık (en çok 28 harf; toplam 3-5 bölüm, ilk sahnede olmasın, "kanca"ya yazma); "baslik": ekrana büyük yazı olarak zıplayan TEK kısa kelime (en çok 10 harf, tüm videoda en çok 2 sahnede, örn. "ERİR!"); "etiketler": sahnedeki animasyon parçasını anlatan 0-2 kısa etiket (en çok 24 harf, örn. "210 °C", "0,4 mm nozul").
DOĞRULUK: Yalnızca 3D baskı topluluğunda yaygın kabul gören, doğru bilgileri yaz. Emin olmadığın sayı verme; sıcaklık/hızda tipik değer ya da aralık kullan. Marka karşılaştırması, fiyat, istatistik, kişisel deneyim UYDURMA. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları anlatıda yazıyla yaz ("iki yüz on derece"); PLA/PETG gibi kısaltmaları büyük harfle yaz.
YALNIZCA JSON döndür: {{"konu":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["3dprinting","..."],
"sahneler":[{{"tip":"kanca","anlati":"...","nokta":"3-8 kelimelik tek bilgi","bolum":"","baslik":"","etiketler":[],"params":{{}}}}]}}"""


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


RENKLER = {"turuncu", "mavi", "yesil", "kirmizi", "sari", "mor", "pembe", "beyaz", "koyu", "gri", "kahve", "siyah"}
IKONLAR = {"nozul", "nozul_tikali", "makara", "disli", "fan", "termometre", "damla", "alev", "duman", "tik", "carpi", "uyari", "saat", "lupa", "yildiz", "parca", "filament", "yatak", "kilit"}
TURLER = {"dikdortgen", "daire", "cizgi", "ok", "yazi", "ikon", "parcacik"}
OZELLIKLER = {"x", "y", "olcek", "donus", "opaklik", "w", "h", "doluluk", "cizim", "r", "x1", "y1", "x2", "y2", "boyut", "kalinlik"}
YEDEKLER = [t for t in TIPLER if t not in ("ozel", "kanca", "kapanis")]


def _renk(v, varsayilan="beyaz"):
    v = str(v or "")
    return v if (v in RENKLER or re.fullmatch(r"#[0-9a-fA-F]{6}", v)) else varsayilan


def _sayi_alan(v, lo=-900, hi=2300):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, f)) if f == f else None


def ozel_eleman(e):
    """Yapay zekânın yazdığı bir çizim elemanını güvenli, sınırlı bir biçime indirger; kullanılamazsa None."""
    if not isinstance(e, dict) or e.get("tur") not in TURLER:
        return None
    t = e["tur"]
    c = {"tur": t}
    for k in ("x", "y", "w", "h", "r", "x1", "y1", "x2", "y2", "olcek", "donus", "opaklik", "doluluk", "cizim", "boyut", "kalinlik", "sayi", "hiz", "halka"):
        if k in e:
            v = _sayi_alan(e[k], -900, 2300 if k not in ("opaklik", "doluluk", "cizim", "olcek", "hiz") else 12)
            if v is not None:
                c[k] = v
    for k in ("renk", "kenar", "doluluk_zemin"):
        if k in e:
            c[k] = _renk(e[k])
    if e.get("yon") in ("yatay", "dikey", "yukari", "asagi", "sag", "sol", "daire"):
        c["yon"] = e["yon"]
    if t == "yazi":
        m = _kisa(e.get("metin"), 30)
        if not m:
            return None
        c["metin"] = m
        c["hiza"] = e.get("hiza") if e.get("hiza") in ("left", "center", "right") else "center"
        c["boyut"] = max(26, min(120, c.get("boyut", 48)))
    if t == "ikon":
        if e.get("ad") not in IKONLAR:
            return None
        c["ad"] = e["ad"]
        c["olcek"] = max(0.3, min(5, c.get("olcek", 1)))
    if t == "parcacik":
        c["sayi"] = int(max(3, min(40, c.get("sayi", 14))))
    if e.get("kesikli"):
        c["kesikli"] = True
    if isinstance(e.get("t"), list) and len(e["t"]) == 2:
        a, b = _sayi_alan(e["t"][0], 0, 30), _sayi_alan(e["t"][1], 0, 99)
        if a is not None and b is not None and b > a:
            c["t"] = [a, b]
    hr = []
    for h in (e.get("hareket") or [])[:4] if isinstance(e.get("hareket"), list) else []:
        if isinstance(h, dict) and h.get("o") in OZELLIKLER:
            den, a_, t0, t1 = (_sayi_alan(h.get(k), -900, 2300) for k in ("den", "a", "t0", "t1"))
            if None not in (den, a_, t0, t1) and t1 > t0:
                hr.append({"o": h["o"], "den": den, "a": a_, "t0": max(0, t0), "t1": min(30, t1), "egri": h.get("egri") if h.get("egri") in ("yumusak", "ziplama", "cikis", "lineer") else "yumusak"})
    if hr:
        c["hareket"] = hr
    if isinstance(e.get("dongu"), dict):
        d = {k: max(-60, min(60, _sayi_alan(v, -60, 60) or 0)) for k, v in e["dongu"].items() if k in ("titre", "yuz", "dondur", "salin", "nabiz")}
        if d:
            c["dongu"] = d
    return c


def ozel_params(p):
    els = [ozel_eleman(e) for e in (p.get("elemanlar") if isinstance(p.get("elemanlar"), list) else [])[:30]]
    els = [e for e in els if e]
    if len(els) < 5:
        raise ValueError(f"özel sahnede en az 5 geçerli eleman gerekli ({len(els)})")
    if not any(e["tur"] in ("yazi", "ikon") for e in els):
        raise ValueError("özel sahnede en az bir yazı ya da ikon olmalı")
    kam = []
    for k in (p.get("kamera") if isinstance(p.get("kamera"), list) else [])[:2]:
        if isinstance(k, list) and len(k) == 3 and all(_sayi_alan(v, -2000, 4000) is not None for v in k):
            kam.append([_sayi_alan(k[0], 300, 780), _sayi_alan(k[1], 400, 1100), _sayi_alan(k[2], 0.7, 1.6)])
    tema = p.get("tema") if p.get("tema") in ("mavi", "mor", "yesil", "turuncu", "gri") else "mavi"
    noktalar = [[_sayi_alan(q[0], 0, 1080), _sayi_alan(q[1], 300, 1400), _sayi_alan(q[2] if len(q) > 2 else 1.4, 0.3, 8)] for q in (p.get("etiket_noktalari") or [])[:2] if isinstance(q, list) and len(q) >= 2 and _sayi_alan(q[0]) is not None and _sayi_alan(q[1]) is not None]
    return {"yedek": p.get("yedek") if p.get("yedek") in YEDEKLER else "ekstruder", "tema": tema, "kamera": kam or [[540, 760, 1.0], [540, 760, 1.08]], "elemanlar": els, "etiket_noktalari": noktalar}


def params_temizle(tip, p):
    p = p if isinstance(p, dict) else {}
    if tip == "ozel":
        return ozel_params(p)
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


def dogrula(s, temizle=lambda x: x, gecmis=()):
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
        if sayac[tip] > (3 if tip == "ozel" else 2):
            raise ValueError(f"'{tip}' tipi çok fazla kullanılmış")
        onceki = tip
        kel, bayrak = isaretle(" ".join(str(x.get("anlati") or "").split()))
        if len(kel) < 4:
            raise ValueError(f"{i + 1}. sahnede anlatı yok ya da çok kısa")
        et = [_kisa(e, 24) for e in (x.get("etiketler") or []) if _kisa(e, 24)][:2] if isinstance(x.get("etiketler"), list) else []
        nokta = _kisa(x.get("nokta"), 70) or " ".join(kel[:7])
        temiz.append({"tip": tip, "anlati": " ".join(kel), "isaret": bayrak, "nokta": nokta, "params": params_temizle(tip, x.get("params")), "etiketler": et,
                      "bolum": _kisa(temizle(str(x.get("bolum") or "")), 28) if i > 0 and tip != "kanca" else "", "baslik": _kisa(temizle(str(x.get("baslik") or "")), 10) if tip != "kanca" else ""})
    if temiz[0]["tip"] != "kanca":
        raise ValueError("ilk sahne 'kanca' olmalı")
    if temiz[-1]["tip"] != "kapanis":
        raise ValueError("son sahne 'kapanis' olmalı")
    if not sayac.get("ozel"):
        raise ValueError("en az bir 'ozel' (konuya özel tasarlanmış) sahne gerekli; yalnızca hazır tipler kullanılmış")
    if len(sayac) < 5:
        raise ValueError(f"en az 5 farklı sahne tipi gerekli ({len(sayac)})")
    kelime = sum(len(x["anlati"].split()) for x in temiz)
    if not 90 <= kelime <= 190:
        raise ValueError(f"anlatı {kelime} kelime; 90-190 olmalı")
    # içerik tekrarı: bu videonun noktaları önceki videolarda zaten anlatıldıysa ya da kendi içinde tekrar ediyorsa reddet
    if B is not None:
        eskiler = [g for g in gecmis if g]
        tekrar = [x["nokta"] for x in temiz if any(B.benzerlik(x["nokta"], g) >= 0.6 for g in eskiler)]
        if len(tekrar) >= 2:
            raise ValueError("şu noktalar önceki videolarda zaten anlatılmış, yeni bilgi ver: " + "; ".join(tekrar[:3]))
        ic = [(i, j) for i in range(len(temiz)) for j in range(i + 1, len(temiz)) if B.benzerlik(temiz[i]["nokta"], temiz[j]["nokta"]) >= 0.7]
        if ic:
            raise ValueError(f"{ic[0][0] + 1}. ve {ic[0][1] + 1}. sahnelerde aynı nokta anlatılıyor; her sahne farklı bilgi versin")
    # en çok 2 büyük başlık kartı
    sirali = [x for x in temiz if x["baslik"]]
    for x in sirali[2:]:
        x["baslik"] = ""
    return {"bicim": "anlat", "konu": str(s.get("konu") or "")[:140], "baslik": temizle(str(s.get("baslik") or ""))[:90],
            "aciklama": str(s.get("aciklama") or "")[:900].replace("http", ""),
            "etiketler": [re.sub(r"[^a-z0-9ığüşöç]", "", str(e).lower()) for e in (s.get("etiketler") or [])][:8], "sahneler": temiz}


def onceki_metni(noktalar, konular):
    """Komuta eklenen 'daha önce anlatılanlar' bloğu. noktalar: [[konu, [nokta,...]], ...]; konular: önceki başlıklar."""
    if not noktalar and not konular:
        return ""
    sat = ["DAHA ÖNCE ANLATILANLAR (tekrar etme):"]
    for k, n in noktalar[-10:]:
        sat.append("- " + str(k)[:70] + ": " + "; ".join(str(x)[:60] for x in n[:8]))
    ek = [k for k in konular if k not in {x[0] for x in noktalar}][-12:]
    if ek:
        sat.append("- Daha önceki video konuları: " + "; ".join(str(k)[:60] for k in ek))
    return "\n".join(sat) + "\n"
