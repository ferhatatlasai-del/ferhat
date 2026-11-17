#!/usr/bin/env python3
"""Hikaye üretici (Kademe 2): trend tasarımlardan, yapay zekâ ile temsili hikaye görselleri üretir ve kuyruğa ekler.

Akış:
  1. Web aramasıyla (OpenAI Responses API) Printables ve MakerWorld'de güncel popüler tasarımları bul.
  2. YALNIZCA lisansı açıkça CC0 ya da CC BY olan tasarımları tut (NC, ND, SA ve belirsiz lisanslar elenir).
     Bağlantı, aramanın gerçekten döndürdüğü adreslerle doğrulanır; alan adı printables.com ya da makerworld.com olmalı.
  3. Her tasarım için KENDİ sahnemizde (atölye, yumuşak ışık) temsili bir görsel üret; tasarımı birebir kopyalama, işlev iddiası yok.
  4. Görseli yapay zekâ ile denetle (yazı, logo, bozuk anatomi, fiziksel olarak mümkün olmayan nesne). Geçmezse 2 kez daha dene;
     hâlâ geçmezse o tasarım atlanır (şüphede yayınlama).
  5. Görsele "Yapay zekâ görseli (temsili)" etiketini ve tasarım atfını (ad, tasarımcı, lisans, kaynak) işle, 1080x1920 JPEG yap.
  6. Kuyruğa ekle (otomatik modda "planli", onay modunda "onay_bekliyor"). Başlangıçta kapalıdır; harcama sınırları vardır.

Başkasının fotoğrafı indirilmez ya da kullanılmaz; yalnızca ad, tasarımcı, lisans ve bağlantı alınır.
Hiçbir şey yayınlamaz (yayını hikaye.py yapar).

Kullanım:
    OPENAI_API_KEY=... python3 ajan/hikaye_uret.py            # ayara göre (aktif ise)
    OPENAI_API_KEY=... python3 ajan/hikaye_uret.py --hemen    # aktif=false olsa bile bir kez (bütçe sınırları geçerli)
    python3 ajan/hikaye_uret.py --lisans-dene "CC BY-NC 4.0"   # lisans süzgecini dene
"""
import argparse
import base64
import datetime
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402
import shorts_uret as SU  # noqa: E402
import uret  # noqa: E402

KOK = H.KOK
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
GORSEL_MODELI = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"
URETIM = KOK / "hikaye" / "uretim.json"
HARCAMA = KOK / "hikaye" / "harcama.json"
KULLANILAN = KOK / "hikaye" / "kullanilan.json"
IZINLI_SITELER = ("printables.com", "makerworld.com")
VARSAYILAN = {"aktif": False, "mod": "otomatik", "gunluk_uretim": 4, "gunluk_gorsel_siniri": 12,
              "aylik_gorsel_siniri": 150, "kalite": "medium", "kuyruk_hedefi": 8}
ARAC_TURLERI = ["web_search", "web_search_preview"]
YAPAY_ZEKA_ETIKETI = "Yapay zekâ görseli (temsili)"


def hata(m, kod=1):
    print(f"HATA: {m}", file=sys.stderr)
    sys.exit(kod)


# ---------- Lisans süzgeci ----------

def lisans_uygun(metin):
    """'CC0' ya da 'CC BY' döndürür; NC/ND/SA ve belirsiz her şey için None. Büyük/küçük harf ve sürüm numarası fark etmez."""
    t = " ".join((metin or "").lower().replace("-", " ").replace("_", " ").replace("—", " ").replace("–", " ").split())
    if not t:
        return None
    if re.search(r"\b(nc|nd|sa)\b|noncommercial|non commercial|noderiv|no deriv|sharealike|share alike|standard digital file|all rights reserved", t):
        return None
    if re.search(r"\bcc0\b|public domain dedication|\bcc zero\b", t):
        return "CC0"
    if re.search(r"\bcc by\b(?!\s*(nc|nd|sa))", t) or re.fullmatch(r"(creative commons )?attribution( 4 0| 3 0| 2 0)?( international)?( \(?cc by\)?)?", t):
        return "CC BY"
    return None


