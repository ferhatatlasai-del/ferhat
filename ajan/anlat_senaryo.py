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

TIPLER = ["ozel", "resim", "kanca", "ekstruder", "sicak_uc", "katman", "tikanma", "ilk_katman", "sogutma", "nem", "stringing", "warping",
          "karsilastir", "sayi", "kontrol_listesi", "dolgu", "hiz", "destek", "kapanis"]
EN_AZ_SURE = {"resim": 3.6, "ozel": 4.2, "tikanma": 5.0, "katman": 4.6, "sicak_uc": 4.0, "ilk_katman": 4.0, "sogutma": 4.0, "nem": 4.0, "stringing": 4.4, "warping": 4.4, "destek": 4.2,
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
ANLATI: sahne başına 1-2 kısa cümle (8-20 kelime), toplam 100-130 kelime (video en çok 58 sn olmalı). İlk sahne güçlü kanca (soru ya da yaygın hata). Cümleler kısa, konuşma dili, "sen" hitabı. Son sahne yoruma davet + takip et.
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
GENEL_IKONLAR = {"yumurta", "kalp", "ampul", "dunya", "kitap", "ev", "yaprak", "para", "gunes", "bulut", "insan", "tavuk"}
IKONLAR = {"nozul", "nozul_tikali", "makara", "disli", "fan", "termometre", "damla", "alev", "duman", "tik", "carpi", "uyari", "saat", "lupa", "yildiz", "parca", "filament", "yatak", "kilit"} | GENEL_IKONLAR
SERBEST_TIPLER = ["ozel", "kanca", "karsilastir", "sayi", "kontrol_listesi", "kapanis"]
RESIMLI_TIPLER = ["resim", "sayi", "karsilastir", "kontrol_listesi", "kapanis"]
HAREKETLER = ("yakin", "uzak", "sol", "sag", "yukari", "asagi")
TURLER = {"dikdortgen", "daire", "cizgi", "ok", "yazi", "ikon", "parcacik", "elips", "yol", "yay", "grup"}
OZELLIKLER = {"x", "y", "olcek", "donus", "opaklik", "w", "h", "doluluk", "cizim", "r", "x1", "y1", "x2", "y2", "boyut", "kalinlik", "rx", "ry", "a0", "a1"}
YEDEKLER = [t for t in TIPLER if t not in ("ozel", "resim", "kanca", "kapanis")]


def _renk(v, varsayilan="beyaz"):
    v = str(v or "")
    return v if (v in RENKLER or re.fullmatch(r"#[0-9a-fA-F]{6}", v)) else varsayilan


def _sayi_alan(v, lo=-900, hi=2300):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, f)) if f == f else None


def ozel_eleman(e, ic=False):
    """Yapay zekânın yazdığı bir çizim elemanını güvenli, sınırlı bir biçime indirger; kullanılamazsa None. ic: grup içi (iç içe grup yok)."""
    if not isinstance(e, dict) or e.get("tur") not in TURLER or (ic and e.get("tur") == "grup"):
        return None
    t = e["tur"]
    c = {"tur": t}
    for k in ("x", "y", "w", "h", "r", "x1", "y1", "x2", "y2", "olcek", "donus", "opaklik", "doluluk", "cizim", "boyut", "kalinlik", "sayi", "hiz", "halka", "rx", "ry", "a0", "a1"):
        if k in e:
            v = _sayi_alan(e[k], -900, 2300 if k not in ("opaklik", "doluluk", "cizim", "olcek", "hiz") else 12) if k not in ("a0", "a1") else _sayi_alan(e[k], -720, 720)
            if v is not None:
                c[k] = v
    for k in ("renk", "kenar", "doluluk_zemin", "renk2"):
        if k in e:
            c[k] = _renk(e[k])
    if e.get("yon") in ("yatay", "dikey", "yukari", "asagi", "sag", "sol", "daire"):
        c["yon"] = e["yon"]
    if e.get("gradyan") in ("dikey", "yatay", "radyal"):
        c["gradyan"] = e["gradyan"]
    for k in ("golge", "kapali", "yumusak", "sadece_kenar"):
        if e.get(k):
            c[k] = True
    if t == "yol":
        q = [[_sayi_alan(n[0], -900, 2300), _sayi_alan(n[1], -900, 2300)] for n in (e.get("noktalar") if isinstance(e.get("noktalar"), list) else [])[:28] if isinstance(n, list) and len(n) >= 2]
        q = [n for n in q if n[0] is not None and n[1] is not None]
        if len(q) < 3:
            return None
        c["noktalar"] = q
    if t == "grup":
        ch = [ozel_eleman(x, True) for x in (e.get("cocuklar") if isinstance(e.get("cocuklar"), list) else [])[:30]]
        ch = [x for x in ch if x]
        if len(ch) < 2:
            return None
        c["cocuklar"] = ch
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
    els = [ozel_eleman(e) for e in (p.get("elemanlar") if isinstance(p.get("elemanlar"), list) else [])[:48]]
    els = [e for e in els if e]
    tum = els + [x for e in els for x in e.get("cocuklar", [])]
    if len(tum) < 5:
        raise ValueError(f"özel sahnede en az 5 geçerli eleman gerekli ({len(tum)})")
    if not any(e["tur"] in ("yazi", "ikon") for e in tum):
        raise ValueError("özel sahnede en az bir yazı ya da ikon olmalı")
    kam = []
    for k in (p.get("kamera") if isinstance(p.get("kamera"), list) else [])[:2]:
        if isinstance(k, list) and len(k) == 3 and all(_sayi_alan(v, -2000, 4000) is not None for v in k):
            kam.append([_sayi_alan(k[0], 300, 780), _sayi_alan(k[1], 400, 1100), _sayi_alan(k[2], 0.7, 1.6)])
    tema = p.get("tema") if p.get("tema") in ("mavi", "mor", "yesil", "turuncu", "gri") else "mavi"
    noktalar = [[_sayi_alan(q[0], 0, 1080), _sayi_alan(q[1], 300, 1400), _sayi_alan(q[2] if len(q) > 2 else 1.4, 0.3, 8)] for q in (p.get("etiket_noktalari") or [])[:2] if isinstance(q, list) and len(q) >= 2 and _sayi_alan(q[0]) is not None and _sayi_alan(q[1]) is not None]
    return {"yedek": p.get("yedek") if p.get("yedek") in YEDEKLER else "ekstruder", "tema": tema, "kamera": kam or [[540, 760, 1.0], [540, 760, 1.08]], "elemanlar": els, "etiket_noktalari": noktalar, "eleman_sayisi": len(tum)}


