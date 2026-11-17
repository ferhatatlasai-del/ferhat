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
import html
import ipaddress
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402
import thingiverse as TV  # noqa: E402
import shorts_uret as SU  # noqa: E402
import uret  # noqa: E402

KOK = H.KOK
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
GORSEL_MODELI = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"
URETIM = KOK / "hikaye" / "uretim.json"
HARCAMA = KOK / "hikaye" / "harcama.json"
KULLANILAN = KOK / "hikaye" / "kullanilan.json"
ADAYLAR = KOK / "hikaye" / "adaylar.json"
ADAY_OMRU_GUN = 4   # aynı arama sonucu bu kadar gün yeniden kullanılır (her çalışmada pahalı arama yapılmaz)
IZINLI_SITELER = ("printables.com", "makerworld.com", "thingiverse.com")
VARSAYILAN = {"aktif": False, "mod": "otomatik", "gunluk_uretim": 3, "gunluk_gorsel_siniri": 6,
              "aylik_gorsel_siniri": 90, "kalite": "low", "kuyruk_hedefi": 6, "referans": "zorunlu"}
ARAC_TURLERI = ["web_search", "web_search_preview"]
BOT_ADI = "Mozilla/5.0 (compatible; DoktorFilamentBot/1.0; tasarim atfi icin tek sayfa onizleme)"
REFERANS_EN_BUYUK = 8 * 1024 * 1024
SAHNELER = [
    "a clean hobbyist workshop bench with a blurred pegboard and filament spools in the background",
    "a tidy desk with a blurred computer monitor and a small plant in the background",
    "a wooden shelf in a cozy maker room with blurred tools in the background",
    "a light concrete workbench with a blurred row of storage drawers in the background",
]
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
    if re.search(r"\bcc0\b|public domain dedication|\bcc zero\b|^public domain$", t):
        return "CC0"
    if re.search(r"\bcc by\b(?!\s*(nc|nd|sa))", t) or re.fullmatch(r"(creative commons )?attribution( 4 0| 3 0| 2 0)?( international)?( \(?cc by\)?)?", t):
        return "CC BY"
    return None


def lisans_acik_red(metin):
    """Lisans metni açıkça kısıtlayıcı mı (NC/ND/SA, standart dijital dosya vb.)? Belirsiz/eksik metin için False."""
    t = " ".join((metin or "").lower().replace("-", " ").replace("_", " ").split())
    return bool(re.search(r"\b(nc|nd|sa)\b|noncommercial|non commercial|noderiv|no deriv|sharealike|share alike|standard digital file|all rights reserved", t))


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