def site_uygun(adres):
    try:
        h = urllib.parse.urlparse(adres).hostname or ""
    except Exception:
        return None
    for s in IZINLI_SITELER:
        if h == s or h.endswith("." + s):
            return s
    return None


def temiz_adres(u):
    return re.sub(r"[?&]utm_[^&]*", "", u or "").rstrip("/?&")


def adres_anahtari(u):
    """Aynı tasarım sayfasının farklı yazımlarını (www, dil öneki, ad eki, sorgu, #) tek anahtara indirger."""
    try:
        p = urllib.parse.urlparse((u or "").strip())
    except Exception:
        return None
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    yol = re.sub(r"^/[a-z]{2}(-[a-z]{2,4})?(?=/)", "", p.path.lower()).rstrip("/")
    m = re.search(r"/models?/(\d+)", yol)
    if host in IZINLI_SITELER and m:
        return f"{host}#{m.group(1)}"
    return f"{host}{yol}" if host else None


# ---------- OpenAI ----------

def openai(yol, govde, sure=240):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        hata("OPENAI_API_KEY tanımlı değil.")
    r = urllib.request.Request(f"{OPENAI}/{yol}", data=json.dumps(govde).encode(), method="POST",
                               headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(r, timeout=sure) as y:
        return json.load(y)


def http_hata_ozeti(e):
    try:
        return f"HTTP {e.code}: {json.loads(e.read().decode())['error']['message'][:160]}"
    except Exception:
        return f"HTTP {e.code}"


def sohbet_json(sistem, kullanici, resim_b64=None):
    icerik = [{"type": "text", "text": kullanici}]
    if resim_b64:
        icerik.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + resim_b64}})
    govde = {"model": MODEL, "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": icerik if resim_b64 else kullanici}]}
    try:
        v = openai("chat/completions", govde)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404) and MODEL != "gpt-4o-mini":
            govde["model"] = "gpt-4o-mini"
            v = openai("chat/completions", govde)
        else:
            raise
    return json.loads(v["choices"][0]["message"]["content"])


ARAMA_ISTEMI = """Sen 3D baskı tasarımlarını araştıran bir ajansın. İnternette ARA ve Printables (printables.com) ile MakerWorld (makerworld.com)
sitelerinde şu sıralar (son 1-4 hafta) popüler olan, ev tipi bir 3D yazıcıyla basılabilen, günlük hayatta kullanışlı ya da ilginç 8-12 tasarım bul.

KESİN KURALLAR:
- Yalnızca tasarımın kendi sayfasında lisansı AÇIKÇA "CC0" ya da "Creative Commons Attribution (CC BY)" olarak yazan tasarımları listele.
  Lisansı sayfada göremiyorsan, NC (ticari değil), ND (türev yok), SA (benzer paylaşım), "Standard Digital File License" ya da belirsizse LİSTELEME.
- Markalı ya da lisanslı karakter/ürün (film, oyun, spor kulübü, marka logosu) içeren tasarımları listeleme.
- Uydurma. Bulamadığın bilgiyi yazma. Bağlantı yalnızca aramada gerçekten açtığın tasarım sayfası olsun.

Her biri için JSON alanları:
- ad: tasarımın adı (sayfadaki gibi)
- tasarimci: tasarımcının kullanıcı adı
- lisans: sayfada yazan lisansın TAM adı (örn. "CC BY 4.0", "CC BY-NC 4.0", "CC0", "Standard Digital File License"). Yalnızca "Creative Commons 4.0 International" gibi eksik yazma; BY/NC/ND/SA ekini sayfada göremediysen "belirsiz" yaz
- lisans_kaniti: sayfadan lisansı gösteren kısa alıntı
- url: tasarım sayfasının adresi
- aciklama: İngilizce, nesnenin ne olduğu ve fiziksel görünümü (şekil, parçalar, kullanım), 1-2 cümle, YALNIZCA sayfada yazanlara dayan
- hareketli_parca: true/false (menteşe, kilit, katlanma, dönen parça var mı)
- kategori: kısa etiket (masa düzeni, mutfak, oyuncak, araç, bahçe vb.)
- neden_populer: Türkçe 1 cümle

Yalnızca geçerli JSON döndür: {"tasarimlar":[{...}]}"""