def params_temizle(tip, p):
    p = p if isinstance(p, dict) else {}
    if tip == "ozel":
        return ozel_params(p)
    if tip == "resim":
        g = _kisa(p.get("gorsel"), 420)
        if len(g) < 25:
            raise ValueError("'resim' sahnesi için İngilizce görsel tarifi (params.gorsel, 25+ karakter) gerekli")
        od = p.get("odak") if isinstance(p.get("odak"), list) and len(p.get("odak")) == 2 else [0.5, 0.45]
        r = {"gorsel": g, "hareket": p.get("hareket") if p.get("hareket") in HAREKETLER else "yakin", "odak": [_sayi(od[0], 0.5, 0.15, 0.85), _sayi(od[1], 0.45, 0.2, 0.75)]}
        if isinstance(p.get("odak2"), list) and len(p.get("odak2")) == 2:
            r["odak2"] = [_sayi(p["odak2"][0], 0.5, 0.15, 0.85), _sayi(p["odak2"][1], 0.45, 0.2, 0.75)]
        r["katman_notu"] = _kisa(p.get("katman_notu"), 240)
        return r
    if tip in ("kanca", "kapanis"):
        return {"ikon": p["ikon"]} if p.get("ikon") in IKONLAR else {}
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


def serbest_ozel_params(p):
    """Serbest konuda özel sahnenin çizimi ayrı bir 'tasarımcı' çağrısında yazılır; hikâye tahtasında yalnızca tasarım notu bulunur."""
    p = p if isinstance(p, dict) else {}
    not_ = _kisa(p.get("tasarim_notu"), 700)
    if len(not_) < 30:
        raise ValueError("özel sahne için 'tasarim_notu' (sahnede ne görünecek, 3-5 cümle) yazılmalı")
    return {"yedek": "kontrol_listesi", "tema": p.get("tema") if p.get("tema") in ("mavi", "mor", "yesil", "turuncu", "gri") else "mavi", "tasarim_notu": not_, "elemanlar": []}