def sohbet_json(sistem, kullanici, resim_b64=None, ek_resim_b64=None):
    icerik = [{"type": "text", "text": kullanici}]
    for resim, mime in ((resim_b64, "image/png"), (ek_resim_b64, "image/jpeg")):
        if resim:
            icerik.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64," + resim, "detail": "low"}})
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
sitelerinde (sonuçların çoğu printables.com'dan olsun) şu sıralar (son 1-4 hafta) popüler olan, ev tipi bir 3D yazıcıyla basılabilen 8-10 tasarım bul.

SEÇİM ÖLÇÜTÜ: Görsel olarak net ayırt edilen, basılı hâli fotoğrafta çekici duran, günlük hayatta kullanışlı ya da ilginç somut bir NESNE olsun
(organizer, tutucu, aksesuar, küçük alet, dekor). Eğitim/öğretici dosyası, yalnızca metin ya da kod, jeton/madalya/logo, basit geometrik parça, dosya koleksiyonu ve karakter/figür koleksiyonu DEĞİL.

ARAMA İPUCU: Arama sorgularına lisans terimlerini de ekle (örn. "printables CC0 popular", "printables public domain CC0 model", "makerworld CC0",
"Creative Commons Attribution CC BY printables"); lisansı sayfada açıkça CC0 ya da CC BY yazan tasarımları öncelikle ara.

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
- aciklama: İngilizce, 2-3 cümle: nesnenin ne olduğu ve BASILI HÂLİNİN görünüşü (genel şekil ve oran, parça sayısı, belirgin ayrıntılar, renk varsa, boyut), YALNIZCA sayfadaki açıklama ve fotoğraflara dayan, tahmin etme
- hareketli_parca: true/false (menteşe, kilit, katlanma, dönen parça var mı)
- kategori: kısa etiket (masa düzeni, mutfak, oyuncak, araç, bahçe vb.)
- neden_populer: Türkçe 1 cümle
- trend_konusu: aşağıdaki TREND listesinden hangisine uyuyorsa o konunun adı (aynen), uymuyorsa boş string

Yalnızca geçerli JSON döndür: {"tasarimlar":[{...}]}"""


def arama_istegi(istem, sure):
    """Web aramasını ZORUNLU kılarak ama kısıtlı (az arama, küçük bağlam) çağırır. Parametre kabul edilmezse sade biçimlere düşer.
    (yanıt, arama_sayısı)"""
    for tur in ARAC_TURLERI:
        for ad, arac_ek, ek in (("kısıtlı", {"search_context_size": "low"}, {"tool_choice": "required", "max_tool_calls": 2}),
                                ("zorunlu", {}, {"tool_choice": "required"}), ("sade", {}, {})):
            govde = {"model": MODEL, "tools": [dict({"type": tur}, **arac_ek)], "input": istem}
            govde.update(ek)
            try:
                v = openai("responses", govde, sure)
                aramalar = [o for o in v.get("output", []) if str(o.get("type", "")).startswith("web_search")]
                return v, len(aramalar)
            except urllib.error.HTTPError as e:
                print(f"UYARI: '{tur}' ({ad}) olmadı ({http_hata_ozeti(e)})")
    return None, 0


TREND_DOSYASI = KOK / "ajan" / "trendler.json"
TREND_EN_ESKI_GUN = 7


def trend_yonlendirmesi():
    """Trend ajanının son bulguları (en çok 7 günlük) arama istemine eklenir. (metin, konu_listesi)"""
    try:
        v = json.loads(TREND_DOSYASI.read_text(encoding="utf-8"))
        z = datetime.datetime.strptime(v["tarih"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        if (H.simdi() - z).total_seconds() > TREND_EN_ESKI_GUN * 86400:
            return "", []
    except Exception:
        return "", []
    konular = [o["konu"].strip() for o in v.get("oneriler", [])
               if o.get("konu") and o.get("basilabilir", True) and str(o.get("risk", "yok")).lower().startswith("yok")][:8]
    kacin = [k for k in v.get("asiri_kullanilan", []) if k][:5]
    if not konular:
        return "", []
    metin = ("TREND YÖNLENDİRMESİ (Trend ajanının son bulguları): Listeleyeceğin tasarımların YARISI şu güncel trend konularından birine uysun,\n"
             "diğer yarısı serbest (çeşitlilik için):\n" + "\n".join(f"- {k}" for k in konular) + "\n"
             + (("Şu klişe konulardan kaçın: " + "; ".join(kacin) + "\n") if kacin else "") + "\n")
    return metin, konular


def tasarim_ara():
    """(tasarimlar, dogrulanan_adresler). Web arama aracı bulunamazsa hata."""
    trend_metni, konular = trend_yonlendirmesi()
    print(f"Trend ajanı yönlendirmesi: {len(konular)} konu" + (f" ({'; '.join(k[:30] for k in konular[:4])}…)" if konular else " (trend verisi yok ya da 7 günden eski)"))
    istem = ARAMA_ISTEMI.replace("KESİN KURALLAR:", trend_metni + "KESİN KURALLAR:", 1) if trend_metni else ARAMA_ISTEMI
    veri, arama_sayisi = arama_istegi(istem, 300)
    if veri is None:
        hata("Web arama aracı kullanılamadı; tasarım araştırması yapılamadı.")
    print(f"Modelin yaptığı web araması: {arama_sayisi} kez")
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
    return tasarim_listesi_oku(metin), adresler


def json_nesnesi_bul(metin):
    """Metindeki ilk geçerli JSON nesnesini bulur (öncesinde/sonrasında fazladan yazı ya da kod çiti olsa da). Bulamazsa None."""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", metin or ""):
        try:
            nesne, _ = dec.raw_decode(metin[m.start():])
            if isinstance(nesne, dict):
                return nesne
        except json.JSONDecodeError:
            continue
    return None


ONARIM_ISTEMI = """Aşağıdaki metin, 3D baskı tasarımlarının listesini içeriyor ama JSON biçimi bozuk. İçindeki tasarımları bozmadan,
UYDURMA EKLEMEDEN geçerli JSON'a çevir: {"tasarimlar":[{"ad":"","tasarimci":"","lisans":"","lisans_kaniti":"","url":"","aciklama":"","hareketli_parca":false,"kategori":"","neden_populer":"","trend_konusu":""}]}
Eksik alanları boş bırak. Okunamayan kayıtları atla.

METİN:
"""


def tasarim_listesi_oku(metin):
    """Arama yanıtından tasarım listesi. Biçim bozuksa önce toparlar, olmazsa ucuz bir metin çağrısıyla onarır (yeniden arama yapmaz)."""
    nesne = json_nesnesi_bul(metin)
    if nesne is None or not isinstance(nesne.get("tasarimlar"), list):
        print("UYARI: arama yanıtı geçerli JSON değil; ucuz bir onarım çağrısı deneniyor.")
        try:
            nesne = sohbet_json("Sen JSON onarıcısın. Yalnızca geçerli JSON döndür.", ONARIM_ISTEMI + (metin or "")[:12000])
        except Exception as e:
            hata(f"Arama yanıtı okunamadı ve onarılamadı ({type(e).__name__}).")
    liste = nesne.get("tasarimlar") if isinstance(nesne, dict) else None
    if not isinstance(liste, list):
        hata("Arama yanıtında tasarım listesi bulunamadı.")
    return [t for t in liste if isinstance(t, dict)]


def uygun_tasarimlar(tasarimlar, dogrulanan, kullanilan_adresler):
    """Lisans, site, bağlantı biçimi ve tekrar süzgeci. (uygunlar, elenenler_nedenleriyle)

    Modelin açıkça CC0 ya da CC BY dediği ve lisans alıntısı verdiği tasarımlar kabul edilir (NC/ND/SA, standart dijital dosya ve
    belirsiz lisanslar elenir). Lisans sayfadan bağımsız teyit edilemiyorsa kayıtta lisans_teyit=False olarak işaretlenir;
    panel bunu gösterir ve kullanıcı tasarım sayfasından kontrol edebilir."""
    dogrulanan = {adres_anahtari(a) for a in dogrulanan}
    kullanilan_anahtarlar = {adres_anahtari(k) for k in kullanilan_adresler}
    uygunlar, elenen = [], []
    for t in tasarimlar:
        ad = (t.get("ad") or "").strip()
        adres = temiz_adres(t.get("url"))
        lis = lisans_uygun(t.get("lisans"))
        if not ad or not adres:
            elenen.append((ad or "?", "ad ya da bağlantı yok"))
        elif not site_uygun(adres) or not re.search(r"/models?/\d+", adres):
            elenen.append((ad, "bağlantı Printables/MakerWorld tasarım sayfası biçiminde değil"))
        elif adres_anahtari(adres) in kullanilan_anahtarlar:
            elenen.append((ad, "daha önce kullanıldı"))
        elif not lis and not lisans_acik_red(t.get("lisans")) and site_uygun(adres) == "printables.com":
            # model lisansı net yazamadı: Printables'ın kendi veri servisinden sorgulanacak
            t["_lisans"], t["_site"], t["_adres"], t["_teyit"] = None, "printables.com", adres, False
            uygunlar.append(t)
        elif not lis:
            elenen.append((ad, f"lisans uygun değil ({t.get('lisans')})"))
        elif not (t.get("lisans_kaniti") or "").strip():
            elenen.append((ad, "lisans kanıtı yok"))
        else:
            t["_lisans"], t["_site"], t["_adres"] = lis, site_uygun(adres), adres
            t["_teyit"] = adres_anahtari(adres) in dogrulanan
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
- Açıklamadaki nesneyi SADAKATLE göster: genel şekil, oran, parça sayısı ve belirgin ayrıntılar açıklamadakiyle aynı olsun. Yaratıcı yorum, ekstra parça ya da başka bir nesne ekleme. Tek bir nesne, sade arka plan.
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


# ---------- Referans fotoğraf ----------

class ReferansYok(Exception):
    """Tasarım sayfasından referans fotoğraf alınamadı (neden mesajda)."""


def genel_adres_mi(adres):
    """Yalnızca https ve herkese açık adresler (yerel/özel ağ adreslerine istek atılmaz)."""
    if os.environ.get("HIKAYE_TEST_SAYFA_TABANI"):
        return True   # yalnızca testte
    p = urllib.parse.urlparse(adres)
    if p.scheme != "https" or not p.hostname:
        return False
    try:
        for bilgi in socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(bilgi[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except Exception:
        return False
    return True


def sayfa_adresi_cevir(adres):
    taban = os.environ.get("HIKAYE_TEST_SAYFA_TABANI")   # yalnızca test: sahte sunucuya yönlendir
    if not taban:
        return adres
    p = urllib.parse.urlparse(adres)
    return taban.rstrip("/") + p.path


def http_al(adres, sure=25, en_buyuk=2 * 1024 * 1024):
    r = urllib.request.Request(adres, headers={"User-Agent": BOT_ADI, "Accept": "text/html,image/*;q=0.8"})
    with urllib.request.urlopen(r, timeout=sure) as y:
        tur = (y.headers.get("Content-Type") or "").lower()
        veri = y.read(en_buyuk + 1)
    if len(veri) > en_buyuk:
        raise ReferansYok("dosya çok büyük")
    return veri, tur


def og_gorsel_adresi(html_metni, sayfa_adresi):
    """Sayfanın paylaşım önizleme (og:image) fotoğrafının adresi."""
    for etiket in re.findall(r"<meta\b[^>]*>", html_metni, re.I):
        if re.search(r'(?:property|name)\s*=\s*["\'](?:og:image|og:image:url|twitter:image)["\']', etiket, re.I):
            m = re.search(r'content\s*=\s*["\']([^"\']+)["\']', etiket, re.I)
            if m:
                return urllib.parse.urljoin(sayfa_adresi, html.unescape(m.group(1)).strip())
    return None


def referans_fotografi(sayfa, gorsel_adresi=None):
    """Tasarımın ana fotoğrafını (yalnızca tek görsel) indirir; en çok 1024 px JPEG bayt olarak döndürür.
    Fotoğraf adresi verilmişse (ör. Printables servisinden) sayfa açılmaz; yoksa sayfanın og:image adresi kullanılır.
    Depoya yazılmaz, yalnızca bellekte kullanılır."""
    gorsel = gorsel_adresi
    if not gorsel:
        try:
            veri, _ = http_al(sayfa_adresi_cevir(sayfa), 25, 3 * 1024 * 1024)
        except urllib.error.HTTPError as e:
            raise ReferansYok(f"sayfa açılamadı (HTTP {e.code})")
        except Exception as e:
            raise ReferansYok(f"sayfa açılamadı ({type(e).__name__})")
        gorsel = og_gorsel_adresi(veri.decode("utf-8", "ignore"), sayfa)
    if not gorsel:
        raise ReferansYok("sayfada önizleme fotoğrafı bulunamadı")
    if not genel_adres_mi(gorsel):
        raise ReferansYok("fotoğraf adresi güvenli değil")
    try:
        ham, tur = http_al(sayfa_adresi_cevir(gorsel), 30, REFERANS_EN_BUYUK)
    except urllib.error.HTTPError as e:
        raise ReferansYok(f"fotoğraf indirilemedi (HTTP {e.code})")
    except ReferansYok:
        raise
    except Exception as e:
        raise ReferansYok(f"fotoğraf indirilemedi ({type(e).__name__})")
    if tur and not tur.startswith("image/"):
        raise ReferansYok("fotoğraf adresi görsel döndürmedi")
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        (g / "ham").write_bytes(ham)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(g / "ham"), "-vf", "scale='min(1024,iw)':-2",
                            "-frames:v", "1", "-q:v", "3", str(g / "r.jpg")], capture_output=True, text=True)
        if r.returncode != 0 or not (g / "r.jpg").exists():
            raise ReferansYok("fotoğraf okunamadı")
        cikti = (g / "r.jpg").read_bytes()
    boy = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", "-"],
                         input=cikti, capture_output=True).stdout.decode().strip()
    try:
        w, h = [int(x) for x in boy.split("x")]
    except ValueError:
        w = h = 0
    if min(w, h) < 300:
        raise ReferansYok(f"fotoğraf çok küçük ({boy or '?'})")
    return cikti


def coklu_parca(alanlar, dosyalar):
    """multipart/form-data gövdesi. (govde, icerik_turu)"""
    sinir = "----hikaye" + os.urandom(8).hex()
    parcalar = []
    for ad, deger in alanlar.items():
        parcalar.append(f'--{sinir}\r\nContent-Disposition: form-data; name="{ad}"\r\n\r\n{deger}\r\n'.encode())
    for ad, dosya_adi, tur, veri in dosyalar:
        parcalar.append(f'--{sinir}\r\nContent-Disposition: form-data; name="{ad}"; filename="{dosya_adi}"\r\nContent-Type: {tur}\r\n\r\n'.encode() + veri + b"\r\n")
    parcalar.append(f"--{sinir}--\r\n".encode())
    return b"".join(parcalar), f"multipart/form-data; boundary={sinir}"


REFERANSLI_ISTEM = ("Recreate the 3D-printed object shown in the reference photo faithfully: keep exactly the same shape, proportions, number of parts, "
                    "visible details and colors. Place it as a single hero object in a new scene: {sahne}, soft purple and pink ambient light, "
                    "photorealistic product photo, vertical composition, object centered in the upper two thirds with empty space in the bottom third. "
                    "Remove the original background and any hands, text, logos, watermarks and brand marks that appear in the reference. "
                    "No text, no letters, no logos anywhere.")


def gorsel_duzenle(prompt, referans_jpeg, kalite):
    """Referans fotoğrafı temel alıp yeni sahnede yeniden çizer (images/edits). Model sırası gorsel_uret ile aynı."""
    global _gorsel_modelleri
    anahtar = os.environ.get("OPENAI_API_KEY")
    son_hata = None
    for model in list(gorsel_modelleri()):
        govde, tur = coklu_parca({"model": model, "prompt": prompt, "size": "1024x1536", "quality": kalite, "n": "1"},
                                 [("image[]", "referans.jpg", "image/jpeg", referans_jpeg)])
        r = urllib.request.Request(f"{OPENAI}/images/edits", data=govde, method="POST",
                                   headers={"Content-Type": tur, "Authorization": f"Bearer {anahtar}"})
        try:
            with urllib.request.urlopen(r, timeout=300) as y:
                v = json.load(y)
        except urllib.error.HTTPError as e:
            son_hata = e
            if e.code in (400, 403, 404):
                print(f"  görsel modeli '{model}' düzenlemede kullanılamadı ({http_hata_ozeti(e)})")
                continue
            raise
        b64 = (v.get("data") or [{}])[0].get("b64_json")
        if not b64:
            raise ValueError("görsel yanıtında veri yok")
        if _gorsel_modelleri[0] != model:
            _gorsel_modelleri = [model] + [m for m in _gorsel_modelleri if m != model]
        return b64
    raise son_hata or ValueError("kullanılabilir görsel modeli yok")


# ---------- Printables veri servisi ----------

PRINTABLES_API = os.environ.get("PRINTABLES_API") or "https://api.printables.com/graphql/"
PRINTABLES_MEDYA = os.environ.get("PRINTABLES_MEDYA") or "https://media.printables.com/"
PRINTABLES_SORGULAR = [
    "query P($id: ID!) { print(id: $id) { id name license { id name abbreviation } user { publicUsername } images { filePath } } }",
    "query P($id: ID!) { print(id: $id) { id name license { id name } user { publicUsername } images { filePath } } }",
]
_introspeksiyon_yazildi = False


def graphql(sorgu, degiskenler=None):
    govde = json.dumps({"query": sorgu, "variables": degiskenler or {}}).encode()
    r = urllib.request.Request(PRINTABLES_API, data=govde, method="POST",
                               headers={"Content-Type": "application/json", "User-Agent": BOT_ADI, "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as y:
        return json.load(y)


def printables_numara(adres):
    m = re.search(r"printables\.com/(?:[a-z]{2}(?:-[a-z]{2,4})?/)?model/(\d+)", adres or "", re.I)
    return m.group(1) if m else None


def printables_bilgi(adres):
    """Printables'ın kendi veri servisinden lisans, tasarımcı ve fotoğraf adresi. (bilgi_sozlugu, hata_metni)
    Sözlük: lisans_metni, tasarimci, ad, gorsel (tam adres ya da None)."""
    global _introspeksiyon_yazildi
    numara = printables_numara(adres)
    if not numara:
        return None, "Printables tasarım numarası bulunamadı"
    son = "bilinmeyen hata"
    for sorgu in PRINTABLES_SORGULAR:
        try:
            v = graphql(sorgu, {"id": numara})
        except urllib.error.HTTPError as e:
            return None, f"servis HTTP {e.code}"
        except Exception as e:
            return None, f"servis ulaşılamadı ({type(e).__name__})"
        hatalar = v.get("errors")
        pr = (v.get("data") or {}).get("print") if not hatalar else None
        if pr:
            lis = pr.get("license") or {}
            resimler = [i.get("filePath") for i in (pr.get("images") or []) if i.get("filePath")]
            gorsel = urllib.parse.urljoin(PRINTABLES_MEDYA, resimler[0]) if resimler else None
            return {"lisans_metni": " ".join(x for x in (lis.get("name"), lis.get("abbreviation")) if x),
                    "tasarimci": (pr.get("user") or {}).get("publicUsername"), "ad": pr.get("name"), "gorsel": gorsel}, ""
        son = "; ".join(str(h.get("message"))[:120] for h in (hatalar or [])[:2]) or "tasarım bulunamadı"
    if not _introspeksiyon_yazildi:   # teşhis: gerçek alan adlarını günlüğe yaz
        _introspeksiyon_yazildi = True
        try:
            t = graphql('{ __type(name: "PrintType") { fields { name } } }')
            alanlar = [f["name"] for f in (((t.get("data") or {}).get("__type") or {}).get("fields") or [])]
            print(f"  [teşhis] PrintType alanları: {', '.join(alanlar[:60]) or 'okunamadı'}")
        except Exception as e:
            print(f"  [teşhis] alan listesi alınamadı ({type(e).__name__})")
    return None, f"servis yanıtı kullanılamadı ({son})"


def printables_dogrula(t):
    """Printables adayı için lisansı sitenin kendi verisiyle kanıtla. (durum, neden)
    durum: True=doğrulandı (lisans uygun), False=lisans uygun değil (elen), None=servis kullanılamadı (eski davranış)."""
    bilgi, hata_metni = printables_bilgi(t["_adres"])
    if not bilgi:
        return None, hata_metni
    lis = lisans_uygun(bilgi["lisans_metni"])
    if not lis:
        return False, f"sitenin kendi verisinde lisans uygun değil ({bilgi['lisans_metni'] or 'yok'})"
    t["_lisans"], t["_teyit"], t["_gorsel_adresi"] = lis, True, bilgi.get("gorsel")
    if bilgi.get("tasarimci"):
        t["tasarimci"] = bilgi["tasarimci"]
    if bilgi.get("ad"):
        t["ad"] = bilgi["ad"]
    return True, f"lisans sitenin verisinde doğrulandı ({bilgi['lisans_metni']})"


# ---------- Thingiverse kaynağı ----------

def trend_terimleri():
    """Trend ajanının İngilizce arama terimleri: [(terim, konu)]. Trend verisi yoksa boş."""
    try:
        v = json.loads(TREND_DOSYASI.read_text(encoding="utf-8"))
        z = datetime.datetime.strptime(v["tarih"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        if (H.simdi() - z).total_seconds() > TREND_EN_ESKI_GUN * 86400:
            return []
        return [((o.get("arama_terimi_en") or "").strip(), o.get("konu", "").strip()) for o in v.get("oneriler", [])
                if (o.get("arama_terimi_en") or "").strip() and str(o.get("risk", "yok")).lower().startswith("yok")][:6]
    except Exception:
        return []


def thingiverse_adaylari(kullanilan_anahtarlar, sayi):
    """Thingiverse'in resmi servisinden CC0/CC BY lisanslı, popüler tasarımlar (lisans ve fotoğraf sitenin kendi verisinden).
    Önce trend terimleriyle aranır (trend uyumlu), sonra genel popüler listeden tamamlanır. Anahtar yoksa boş döner."""
    if not TV.hazir():
        print("Thingiverse kaynağı kapalı (THINGIVERSE_TOKEN tanımlı değil).")
        return []
    ozetler, konu_haritasi = [], {}
    try:
        for terim, konu in trend_terimleri()[:4]:
            for o in TV.ara(terim, 8)[:8]:
                if o.get("id") and o["id"] not in konu_haritasi:
                    ozetler.append(o)
                    konu_haritasi[o["id"]] = konu
        for o in TV.populer(30):
            if o.get("id") and o["id"] not in konu_haritasi:
                ozetler.append(o)
                konu_haritasi[o["id"]] = ""
    except TV.ThingiverseHata as e:
        print(f"Thingiverse listesi alınamadı ({e})")
        return []
    adaylar, bakilan, elenen_say = [], 0, {}
    for o in ozetler:
        if len(adaylar) >= sayi or bakilan >= 25:
            break
        adres = o.get("public_url") or f"https://www.thingiverse.com/thing:{o['id']}"
        if adres_anahtari(adres) in kullanilan_anahtarlar:
            continue
        bakilan += 1
        try:
            b = TV.kayit_bilgisi(TV.detay(o["id"]))
        except TV.ThingiverseHata as e:
            print(f"  Thingiverse {o.get('id')}: ayrıntı alınamadı ({e})")
            continue
        lis = lisans_uygun(b["lisans"])
        if not lis:
            elenen_say[b["lisans"] or "lisans yok"] = elenen_say.get(b["lisans"] or "lisans yok", 0) + 1
            continue
        if not b["gorsel"] or not b["ad"]:
            continue
        adaylar.append({"ad": b["ad"], "tasarimci": b["tasarimci"], "lisans": b["lisans"], "lisans_kaniti": f"Thingiverse servisi: {b['lisans']}",
                        "url": b["url"], "aciklama": b["aciklama"] or b["ad"], "hareketli_parca": False, "kategori": "",
                        "trend_konusu": konu_haritasi.get(o["id"], ""), "_lisans": lis, "_site": "thingiverse.com", "_adres": temiz_adres(b["url"]),
                        "_teyit": True, "_gorsel_adresi": b["gorsel"]})
    ozet = ", ".join(f"{k} x{v}" for k, v in sorted(elenen_say.items(), key=lambda x: -x[1])[:5])
    print(f"Thingiverse: {len(ozetler)} popüler tasarım listelendi, {bakilan} tanesine bakıldı, {len(adaylar)} uygun (CC0/CC BY)." + (f" Elenen lisanslar: {ozet}" if ozet else ""))
    return adaylar


def openai_get(yol, sure=60):
    anahtar = os.environ.get("OPENAI_API_KEY")
    r = urllib.request.Request(f"{OPENAI}/{yol}", headers={"Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(r, timeout=sure) as y:
        return json.load(y)


def surum_anahtari(model_adi):
    """gpt-image-1 < gpt-image-1.5 < gpt-image-2 gibi adları sürüme göre sıralamak için."""
    return [int(x) for x in re.findall(r"\d+", model_adi)] or [0]


_gorsel_modelleri = None


def gorsel_modelleri():
    """Denenecek görsel modelleri: önce açıkça ayarlanan, sonra hesabın erişebildiği gpt-image* (yeniden eskiye), sonra varsayılan."""
    global _gorsel_modelleri
    if _gorsel_modelleri is not None:
        return _gorsel_modelleri
    aday = []
    if os.environ.get("OPENAI_IMAGE_MODEL"):
        aday.append(os.environ["OPENAI_IMAGE_MODEL"])
    try:
        liste = [m["id"] for m in openai_get("models").get("data", [])]
        tum = [m for m in liste if m.startswith("gpt-image") and "mini" not in m]
        sabit = sorted([m for m in tum if re.fullmatch(r"gpt-image-\d+(\.\d+)?", m) and m != "gpt-image-1"], key=surum_anahtari)
        diger = sorted([m for m in tum if m not in sabit], key=surum_anahtari, reverse=True)
        print(f"Hesabın görsel modelleri: {', '.join(tum) or 'yok'}. Deneme sırası: sabit adlı düşük sürümden (ucuz), sonra diğerleri")
        aday += sabit + diger
    except Exception as e:
        print(f"Model listesi alınamadı ({type(e).__name__}); varsayılan denenecek.")
    aday.append("gpt-image-1")
    _gorsel_modelleri = list(dict.fromkeys(aday))
    return _gorsel_modelleri


def gorsel_uret(prompt, kalite):
    """Görseli ilk çalışan modelle üretir (b64). Model yok/erişim yok hatalarında sıradaki modeli dener ve çalışanı hatırlar."""
    global _gorsel_modelleri
    son_hata = None
    for model in list(gorsel_modelleri()):
        try:
            v = openai("images/generations", {"model": model, "prompt": prompt, "size": "1024x1536", "quality": kalite, "n": 1}, 300)
        except urllib.error.HTTPError as e:
            son_hata = e
            if e.code in (400, 403, 404):
                print(f"  görsel modeli '{model}' kullanılamadı ({http_hata_ozeti(e)})")
                continue
            raise
        b64 = (v.get("data") or [{}])[0].get("b64_json")
        if not b64:
            raise ValueError("görsel yanıtında veri yok")
        if _gorsel_modelleri[0] != model:
            _gorsel_modelleri = [model] + [m for m in _gorsel_modelleri if m != model]
        return b64
    raise son_hata or ValueError("kullanılabilir görsel modeli yok")


DENETIM_SISTEM = "Sen sosyal medya görsellerini denetleyen titiz bir editörsün. Yalnızca geçerli JSON döndür."
DENETIM_ISTEMI = """Bu görsel, şu 3D baskı nesnesinin TEMSİLİ görseli olarak Instagram hikayesinde yayınlanacak:
Nesne: {ad}. Açıklama: {aciklama}

Görseli titizlikle incele ve şu JSON'u döndür:
{{"yazi_var": okunabilir ya da anlamsız herhangi bir yazı/harf/rakam var mı (true/false),
"logo_var": tanınabilir logo, marka ya da filigran var mı,
"taninmis_karakter": film/oyun/çizgi film/anime gibi telifli, tanınmış bir karakter ya da marka ürünü var mı,
"bozuk_anatomi": bozuk el, yüz ya da gerçekçi olmayan insan/kopuk uzuv var mı (insan yoksa false),
"nesne_makul": gösterilen nesne fiziksel olarak mümkün, makul ve ev tipi 3D yazıcıyla basılmış gibi mi,
"tarife_uygun": görsel açıklamadaki nesnenin genel şeklini ve belirgin özelliklerini sadakatle gösteriyor mu (başka bir nesne, ekstra ya da eksik ana parça varsa false),
"puan": 1-10 genel kalite ve güvenilirlik,
"sorunlar": ["kısa sorun cümleleri"]}}"""


REFERANS_KONTROL_ISTEMI = """Bu, bir 3D baskı tasarım sayfasının ana fotoğrafı. Hikaye görseli üretmek için referans olarak kullanılacak. Yalnızca JSON döndür:
{"kullanilabilir": tek bir nesneyi net gösteren, gerçek baskı fotoğrafına benzeyen, baskın yazı/logo/etiket/başlık/filigran içermeyen fotoğraf mı (true/false),
"neden": "kısa Türkçe neden"}"""


def referans_kullanilabilir(referans_jpeg):
    """Pahalı görsel üretiminden önce referans fotoğrafı ucuzca denetle (yazı, kolaj, çizim vb. varsa üretme)."""
    try:
        c = sohbet_json(DENETIM_SISTEM, REFERANS_KONTROL_ISTEMI, None, base64.b64encode(referans_jpeg).decode())
    except Exception as e:
        return True, f"referans denetimi çalışmadı ({type(e).__name__}); devam"
    return c.get("kullanilabilir") is True, str(c.get("neden") or "")[:140]


REFERANS_DENETIM_EKI = """

İKİNCİ görsel, tasarımın gerçek REFERANS fotoğrafıdır. JSON'a ek olarak şu alanı da ekle:
"referansa_sadik": birinci (üretilen) görseldeki nesne, referanstaki nesneyle aynı genel şekil, oran, parça sayısı ve belirgin ayrıntılara sahip mi (aynı nesne mi; farklı bir nesne, ekstra ya da eksik ana parça varsa false)."""


def denetle(b64, t, referans_jpeg=None):
    istem = DENETIM_ISTEMI.format(ad=t["ad"], aciklama=t.get("aciklama", "")) + (REFERANS_DENETIM_EKI if referans_jpeg else "")
    c = sohbet_json(DENETIM_SISTEM, istem, b64, base64.b64encode(referans_jpeg).decode() if referans_jpeg else None)
    try:
        puan = float(c.get("puan", 0))
    except (TypeError, ValueError):
        puan = 0.0
    gecti = (not c.get("yazi_var") and not c.get("logo_var") and not c.get("taninmis_karakter") and not c.get("bozuk_anatomi")
             and c.get("nesne_makul") is True and c.get("tarife_uygun") is True and puan >= 7
             and (not referans_jpeg or c.get("referansa_sadik") is True))
    return gecti, {"puan": puan, "sorunlar": [str(s)[:100] for s in (c.get("sorunlar") or [])][:5]}


IZINLI_HARFLER = set("çğıöşüÇĞİÖŞÜâÂîÎûÛ·")


def yazi_temizle(metin):
    """Yazı tipinde olmayan karakterleri (tam genişlik tırnak, emoji vb.) çıkarır; böylece görselde kutucuk çıkmaz."""
    t = unicodedata.normalize("NFKC", metin or "")
    t = t.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return "".join(c for c in t if 32 <= ord(c) < 127 or c in IZINLI_HARFLER).strip()


def kisalt(metin, en_cok):
    return metin if len(metin) <= en_cok else metin[:max(1, en_cok - 2)].rstrip() + ".."


def etiket_satirlari(t):
    """Hikaye üstündeki küçük yazı: 2 kısa satır (yapay zekâ etiketi + tek satır atıf)."""
    ad = kisalt(yazi_temizle(t["ad"]), 28)
    tasarimci = kisalt(yazi_temizle(t.get("tasarimci") or "?"), 18)
    atif = f"{ad} · {tasarimci} · {t['_lisans']} · {yazi_temizle(t['_site']).replace('.com', '')}"
    return [YAPAY_ZEKA_ETIKETI, atif]


def etiketli_jpeg(png_b64, t, cikti):
    """Görseli 1080x1920'ye yerleştir, küçük ve sade yapay zekâ etiketi + atıf işle (hikaye arayüzünün kapatmayacağı alanda), JPEG yaz."""
    font = SU.font_bul()
    satirlar = [x for x in etiket_satirlari(t) if x]
    boyutlar = [24, 20]
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        (g / "a.png").write_bytes(base64.b64decode(png_b64))
        filtre = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:6,eq=brightness=-0.18[bg];"
                  "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-70[v0];[v0]null")
        taban = 1590   # alttaki ~250 px Instagram yanıt çubuğuna ayrılır; yazı bunun üstünde, görselin içinde kalır
        for i, satir in enumerate(satirlar):
            dosya = g / f"y{i}.txt"
            dosya.write_text(satir, encoding="utf-8")   # sonunda satır sonu yok
            filtre += (f",drawtext=fontfile={font}:textfile={dosya}:expansion=none:fontsize={boyutlar[min(i, 1)]}:fontcolor=white@0.95:"
                       f"box=1:boxcolor=black@0.45:boxborderw=7:x=(w-text_w)/2:y={taban + i * 38}")
        filtre += ",format=yuvj420p[v]"
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

    kullanilan = json_oku(KULLANILAN, [])
    kul_anahtar = {adres_anahtari(k.get("url")) for k in kullanilan}
    onbellek = json_oku(ADAYLAR, {})
    kalan = []
    try:
        yas = (an - datetime.datetime.fromisoformat(onbellek["tarih"])).total_seconds() / 86400
        if yas < ADAY_OMRU_GUN:
            kalan = [t for t in onbellek.get("tasarimlar", []) if adres_anahtari(t.get("_adres")) not in kul_anahtar]
    except Exception:
        pass
    hedef_aday = max(1, min(int(ayar["gunluk_uretim"]), 12)) + 2   # reddedilen/atlanan adaylar için pay
    printables_hedef = max(1, hedef_aday // 2) if TV.hazir() else hedef_aday   # Thingiverse varsa adayların yarısını o tamamlar
    if len(kalan) >= printables_hedef:
        uygunlar = kalan
        print(f"Aday listesi önbellekten kullanıldı ({len(uygunlar)} kullanılmamış tasarım); yeni arama yapılmadı (maliyet tasarrufu).")
    else:
        print("Tasarımlar aranıyor (Printables, MakerWorld)…")
        tasarimlar, dogrulanan = tasarim_ara()
        print(f"Aramanın döndürdüğü kaynak sayısı: {len(dogrulanan)}")
        uygunlar, elenen = uygun_tasarimlar(tasarimlar, dogrulanan, {temiz_adres(k.get("url")) for k in kullanilan})
        print(f"Bulunan {len(tasarimlar)}, uygun {len(uygunlar)} (modele göre CC0 / CC BY; bunlardan {sum(1 for t in uygunlar if t.get('_teyit'))} tanesinin sayfası aramada da göründü). Elenenler:")
        for ad, neden in elenen:
            print(f"  - {ad}: {neden}")
        mevcut = {adres_anahtari(t.get("_adres")) for t in uygunlar}
        uygunlar = uygunlar + [t for t in kalan if adres_anahtari(t.get("_adres")) not in mevcut]   # önceki kullanılmamış adaylar da kalsın
        yaz(ADAYLAR, {"tarih": an.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "tasarimlar": [{k: v for k, v in t.items() if k not in ("_referansli", "_gorsel_adresi")} for t in uygunlar]})
    if ayar.get("referans", "zorunlu") == "zorunlu":
        # MakerWorld siteleri robotları engelliyor ve veri servisi yok: referans zorunluyken yalnızca Printables adayları kullanılır
        onceki = len(uygunlar)
        uygunlar = [t for t in uygunlar if site_uygun(t.get("_adres")) == "printables.com"]
        if onceki != len(uygunlar):
            print(f"  MakerWorld adayları ({onceki - len(uygunlar)}) referans fotoğraf alınamadığı için bu çalışmada atlandı.")
    tv_adaylar = thingiverse_adaylari(kul_anahtar | {adres_anahtari(t.get("_adres")) for t in uygunlar}, max(1, hedef_aday - len(uygunlar)))
    if tv_adaylar:   # iki kaynağı sırayla serpiştir (çeşitlilik)
        karisik = []
        for i in range(max(len(uygunlar), len(tv_adaylar))):
            if i < len(uygunlar):
                karisik.append(uygunlar[i])
            if i < len(tv_adaylar):
                karisik.append(tv_adaylar[i])
        uygunlar = karisik
    if not uygunlar:
        print("Uygun tasarım yok; hiçbir şey üretilmedi.")
        return 0

    hedef = max(1, min(int(ayar["gunluk_uretim"]), 12))
    uretilen, atlanan = [], []
    gorsel_hatasi = False
    kategoriler = set()
    sira = 0
    for t in uygunlar:
        if len(uretilen) >= hedef:
            break
        if t.get("kategori") and t.get("kategori") in kategoriler and len(uygunlar) - len(uretilen) > hedef - len(uretilen):
            continue   # çeşitlilik: aynı kategoriden art arda seçme (yeterince aday varken)
        # Printables adayları: lisans ve fotoğraf sitenin kendi veri servisinden (kanıtlı)
        if site_uygun(t["_adres"]) == "printables.com":
            durum, neden = printables_dogrula(t)
            print(f"  {t['ad']}: Printables servisi: {neden}")
            if durum is False:
                atlanan.append((t["ad"], neden))
                kullanilan.append({"url": t["_adres"], "ad": t["ad"], "tarih": H.simdi().strftime("%Y-%m-%d"), "durum": "lisans_uygun_degil"})
                yaz(KULLANILAN, kullanilan[-200:])
                continue
            if durum is None and not t.get("_lisans"):
                atlanan.append((t["ad"], "lisans doğrulanamadı (modelin beyanı da belirsiz)"))
                continue
        # referans fotoğraf (yalnızca bellekte)
        referans = None
        if ayar.get("referans", "zorunlu") != "yok":
            try:
                referans = referans_fotografi(t["_adres"], t.get("_gorsel_adresi"))
                print(f"  {t['ad']}: referans fotoğraf alındı ({len(referans) // 1024} KB)")
                uygun, neden = referans_kullanilabilir(referans)
                if not uygun:
                    print(f"  {t['ad']}: referans fotoğraf uygun değil ({neden}); görsel üretilmedi")
                    atlanan.append((t["ad"], f"referans uygun değil: {neden}"))
                    kullanilan.append({"url": t["_adres"], "ad": t["ad"], "tarih": H.simdi().strftime("%Y-%m-%d"), "durum": "referans_uygun_degil"})
                    yaz(KULLANILAN, kullanilan[-200:])
                    continue
            except ReferansYok as e:
                print(f"  {t['ad']}: referans fotoğraf alınamadı ({e})")
                if ayar.get("referans", "zorunlu") == "zorunlu":
                    atlanan.append((t["ad"], f"referans alınamadı: {e}"))
                    continue   # kullanılmış sayılmaz; sonraki çalışmada yeniden denenir
        t["_referansli"] = bool(referans)
        kabul = None
        for deneme in range(2):
            if gun_say >= ayar["gunluk_gorsel_siniri"] or ay_say >= ayar["aylik_gorsel_siniri"]:
                print("Harcama sınırına ulaşıldı; durduruluyor.")
                break
            try:
                if referans:
                    b64 = gorsel_duzenle(REFERANSLI_ISTEM.format(sahne=SAHNELER[(sira + deneme) % len(SAHNELER)]), referans, ayar["kalite"])
                else:
                    prompt = sahne_promptu(t, karakterli=(sira % 3 == 2))
                    b64 = gorsel_uret(prompt, ayar["kalite"])
            except urllib.error.HTTPError as e:
                print(f"  görsel üretilemedi ({http_hata_ozeti(e)})")
                atlanan.append((t["ad"], http_hata_ozeti(e)))
                gorsel_hatasi = True
                break
            except Exception as e:
                print(f"  görsel üretilemedi ({type(e).__name__}: {str(e)[:100]})")
                break
            harcama_ekle(harcama, gun, ay)
            gun_say += 1
            ay_say += 1
            try:
                gecti, kontrol = denetle(b64, t, referans)
            except Exception as e:
                print(f"  denetim çalışmadı ({type(e).__name__}); şüphede yayınlanmaz, atlanıyor")
                gecti, kontrol = False, {"puan": 0, "sorunlar": ["denetim çalışmadı"]}
            print(f"  {t['ad']}: deneme {deneme + 1}, denetim {'GEÇTİ' if gecti else 'GEÇMEDİ'} (puan {kontrol['puan']}) {kontrol['sorunlar']}")
            if gecti:
                kabul = (b64, kontrol, deneme + 1)
                break
        yaz(HARCAMA, harcama)
        sira += 1
        if gorsel_hatasi:
            print("Görsel servisi hata verdi; kalan tasarımlar için denenmeyecek (anahtar/model erişimini kontrol et).")
            break
        if not kabul:
            atlanan.append((t["ad"], "denetimden geçemedi ya da üretilemedi"))
            kullanilan.append({"url": t["_adres"], "ad": t["ad"], "tarih": H.simdi().strftime("%Y-%m-%d"), "durum": "atlandi"})
            yaz(KULLANILAN, kullanilan[-200:])
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
               "atif": {"ad": t["ad"], "tasarimci": t.get("tasarimci"), "lisans": t["_lisans"], "url": t["_adres"], "site": t["_site"], "lisans_teyit": bool(t.get("_teyit")), "referansli": bool(t.get("_referansli"))},
               "trend": (t.get("trend_konusu") or "")[:80],
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