def tasarim_ara():
    """(tasarimlar, dogrulanan_adresler). Web arama aracı bulunamazsa hata."""
    veri = None
    for tur in ARAC_TURLERI:
        try:
            veri = openai("responses", {"model": MODEL, "tools": [{"type": tur}], "input": ARAMA_ISTEMI}, 300)
            break
        except urllib.error.HTTPError as e:
            print(f"UYARI: '{tur}' aracı olmadı ({http_hata_ozeti(e)})")
    if veri is None:
        hata("Web arama aracı kullanılamadı; tasarım araştırması yapılamadı.")
    metin, adresler = "", set()
    for oge in veri.get("output", []):
        if oge.get("type") != "message":
            continue
        for c in oge.get("content", []):
            if c.get("type") == "output_text":
                metin += c.get("text", "")
                for a in c.get("annotations", []) or []:
                    if a.get("type") == "url_citation" and a.get("url"):
                        adresler.add(temiz_adres(a["url"]))
    m = re.search(r"\{.*\}", metin, re.S)
    if not m:
        hata("Arama yanıtında JSON bulunamadı.")
    try:
        return json.loads(m.group(0)).get("tasarimlar", []), adresler
    except json.JSONDecodeError as e:
        hata(f"Arama yanıtı okunamadı: {e}")


DOGRULA_ISTEMI = """Şu 3D baskı tasarım sayfasını internette ARA ve aç: {url}
Sayfa gerçekten var mı ve sayfada yazan lisans nedir? Uydurma; sayfayı açamadıysan gecerli_sayfa false yaz.
Yalnızca geçerli JSON döndür: {{"gecerli_sayfa": true/false, "ad": "sayfadaki tasarım adı", "lisans": "sayfada yazan lisansın tam adı (BY/NC/ND/SA ekleriyle, örn. CC BY 4.0); göremediysen belirsiz"}}"""