def dogrula(s, temizle=lambda x: x, gecmis=(), serbest=False, resimli=False):
    """Hikâye tahtasını temizler; sorun varsa ValueError. temizle: metin temizleyici (U.yazi_temizle)."""
    sah = [x for x in (s.get("sahneler") or []) if isinstance(x, dict)]
    if not 5 <= len(sah) <= 12:
        raise ValueError(f"sahne sayısı 5-12 olmalı ({len(sah)})")
    temiz, onceki, sayac = [], None, {}
    for i, x in enumerate(sah):
        tip = x.get("tip")
        if tip not in (RESIMLI_TIPLER if resimli else SERBEST_TIPLER if serbest else TIPLER):
            raise ValueError(f"{i + 1}. sahne tipi geçersiz: {tip}" + (" (bu modda yalnızca " + ", ".join(RESIMLI_TIPLER if resimli else SERBEST_TIPLER) + " kullanılır)" if (serbest or resimli) else ""))
        if tip == onceki and not (resimli and tip == "resim"):
            raise ValueError(f"{i + 1}. sahne bir öncekiyle aynı tip ({tip}); çeşitlilik gerekli")
        sayac[tip] = sayac.get(tip, 0) + 1
        if sayac[tip] > (10 if (resimli and tip == "resim") else (6 if serbest else 3) if tip == "ozel" else 2):
            raise ValueError(f"'{tip}' tipi çok fazla kullanılmış")
        onceki = tip
        kel, bayrak = isaretle(" ".join(str(x.get("anlati") or "").split()))
        if len(kel) < 4:
            raise ValueError(f"{i + 1}. sahnede anlatı yok ya da çok kısa")
        et = [_kisa(e, 24) for e in (x.get("etiketler") or []) if _kisa(e, 24)][:2] if isinstance(x.get("etiketler"), list) else []
        nokta = _kisa(x.get("nokta"), 70) or " ".join(kel[:7])
        temiz.append({"tip": tip, "anlati": " ".join(kel), "isaret": bayrak, "nokta": nokta, "params": (serbest_ozel_params(x.get("params")) if (serbest and tip == "ozel") else params_temizle(tip, x.get("params"))), "etiketler": et,
                      "bolum": _kisa(temizle(str(x.get("bolum") or "")), 28) if i > 0 and tip != "kanca" else "", "baslik": _kisa(temizle(str(x.get("baslik") or "")), 10) if tip != "kanca" else ""})
    if temiz[0]["tip"] != ("resim" if resimli else "kanca"):
        raise ValueError("ilk sahne '" + ("resim" if resimli else "kanca") + "' olmalı")
    if temiz[-1]["tip"] != "kapanis":
        raise ValueError("son sahne 'kapanis' olmalı")
    if resimli and sayac.get("resim", 0) < 4:
        raise ValueError("resimli modda en az 4 'resim' sahnesi gerekli")
    if serbest and not resimli and sayac.get("ozel", 0) < 3:
        raise ValueError("serbest konuda en az 3 'ozel' sahne gerekli")
    if not resimli and not sayac.get("ozel"):
        raise ValueError("en az bir 'ozel' (konuya özel tasarlanmış) sahne gerekli; yalnızca hazır tipler kullanılmış")
    if len(sayac) < (3 if resimli else 4 if serbest else 5):
        raise ValueError(f"en az {3 if resimli else 4 if serbest else 5} farklı sahne tipi gerekli ({len(sayac)})")
    kelime = sum(len(x["anlati"].split()) for x in temiz)
    alt, ust = (85, 125) if (serbest or resimli) else (90, 135)   # ≈0,44 sn/kelime + kuyruk: üst sınır ≈ 58 sn (hikâye/Reels/Shorts 60 sn sınırı)
    if not alt <= kelime <= ust:
        raise ValueError(f"anlatı {kelime} kelime; {alt}-{ust} olmalı (video en çok 58 sn: kısalt)" if kelime > ust else f"anlatı {kelime} kelime; {alt}-{ust} olmalı")
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
            "etiketler": [re.sub(r"[^a-z0-9ığüşöç]", "", str(e).lower()) for e in (s.get("etiketler") or [])][:8], "sahneler": temiz,
            "stil": _kisa(s.get("stil"), 220)}


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