def sayfa_dogrula(t):
    """Aramada doğrulanamayan adayı, sayfaya özel ikinci bir aramayla sına. Aynı sayfa kaynak gösterilmeli ve lisans uygun olmalı."""
    adres = t["_adres"]
    for tur in ARAC_TURLERI:
        try:
            v = openai("responses", {"model": MODEL, "tools": [{"type": tur}], "input": DOGRULA_ISTEMI.format(url=adres)}, 240)
            break
        except urllib.error.HTTPError:
            v = None
    if v is None:
        return False, "doğrulama araması yapılamadı"
    metin, kaynaklar = "", set()
    for oge in v.get("output", []):
        if oge.get("type") != "message":
            continue
        for c in oge.get("content", []):
            if c.get("type") == "output_text":
                metin += c.get("text", "")
                for a in c.get("annotations", []) or []:
                    if a.get("type") == "url_citation" and a.get("url"):
                        kaynaklar.add(adres_anahtari(a["url"]))
    if adres_anahtari(adres) not in kaynaklar:
        return False, "sayfa ikinci aramada da kaynak olarak görünmedi"
    m = re.search(r"\{.*\}", metin, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return False, "doğrulama yanıtı okunamadı"
    if j.get("gecerli_sayfa") is not True:
        return False, "sayfa açılamadı"
    lis = lisans_uygun(j.get("lisans"))
    if not lis:
        return False, f"sayfadaki lisans uygun değil ({j.get('lisans')})"
    t["_lisans"] = lis
    return True, f"sayfa doğrulandı, lisans {lis}"


def uygun_tasarimlar(tasarimlar, dogrulanan, kullanilan_adresler):
    """Lisans, site, doğrulanmış bağlantı ve tekrar süzgeci. (uygunlar, elenenler_nedenleriyle)"""
    dogrulanan = {adres_anahtari(a) for a in dogrulanan}
    uygunlar, elenen = [], []
    for t in tasarimlar:
        ad = (t.get("ad") or "").strip()
        adres = temiz_adres(t.get("url"))
        lis = lisans_uygun(t.get("lisans"))
        if not ad or not adres:
            elenen.append((ad or "?", "ad ya da bağlantı yok"))
        elif not site_uygun(adres):
            elenen.append((ad, "kaynak Printables ya da MakerWorld değil"))
        elif adres_anahtari(adres) not in dogrulanan:
            if not lis:
                elenen.append((ad, f"lisans uygun değil ({t.get('lisans')})"))
            elif (t.get("lisans_kaniti") or "").strip():
                t["_lisans"], t["_site"], t["_adres"] = lis, site_uygun(adres), adres
                t["_ikinci_dogrulama"] = True
                uygunlar.append(t)
            else:
                elenen.append((ad, f"bağlantı aramada doğrulanamadı ({adres})"))
        elif not lis:
            elenen.append((ad, f"lisans uygun değil ({t.get('lisans')})"))
        elif not (t.get("lisans_kaniti") or "").strip():
            elenen.append((ad, "lisans kanıtı yok"))
        elif adres in kullanilan_adresler or any(adres_anahtari(k) == adres_anahtari(adres) for k in kullanilan_adresler):
            elenen.append((ad, "daha önce kullanıldı"))
        else:
            t["_lisans"], t["_site"], t["_adres"] = lis, site_uygun(adres), adres
            uygunlar.append(t)
    return uygunlar, elenen


# ---------- Görsel ----------

SAHNE_SISTEM = "Sen bir ürün fotoğrafı yönetmenisin. Yalnızca geçerli JSON döndür."
SAHNE_ISTEMI = """Aşağıdaki 3D baskı tasarımı için, kendi sahnemizde TEMSİLİ bir hikaye görseli prompt'u yaz (İngilizce).

Tasarım: {ad}
Açıklama: {aciklama}
Hareketli parça var mı: {hareketli}

KURALLAR:
- Nesne ev tipi FDM yazıcıyla basılmış gibi görünsün (görünür katman çizgileri, mat plastik), temiz bir atölye tezgâhında, yumuşak mor ve pembe ışıkta, arka plan bulanık, DİKEY kompozisyon, alt üçte bir boş (yazı için).
- Tasarımı birebir kopyalamaya çalışma; nesnenin genel türünü ve ana özelliğini göster.
- Hareket eden mekanizma gösterme: parçalar kapalı ve hareketsiz dursun. İşlev iddiası yok, sadece nesnenin kendisi.
- Görselde yazı, harf, logo, marka, filigran OLMASIN. Gerçek insan yüzü olmasın.
{karakter_kurali}
JSON: {{"prompt": "...", "karakter": true/false}}"""


def sahne_promptu(t, karakterli):
    kural = ("- İsteğe bağlı olarak sahnede 'Doctor Filament' adlı kurgusal karakter nesnenin yanında durabilir (karakter true yap, görünüşünü ANLATMA, kod ekler)."
             if karakterli else "- Karakter ya da insan olmasın (karakter false).")
    c = sohbet_json(SAHNE_SISTEM, SAHNE_ISTEMI.format(ad=t["ad"], aciklama=t.get("aciklama", ""), hareketli="evet" if t.get("hareketli_parca") else "hayır",
                                                       karakter_kurali=kural))
    govde = (c.get("prompt") or "").strip()
    if not govde:
        raise ValueError("boş prompt")
    sonek = ("Photorealistic, vertical composition, no text, no letters, no readable text on any object, no logos, no brand marks, no watermark.")
    karakter = bool(c.get("karakter")) and karakterli
    persona = uret.persona_tarifi()
    parcalar = [govde.rstrip(".") + "."]
    if karakter:
        parcalar.append(persona if persona.endswith(".") else persona + ".")
    parcalar.append(sonek)
    return " ".join(parcalar)


def gorsel_uret(prompt, kalite):
    v = openai("images/generations", {"model": GORSEL_MODELI, "prompt": prompt, "size": "1024x1536", "quality": kalite, "n": 1}, 300)
    b64 = (v.get("data") or [{}])[0].get("b64_json")
    if not b64:
        raise ValueError("görsel yanıtında veri yok")
    return b64


DENETIM_SISTEM = "Sen sosyal medya görsellerini denetleyen titiz bir editörsün. Yalnızca geçerli JSON döndür."
DENETIM_ISTEMI = """Bu görsel, şu 3D baskı nesnesinin TEMSİLİ görseli olarak Instagram hikayesinde yayınlanacak:
Nesne: {ad}. Açıklama: {aciklama}

Görseli titizlikle incele ve şu JSON'u döndür:
{{"yazi_var": okunabilir ya da anlamsız herhangi bir yazı/harf/rakam var mı (true/false),
"logo_var": tanınabilir logo, marka ya da filigran var mı,
"bozuk_anatomi": bozuk el, yüz ya da gerçekçi olmayan insan/kopuk uzuv var mı (insan yoksa false),
"nesne_makul": gösterilen nesne fiziksel olarak mümkün, makul ve ev tipi 3D yazıcıyla basılmış gibi mi,
"tarife_uygun": görsel tarif edilen nesne türünü gösteriyor mu,
"puan": 1-10 genel kalite ve güvenilirlik,
"sorunlar": ["kısa sorun cümleleri"]}}"""


def denetle(b64, t):
    c = sohbet_json(DENETIM_SISTEM, DENETIM_ISTEMI.format(ad=t["ad"], aciklama=t.get("aciklama", "")), b64)
    try:
        puan = float(c.get("puan", 0))
    except (TypeError, ValueError):
        puan = 0.0
    gecti = (not c.get("yazi_var") and not c.get("logo_var") and not c.get("bozuk_anatomi")
             and c.get("nesne_makul") is True and c.get("tarife_uygun") is True and puan >= 7)
    return gecti, {"puan": puan, "sorunlar": [str(s)[:100] for s in (c.get("sorunlar") or [])][:5]}


def etiketli_jpeg(png_b64, t, cikti):
    """Görseli 1080x1920'ye yerleştir, YZ etiketini ve atfı işle, JPEG yaz."""
    font = SU.font_bul()
    satirlar = [YAPAY_ZEKA_ETIKETI, ""] + SU.sar(f"Tasarım: {t['ad']}", 44).split("\n")[:2] + \
        SU.sar(f"Tasarımcı: {t.get('tasarimci') or '?'} · {t['_lisans']}", 44).split("\n")[:1] + [f"Kaynak: {t['_site']}"]
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        (g / "a.png").write_bytes(base64.b64decode(png_b64))
        (g / "yazi.txt").write_text("\n".join(satirlar), encoding="utf-8")
        filtre = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:6,eq=brightness=-0.18[bg];"
                  "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-70[v0];"
                  f"[v0]drawtext=fontfile={font}:textfile={g / 'yazi.txt'}:fontsize=34:fontcolor=white:line_spacing=10:box=1:boxcolor=black@0.62:"
                  "boxborderw=22:expansion=none:x=(w-text_w)/2:y=h-text_h-340,format=yuvj420p[v]")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(g / "a.png"), "-filter_complex", filtre, "-map", "[v]",
                            "-frames:v", "1", "-q:v", "3", str(cikti)], capture_output=True, text=True)
        if r.returncode != 0 or not cikti.exists():
            raise RuntimeError("görsel hazırlanamadı: " + (r.stderr or "")[-160:])


# ---------- Ayar, harcama, kayıt ----------

def json_oku(yol, varsayilan):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(varsayilan))


def ayar_oku():
    a = dict(VARSAYILAN)
    a.update(json_oku(URETIM, {}))
    return a


def yaz(yol, veri):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def harcama_say(h, an):
    gun, ay = an.astimezone(H.TR).strftime("%Y-%m-%d"), an.astimezone(H.TR).strftime("%Y-%m")
    return h.get("gunler", {}).get(gun, {}).get("gorsel", 0), h.get("aylar", {}).get(ay, {}).get("gorsel", 0), gun, ay


def harcama_ekle(h, gun, ay):
    h.setdefault("gunler", {}).setdefault(gun, {"gorsel": 0})["gorsel"] += 1
    h.setdefault("aylar", {}).setdefault(ay, {"gorsel": 0})["gorsel"] += 1
    # eski günleri temizle (son 40 gün)
    for k in sorted(h["gunler"])[:-40]:
        h["gunler"].pop(k, None)


def yeni_kimlik(sira):
    z = H.simdi().astimezone(datetime.timezone.utc)
    return f"h{z:%Y%m%d-%H%M%S}-{chr(97 + sira % 26)}{(sira * 7 + 3) % 10}{chr(97 + (sira * 3 + 5) % 26)}"