# ---------------- SERBEST KONU (3D baskı dışı) ----------------
SERBEST_IKONLAR = "yumurta, tavuk, kalp, ampul, dunya, kitap, ev, yaprak, para, gunes, bulut, insan, termometre, damla, alev, tik, carpi, uyari, saat, lupa, yildiz, kilit"
ISTEM_SERBEST = """YouTube Shorts / Instagram Reels için EN ÇOK 58 saniyelik (60 sn kesin sınırdır: Instagram hikâyesi, Reels ve Shorts), ANİMASYONLU, görsel olarak DETAYLI ve ÇEŞİTLİ, TÜRKÇE, merak uyandıran bir bilgi videosunun HİKÂYE TAHTASINI yaz. Kanal 3D baskı ağırlıklıdır ama bu video SERBEST bir konudadır: konu 3D baskıyla ilgili olmak zorunda DEĞİL, ona zorla bağlama; ama video genel bir kitleye yönelik, sakin, güvenilir ve eğlenceli olsun.
Konu: {konu}
İpucu: {ipucu}
KONU UYGUN DEĞİLSE (nefret/hakaret, siyaset, kişi hedefleme, sağlık/hukuk/yatırım TAVSİYESİ, şiddet, yetişkin içerik, tehlikeli talimat) hikâye yazma; yalnızca {{"uygunsuz": "kısa neden"}} döndür.

Video, her biri bir ANİMASYON SAHNESİ olan 6 ile 8 sahneden oluşur. Konuyu adım adım, sebep-sonuç ve süreç olarak anlat.
SAHNE TİPLERİ (yalnızca bunlar):
- kanca: açılış (merkezde büyük bir ikon, ışınlar, soru işaretleri). ZORUNLU ilk sahne. params: {{"ikon": "yumurta"}}  (ikon: """ + SERBEST_IKONLAR + """)
- karsilastir: iki değeri sütunla karşılaştırır. params: {{"a": {{"ad": "Yaz", "deger": 5}}, "b": {{"ad": "Kış", "deger": 3}}, "birim": "adet"}}
- sayi: büyük halka sayaç. params: {{"deger": 65, "maks": 100, "birim": "%", "etiket": "kısa açıklama"}}
- kontrol_listesi: onay işaretli madde listesi (özet için). params: {{"maddeler": ["en çok 28 harf", "...", "..."]}}  (3-4 madde)
- kapanis: son sahne (takip et). ZORUNLU son sahne. params: {{"ikon": "kalp"}}
- ozel: DETAYLI, konuya özel çizilmiş animasyon sahnesi. Videonun ANA görsel yükünü bu sahneler taşır: 3-4 tane yaz. Çizimi ayrı bir ressam yapacak; sen yalnızca ne görüneceğini anlat: params: {{"yedek": "kontrol_listesi", "tema": "mavi|mor|yesil|turuncu|gri", "tasarim_notu": "sahnede NE görünecek: mekân/arka plan, ana nesneler ve parçaları, hareket sırası (önce ne belirir, sonra ne olur), gösterilecek sayı/etiketler. 3-5 somut cümle."}}
ÇEŞİTLİLİK KURALLARI: Aynı tip arka arkaya gelmesin; ozel dışındaki tipler en çok 2 kez; en az 4 farklı tip. Her özel sahne farklı bir mekân/nesne/kavram göstersin (aynı kompozisyonu tekrarlama).
TEKRARA DÜŞME: Her sahnenin "nokta" alanına o sahnede anlattığın TEK somut bilgiyi 3-8 kelimeyle yaz. Aşağıdaki, daha önceki videolarda ZATEN anlatılmış noktaları ve konuları TEKRAR ETME. Bu videonun noktaları da birbirinden farklı olsun.
{onceki}
ANLATI: toplam 95-120 kelime (KESİN: 125'i geçme, video 58 sn'yi aşmasın). Özel sahnelerde 14-22 kelime (1-2 kısa cümle; ressamın çizeceği şeyi anlat), diğerlerinde 8-16 kelime. İlk sahne güçlü kanca (soru ya da yaygın yanılgı). Cümleler kısa, konuşma dili, "sen" hitabı. Son sahne yoruma davet + takip et.
VURGU: anlatıda önemli kelimeleri işaretle: *kelime* turuncu, ~kelime~ mavi. Her sahnede en çok 2 vurgu; çok kelimeli vurguda HER kelimeyi ayrı işaretle.
EK ALANLAR (isteğe bağlı): "bolum": yeni bölüm başlığı (en çok 28 harf; ilk sahnede olmasın, "kanca"ya yazma; 3-5 bölüm); "baslik": ekrana büyük yazı olarak zıplayan TEK kısa kelime (en çok 10 harf, tüm videoda en çok 2 sahnede); "etiketler": [] bırak.
GÜVENLİK/ACİL DURUM VE HABER KONULARI: Tehlike, güvenlik ya da güncel olay içeren konularda yalnızca resmî kurumların ve uzmanların GENEL KABUL GÖREN tavsiyelerini ver (yetkililere haber ver: Türkiye'de 112, güvenli kapalı alana çekil, uzak dur, kahramanlık yapma); kesin garanti verme, riskli davranış özendirme. Olayı gerçekmiş gibi anlatma: "diyelim ki / eğer karşılaşırsan" çerçevesi kur; yer, kişi ve kurum adı uydurma. Konu esprili anlatılsın denmişse hafif, zekice, kimseyle alay etmeyen espriler yap; bilgi her zaman doğru ve net kalsın.
DOĞRULUK: Yalnızca yaygın kabul gören, doğru bilgileri yaz. Emin olmadığın sayıyı verme; tipik değer ya da aralık kullan ("yaklaşık", "genellikle"). İstatistik, fiyat, marka karşılaştırması, kişisel deneyim, bilimsel iddia UYDURMA. Tartışmalı ya da kesin olmayan konuda dengeli konuş. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları anlatıda yazıyla yaz ("yüz yirmi gün").
YALNIZCA JSON döndür: {{"konu":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["konuyla ilgili","3-6 etiket"],
"sahneler":[{{"tip":"kanca","anlati":"...","nokta":"3-8 kelimelik tek bilgi","bolum":"","baslik":"","etiketler":[],"params":{{"ikon":"yumurta"}}}}]}}"""

ISTEM_TASARIM = """Sen bir hareketli grafik ressamısın. Aşağıdaki bilgi videosu sahnesi için DETAYLI, katmanlı, sürekli hareketli bir animasyon sahnesini JSON olarak tarif et.
Video konusu: {konu}
Sahne anlatısı (spiker bunu okuyacak, animasyon aynı sırayla ilerlemeli): {anlati}
Tasarım notu: {tasarim}
Sahne süresi: yaklaşık {sure} sn (t değerleri 0 ile {sure} arasında olsun; elemanlar anlatıyla aynı sırada belirsin).

KOORDİNAT: yatay 0-1080, dikey 350-1250 görünür alan (merkez 540,760); sahnenin altında alt yazı olduğu için dikeyde 360-1150 arasını kullan. Elemanlar listede alttan üste sırayla çizilir.
ORTAK ALANLAR (hepsinde isteğe bağlı): "t":[giriş_sn, çıkış_sn], "renk" ve "renk2"+"gradyan":"dikey|yatay|radyal" (renk geçişi), "golge":true, "opaklik", "olcek", "donus" (radyan), "hareket":[{{"o":"x|y|olcek|donus|opaklik|w|h|rx|ry|doluluk|cizim","den":a,"a":b,"t0":sn,"t1":sn,"egri":"yumusak|ziplama|cikis|lineer"}}] (en çok 4), "dongu":{{"titre":n,"yuz":n,"dondur":n,"salin":n,"nabiz":n}} (sürekli hareket).
TÜRLER:
- dikdortgen {{x,y,w,h,r(köşe yuvarlama),renk,renk2,gradyan,kenar,kalinlik,doluluk(0-1 dolum çubuğu),yon:"yatay|dikey"}}
- daire {{x,y,r,renk,renk2,gradyan,halka(kalınlık: yalnızca çember çizer),cizim(0-1),kenar}}
- elips {{x,y,rx,ry,renk,renk2,gradyan,kenar,kalinlik}}
- yol {{x,y,noktalar:[[x,y],...],kapali,yumusak,renk,renk2,gradyan,kenar,kalinlik,cizim}}: HERHANGİ bir biçimi çizersin (dağ, yaprak, gövde, kanat, dalga, bina, bulut, bitki...). noktalar 3-28 adet ve (x,y) başlangıcına GÖRELİ; kapali:true doldurur; yumusak:true köşeleri yuvarlar; açık yolda cizim 0-1 yolun çizilme oranıdır.
- yay {{x,y,r,a0,a1 (derece),renk,kalinlik,cizim}}
- cizgi / ok {{x1,y1,x2,y2,renk,kalinlik,kesikli,cizim(0-1: çizilerek belirir)}}
- yazi {{x,y,metin (en çok 30 harf),boyut (40-110),renk,hiza}}
- ikon {{x,y,ad,olcek,renk,doluluk}}: ad yalnızca şunlardan: """ + SERBEST_IKONLAR + """
- parcacik {{x,y,w,h,sayi,yon:"yukari|asagi|sag|sol|daire",renk,boyut,hiz}}
- grup {{x,y,cocuklar:[2-30 eleman, iç içe grup yok]}}: bir nesnenin parçalarını birleştirir. Grubun x,y,olcek,donus,opaklik,hareket,dongu,golge değerleri çocuklara BİRLİKTE uygulanır (ör. tavuk = gövde+kafa+gaga+ibik+göz+kanat+bacaklar tek grup → birlikte sallanır, yürür). Çocukların koordinatları grubun merkezine göredir.
Renkler: turuncu, mavi, yesil, kirmizi, sari, mor, pembe, beyaz, koyu, gri, kahve, siyah ya da #rrggbb.

TASARIM İLKELERİ (24-48 eleman; gruplardaki çocuklar da sayılır):
1) ARKA PLAN (4-8 eleman): zemin/gökyüzü/oda, gradyanlı büyük şekiller, ufuk, derinlik ögeleri (bulut, ağaç, raf, pencere, tepe...). Arka plan x 0-1080, y 300-1300 alanını TAMAMEN kaplasın (ilk eleman tam ekran gradyanlı dikdörtgen). Boş arka plan YOK. Renkleri gerçekçi seç (çim yeşil, gökyüzü mavi...); renk tonu sonradan değişmez.
2) ANA NESNELER: her biri 6-14 parçalı grup; ayrıntılar (göz, parlama noktası, gölge, desen, çizgi), ikinci ton renk (renk2) ve gölge kullan. Tek şekilden oluşan nesne YOK; gerçekçi/sevimli düz illüstrasyon tarzı.
3) SÜREÇ ANİMASYONU: parçalar anlatıyla aynı sırada belirsin ("t"), büyüsün, yer değiştirsin ("hareket"), oklar çizilsin ("cizim" 0→1), çubuk/sayaç dolsun ("doluluk"), parçacıklar aksın. Sahne boyunca HER an bir şey hareket etsin ("dongu").
4) ETİKET ve SAYILAR: 3-6 kısa yazı; üst üste binmesin, ekran dışına taşmasın, okunur olsun (boyut ≥ 40), nesneleri örtmesin.
5) KAMERA: "kamera":[[540,760,1.0],[540,740,1.12]] gibi yavaş bir yakınlaşma/kayma.
6) 4-6 uyumlu renk; ana nesne arka plandan net ayrışsın.
ÇOK ÖNEMLİ: Çıktı geçerli JSON olsun; sayılar sayı, metinler kısa olsun.
Mini örnek (yalnızca biçim için): {{"tema":"mavi","kamera":[[540,760,1.0],[540,740,1.1]],"elemanlar":[{{"tur":"dikdortgen","x":540,"y":560,"w":1080,"h":420,"renk":"#2a6fb8","renk2":"#8fd0ff","gradyan":"dikey"}},{{"tur":"yol","x":0,"y":0,"kapali":true,"yumusak":true,"renk":"#3d8f4a","renk2":"#2a6b36","noktalar":[[0,900],[300,850],[650,890],[1080,850],[1080,1200],[0,1200]]}},{{"tur":"grup","x":540,"y":900,"golge":true,"dongu":{{"yuz":4}},"cocuklar":[{{"tur":"elips","x":0,"y":0,"rx":110,"ry":80,"renk":"#fff8e6","renk2":"#e8d9b8","gradyan":"dikey"}},{{"tur":"daire","x":90,"y":-70,"r":42,"renk":"#fff8e6"}},{{"tur":"daire","x":104,"y":-80,"r":6,"renk":"#10161f"}}]}},{{"tur":"yazi","x":540,"y":420,"metin":"ETİKET","boyut":56,"renk":"beyaz","t":[1,99]}},{{"tur":"ok","x1":300,"y1":700,"x2":420,"y2":800,"renk":"sari","t":[2,99],"hareket":[{{"o":"cizim","den":0,"a":1,"t0":2,"t1":3}}]}}],"etiket_noktalari":[]}}
YALNIZCA JSON döndür: {{"tema":"...","kamera":[[x,y,zoom],[x,y,zoom]],"elemanlar":[...],"etiket_noktalari":[]}}"""