def calis(a):
    ayar = ayar_oku()
    an = H.simdi()
    if not ayar["aktif"] and not a.hemen:
        print("Karar: bekle (görsel üretimi kapalı: aktif=false)")
        return 0
    ogeler = H.kuyruk_oku()
    bekleyen = sum(1 for o in ogeler if o.get("durum") in ("planli", "onay_bekliyor"))
    if bekleyen >= ayar["kuyruk_hedefi"] and not a.hemen:
        print(f"Karar: bekle (kuyruk yeterli: {bekleyen} hikaye bekliyor, hedef {ayar['kuyruk_hedefi']})")
        return 0
    harcama = json_oku(HARCAMA, {})
    gun_say, ay_say, gun, ay = harcama_say(harcama, an)
    if gun_say >= ayar["gunluk_gorsel_siniri"] or ay_say >= ayar["aylik_gorsel_siniri"]:
        print(f"Karar: bekle (harcama sınırı: bugün {gun_say}/{ayar['gunluk_gorsel_siniri']}, bu ay {ay_say}/{ayar['aylik_gorsel_siniri']})")
        return 0
    H.ffmpeg_hazir()

    print("Tasarımlar aranıyor (Printables, MakerWorld)…")
    tasarimlar, dogrulanan = tasarim_ara()
    kullanilan = json_oku(KULLANILAN, [])
    print(f"Aramanın döndürdüğü kaynak sayısı: {len(dogrulanan)}")
    for kaynak in sorted(dogrulanan)[:15]:
        print(f"  kaynak: {kaynak}")
    uygunlar, elenen = uygun_tasarimlar(tasarimlar, dogrulanan, {temiz_adres(k.get("url")) for k in kullanilan})
    print(f"Bulunan {len(tasarimlar)}, uygun {len(uygunlar)} (CC0 / CC BY, doğrulanmış). Elenenler:")
    for ad, neden in elenen:
        print(f"  - {ad}: {neden}")
    kesin = []
    hedef_sayi = max(1, min(int(ayar["gunluk_uretim"]), 12))
    for t in uygunlar:
        if len(kesin) >= hedef_sayi:
            break
        if t.get("_ikinci_dogrulama"):
            ok, neden = sayfa_dogrula(t)
            print(f"  ikinci doğrulama: {t['ad']}: {neden}")
            if not ok:
                continue
        kesin.append(t)
    uygunlar = kesin
    if not uygunlar:
        print("Uygun tasarım yok; hiçbir şey üretilmedi.")
        return 0

    hedef = max(1, min(int(ayar["gunluk_uretim"]), 12))
    uretilen, atlanan = [], []
    kategoriler = set()
    sira = 0
    for t in uygunlar:
        if len(uretilen) >= hedef:
            break
        if t.get("kategori") in kategoriler and len(uygunlar) - len(uretilen) > hedef - len(uretilen):
            continue   # çeşitlilik: aynı kategoriden art arda seçme (yeterince aday varken)
        kabul = None
        for deneme in range(3):
            if gun_say >= ayar["gunluk_gorsel_siniri"] or ay_say >= ayar["aylik_gorsel_siniri"]:
                print("Harcama sınırına ulaşıldı; durduruluyor.")
                break
            try:
                prompt = sahne_promptu(t, karakterli=(sira % 3 == 2))
                b64 = gorsel_uret(prompt, ayar["kalite"])
            except urllib.error.HTTPError as e:
                print(f"  görsel üretilemedi ({http_hata_ozeti(e)})")
                atlanan.append((t["ad"], http_hata_ozeti(e)))
                break
            except Exception as e:
                print(f"  görsel üretilemedi ({type(e).__name__}: {str(e)[:100]})")
                break
            harcama_ekle(harcama, gun, ay)
            gun_say += 1
            ay_say += 1
            try:
                gecti, kontrol = denetle(b64, t)
            except Exception as e:
                print(f"  denetim çalışmadı ({type(e).__name__}); şüphede yayınlanmaz, atlanıyor")
                gecti, kontrol = False, {"puan": 0, "sorunlar": ["denetim çalışmadı"]}
            print(f"  {t['ad']}: deneme {deneme + 1}, denetim {'GEÇTİ' if gecti else 'GEÇMEDİ'} (puan {kontrol['puan']}) {kontrol['sorunlar']}")
            if gecti:
                kabul = (b64, kontrol, deneme + 1)
                break
        yaz(HARCAMA, harcama)
        sira += 1
        if not kabul:
            atlanan.append((t["ad"], "denetimden geçemedi ya da üretilemedi"))
            continue
        kimlik = yeni_kimlik(sira)
        while (H.KUYRUK / f"{kimlik}.json").exists():
            sira += 1
            kimlik = yeni_kimlik(sira)
        gorsel_yolu = f"hikaye/gorseller/{kimlik}.jpg"
        (KOK / "hikaye" / "gorseller").mkdir(parents=True, exist_ok=True)
        etiketli_jpeg(kabul[0], t, KOK / gorsel_yolu)
        kategoriler.add(t.get("kategori"))
        oge = {"id": kimlik, "kaynak": "uretim", "durum": "planli" if ayar["mod"] == "otomatik" else "onay_bekliyor",
               "olusturma": H.simdi().strftime("%Y-%m-%dT%H:%M:%S.000Z"), "gorsel": gorsel_yolu, "baslik": t["ad"][:80],
               "atif": {"ad": t["ad"], "tasarimci": t.get("tasarimci"), "lisans": t["_lisans"], "url": t["_adres"], "site": t["_site"]},
               "kontrol": {"puan": kabul[1]["puan"], "deneme": kabul[2], "sorunlar": kabul[1]["sorunlar"]},
               "yayin": None, "hata": "", "deneme": 0}
        yaz(H.KUYRUK / f"{kimlik}.json", oge)
        kullanilan.append({"url": t["_adres"], "ad": t["ad"], "tarih": H.simdi().strftime("%Y-%m-%d")})
        yaz(KULLANILAN, kullanilan[-200:])
        uretilen.append(t["ad"])

    print(f"Üretilen: {len(uretilen)} ({', '.join(uretilen) or '-'}). Atlanan: {len(atlanan)}. Bugün görsel: {gun_say}, bu ay: {ay_say}.")
    if a.git:
        H.git_kaydet(f"Hikaye üretici: {len(uretilen)} yeni hikaye", [KOK / "hikaye"])
    if uretilen:
        if ayar["mod"] == "otomatik":
            H.bildir("Yeni yapay zekâ hikayeleri hazır", f"{len(uretilen)} hikaye kuyruğa girdi; ayarladığın saatlerde yayınlanacak.", adres="/", etiket="uretim")
        else:
            H.bildir("Hikayeler onayını bekliyor", f"{len(uretilen)} yapay zekâ hikayesi panelde onay bekliyor.", adres="/", etiket="uretim")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hemen", action="store_true", help="aktif=false ve kuyruk dolu olsa bile bir kez çalış (harcama sınırları geçerli)")
    ap.add_argument("--git", action="store_true", help="Sonucu depoya yaz ve it")
    ap.add_argument("--lisans-dene", help="Bir lisans metninin süzgeçten geçip geçmediğini yaz")
    a = ap.parse_args()
    if a.lisans_dene is not None:
        print(lisans_uygun(a.lisans_dene) or "UYGUN DEĞİL")
        return
    sys.exit(calis(a))


if __name__ == "__main__":
    main()