# ---------------- RESİMLİ ANLATIM (yapay zekâ resimleri + sinematik hareket; her konu) ----------------
ISTEM_RESIMLI = """YouTube Shorts / Instagram Reels için EN ÇOK 58 saniyelik (60 sn kesin sınırdır: Instagram hikâyesi, Reels ve Shorts), SİNEMATİK, görsel olarak zengin, TÜRKÇE, merak uyandıran bir bilgi videosunun HİKÂYE TAHTASINI yaz. Görseller yapay zekâ tarafından RESİM olarak üretilecek ve üzerlerine yavaş kamera hareketi, altyazı, ses ve müzik eklenecek. Konu serbesttir (3D baskıyla ilgili olmak zorunda değil, zorla bağlama).
Konu: {konu}
İpucu: {ipucu}
KONU UYGUN DEĞİLSE (nefret/hakaret, siyaset, kişi hedefleme, sağlık/hukuk/yatırım TAVSİYESİ, şiddet, yetişkin içerik, tehlikeli talimat) hikâye yazma; yalnızca {{"uygunsuz": "kısa neden"}} döndür.

VİDEO TÜM SAHNELER İÇİN TEK BİR GÖRSEL STİL kullanır: "stil" alanına İngilizce, konuya uygun tutarlı bir stil yaz (ör. "warm flat vector illustration, soft gradients, rich detail, consistent color palette" ya da "cinematic documentary photograph, natural light, shallow depth of field"). İnsan gerekiyorsa sade stilize figürler (detaylı yüz yok) tercih et.
7 ile 9 sahne yaz (hızlı tempo: her sahne ~5-7 sn). SAHNE TİPLERİ:
- resim: tam ekran yapay zekâ görseli (videonun ana sahnesi; 5-8 tane; sahne başına TEK kısa cümle, hızlı tempo). params: {{"gorsel": "İNGİLİZCE, 25-60 kelimelik DETAYLI görsel tarifi: ana nesne/olay, mekân, arka plan, ışık, renkler, kompozisyon; metin/yazı/logo YOK", "hareket": "yakin|uzak|sol|sag|yukari|asagi", "odak": [0.5, 0.45], "katman_notu": "Görselin ÜSTÜNE animasyonla ne eklenecek (1 cümle, Türkçe): ör. aslanın üstünde nabız atan kırmızı halka ve 'MESAFE' etiketi; geri çekilmeyi gösteren ok; ev simgesi"}}
  Görsel tarifleri HER SAHNEDE FARKLI olsun (farklı mekân, plan ve açı: geniş plan, yakın plan, üstten, kesit, karşılaştırma...). Görselin alt üçte biri sade/koyu kalsın (altyazı için). Ana nesne ekranın ortasının biraz üstünde. "odak": ana nesnenin görseldeki yeri [yatay 0-1, dikey 0-1].
- sayi: büyük halka sayaç (önemli bir sayı için; en çok 1). params: {{"deger": 65, "maks": 100, "birim": "%", "etiket": "kısa açıklama"}}
- karsilastir: iki değeri sütunla karşılaştırır (en çok 1). params: {{"a": {{"ad": "Yaz", "deger": 5}}, "b": {{"ad": "Kış", "deger": 3}}, "birim": "adet"}}
- kontrol_listesi: onay işaretli özet listesi (en çok 1, sondan bir önce). params: {{"maddeler": ["en çok 28 harf", "...", "..."]}}
- kapanis: son sahne (takip et). ZORUNLU son. params: {{"ikon": "kalp"}}
İlk sahne "resim" olsun (güçlü kanca görseli). Aynı kompozisyonu tekrarlama.
TEKRARA DÜŞME: Her sahnenin "nokta" alanına o sahnede anlattığın TEK somut bilgiyi 3-8 kelimeyle yaz. Aşağıdaki, daha önceki videolarda ZATEN anlatılmış noktaları ve konuları TEKRAR ETME.
{onceki}
ANLATI: toplam 95-120 kelime (KESİN: 125'i geçme, video 58 sn'yi aşmasın); sahne başına TEK kısa cümle (8-15 kelime). İlk sahne güçlü kanca (soru ya da yaygın yanılgı). Cümleler kısa, konuşma dili, "sen" hitabı. Her sahnenin anlatısı o sahnenin görselini anlatsın. Son sahne yoruma davet + takip et.
VURGU: önemli kelimeleri işaretle: *kelime* turuncu, ~kelime~ mavi. Her sahnede en çok 2 vurgu.
EK ALANLAR (isteğe bağlı): "bolum": yeni bölüm başlığı (en çok 28 harf; ilk sahnede olmasın; 3-5 bölüm); "baslik": ekrana büyük yazı olarak zıplayan TEK kısa kelime (en çok 10 harf, tüm videoda en çok 2 sahnede); "etiketler": [] bırak (etiketler "resim" sahnelerinde katman_notu ile eklenir).
GÜVENLİK/ACİL DURUM VE HABER KONULARI: Tehlike, güvenlik ya da güncel olay içeren konularda yalnızca resmî kurumların ve uzmanların GENEL KABUL GÖREN tavsiyelerini ver (yetkililere haber ver: Türkiye'de 112, güvenli kapalı alana çekil, uzak dur, kahramanlık yapma); kesin garanti verme, riskli davranış özendirme. Olayı gerçekmiş gibi anlatma: "diyelim ki / eğer karşılaşırsan" çerçevesi kur; yer, kişi ve kurum adı uydurma. Konu esprili anlatılsın denmişse hafif, zekice, kimseyle alay etmeyen espriler yap; bilgi her zaman doğru ve net kalsın.
DOĞRULUK: Yalnızca yaygın kabul gören, doğru bilgileri yaz. Emin olmadığın sayıyı verme; "yaklaşık", "genellikle" kullan. İstatistik, fiyat, marka karşılaştırması, kişisel deneyim, bilimsel iddia UYDURMA. Tartışmalı konuda dengeli konuş. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Sayıları anlatıda yazıyla yaz.
YALNIZCA JSON döndür: {{"konu":"...","stil":"...","baslik":"arama odaklı en çok 70 karakter","aciklama":"2-3 kısa satır, son satır yorum daveti","etiketler":["konuyla ilgili","3-6 etiket"],
"sahneler":[{{"tip":"resim","anlati":"...","nokta":"3-8 kelimelik tek bilgi","bolum":"","baslik":"","etiketler":[],"params":{{"gorsel":"...","hareket":"yakin","odak":[0.5,0.45]}}}}]}}"""


def katman_params(j):
    """'Katman ressamı' çıktısını (görsele yapışık animasyonlu ögeler) güvenli biçime indirger. Dönen: eleman listesi (en az 3, en çok 20) ya da ValueError."""
    els = [ozel_eleman(e) for e in (j.get("elemanlar") if isinstance(j, dict) and isinstance(j.get("elemanlar"), list) else [])[:20]]
    els = [e for e in els if e]
    if len(els) < 3:
        raise ValueError(f"katmanda en az 3 geçerli eleman gerekli ({len(els)})")
    if not any(e["tur"] in ("yazi", "yol", "ok", "daire", "ikon", "grup") for e in els):
        raise ValueError("katmanda işaret/etiket ögesi yok")
    for e in els:   # yazılar kamera kırpmasında kesilmesin: yazının tamamı görsel koordinatında x 170-860 içinde kalsın
        if e["tur"] == "yazi":
            e["boyut"] = min(e.get("boyut", 56), 64)
            gen = max(40, len(e["metin"]) * e["boyut"] * 0.62)
            e["x"] = max(170 + gen / 2, min(860 - gen / 2, e.get("x", 512))) if gen < 690 else 512
            e["y"] = max(300, min(1180, e.get("y", 700)))
    return els


ISTEM_KATMAN = """Sen bir hareketli grafik ressamısın. Bir bilgi videosunun tam ekran görselinin ÜSTÜNE binen, animasyonlu bir KATMAN tasarla: oklar, nabız atan halkalar, kısa etiketler, sayılar, parıltılar, simgeler, hız çizgileri, konuşma balonları. Katman görsele YAPIŞIKTIR (kamera hareket ederken nesneyle birlikte hareket eder).
Video konusu: {konu}
Sahne anlatısı ve KELİME ZAMANLARI (sahne başından saniye): {anlati}
Sahnenin görseli: {gorsel}
Görselde ne nerede (görsel koordinatı; görsel 1024 x 1536 pikseldir, x 0-1024, y 0-1536): {nesneler}
Ana odak noktası: ({ox}, {oy}); ikinci plan (yakın çekim) odağı: ({ox2}, {oy2}).
Sahne süresi: yaklaşık {sure} sn. Ögeler anlatıdaki ilgili kelime söylenirken belirsin ("t":[giriş, çıkış] kelime zamanlarına göre; çıkış için 99 yaz ya da sahne süresinden önce bir an).

KURALLAR:
- 5-12 eleman. Görseli örtme: tam ekran dolgu, büyük yarı saydam bloklar YOK. Ögeler küçük/orta olsun, nesnelerin ÜSTÜNDE ya da YANINDA, yukarıda verilen konumlara göre yerleştirilsin (ok ucu gerçekten o nesneyi göstersin).
- Güvenli alan: x 170-860, y 300-1180 (görsel koordinatı); alt kısım altyazıya ayrılmıştır, oraya yazı koyma. Yazı genişliği ≈ harf sayısı × boyut × 0.62 piksel ve yazının TAMAMI x 170-860 içinde kalmalı (kamera yakınlaşınca kenarlar kesilir).
- Yazılar kısa (en çok 14 harf), boyut 46-64, okunur renk (beyaz/sarı + koyu kontur otomatik), üst üste binmesin.
- Her an biraz hareket olsun: "dongu" (nabiz/yuz/salin/titre), "hareket" (olcek, opaklik, cizim 0→1 ile oklar çizilsin, x/y kayma).
- Bilgiye hizmet et: tehlike/uyarı ise kırmızı/sarı, güvenli yön ise yeşil; sayı varsa sayıyı göster.
KOORDİNAT/ALANLAR: ortak: "t":[giriş_sn,çıkış_sn], "renk","renk2"+"gradyan","golge","opaklik","olcek","donus"(radyan),"hareket":[{{"o":"x|y|olcek|donus|opaklik|w|h|rx|ry|doluluk|cizim","den":a,"a":b,"t0":sn,"t1":sn,"egri":"yumusak|ziplama|cikis|lineer"}}],"dongu":{{"titre":n,"yuz":n,"dondur":n,"salin":n,"nabiz":n}}.
TÜRLER: daire {{x,y,r,renk,halka(kalınlık: yalnızca çember),cizim}}; elips {{x,y,rx,ry,renk,halka}}; yay {{x,y,r,a0,a1,renk,kalinlik,cizim}}; cizgi/ok {{x1,y1,x2,y2,renk,kalinlik,kesikli,cizim}}; yazi {{x,y,metin,boyut,renk,hiza}}; ikon {{x,y,ad,olcek}} ad: """ + SERBEST_IKONLAR + """; yol {{x,y,noktalar:[[x,y],...],kapali,yumusak,renk,kenar,kalinlik,cizim}}; parcacik {{x,y,w,h,sayi,yon,renk,boyut,hiz}}; grup {{x,y,cocuklar:[...]}}. Renkler: turuncu, mavi, yesil, kirmizi, sari, mor, pembe, beyaz, koyu, gri, kahve, siyah ya da #rrggbb.
Mini örnek (biçim için): {{"elemanlar":[{{"tur":"daire","x":500,"y":900,"r":120,"renk":"kirmizi","halka":10,"t":[0.8,99],"dongu":{{"nabiz":0.08}}}},{{"tur":"ok","x1":700,"y1":600,"x2":560,"y2":800,"renk":"sari","kalinlik":12,"t":[1.2,99],"hareket":[{{"o":"cizim","den":0,"a":1,"t0":1.2,"t1":1.8}}]}},{{"tur":"yazi","x":720,"y":560,"metin":"KOŞMA!","boyut":70,"renk":"sari","t":[1.4,99]}}]}}
YALNIZCA JSON döndür: {{"elemanlar":[...]}}"""
