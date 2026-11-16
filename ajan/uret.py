#!/usr/bin/env python3
"""Günlük içerik taslağı üretir: Doktor Filament (yapay zekâ karakteri) için carousel ya da kısa video planı.

Instagram, YouTube Shorts ve Facebook için ayrı metinler yazar. OpenAI API kullanır, ek bağımlılık yok.

Kullanım:
    OPENAI_API_KEY=... python3 ajan/uret.py            # taslak üretir
    python3 ajan/uret.py --dry-run                     # API çağırmadan prompt'u gösterir
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
TASLAK_DIZINI = KOK / "taslaklar"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_ADRES = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
YEDEK_MODEL = "gpt-4o-mini"

YZ_SATIRI = "🤖 Doktor Filament yapay zekâ ile üretilmiş bir karakterdir."
VARSAYILAN_ETIKETLER = ["#3dprinting", "#3dyazici", "#3dprint", "#doktorfilament", "#shorts"]
YASAK_SOZCUKLER = ["mükemmel", "harika", "muhteşem", "eğlenceli", "biliyor musun", "inanılmaz"]
VIDEO_SONEKI = (
    "Vertical 9:16 short-form video, smooth natural motion, no on-screen text, "
    "no readable text or letters on clothing or objects, no logos, no watermark."
)
GORSEL_SONEKI = (
    "Photorealistic, vertical 4:5 image, no text, no letters, no readable text on clothing "
    "or objects, no logos, no watermark."
)


def oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def gecmis_konular(adet=20):
    """Tekrarı önlemek için son taslakların konu başlığını ve formatını toplar."""
    konular = []
    for dosya in sorted(TASLAK_DIZINI.glob("*.md"))[-adet:]:
        baslik, bicim = "", ""
        for satir in dosya.read_text(encoding="utf-8").splitlines():
            if not baslik and satir.startswith("# "):
                baslik = satir[2:].strip()
            m = re.match(r"- \*\*Format:\*\* (.+)", satir)
            if m:
                bicim = m.group(1).strip()
        if baslik:
            konular.append(f"{baslik} ({bicim})" if bicim else baslik)
    # Taslağı olmayan ama panelden yayınlanan (bağımsız) içerikler de tekrarlanmasın
    for kayit in sorted((KOK / "zincir").glob("y*.json"))[-adet:]:
        try:
            k = json.loads(kayit.read_text(encoding="utf-8"))
            if k.get("konu"):
                konular.append(f"{k['konu']} (yayınlandı)")
        except Exception:
            pass
    return konular


def hesap_durumu():
    yol = KOK / "ajan" / "hesap_durumu.md"
    return yol.read_text(encoding="utf-8") if yol.exists() else "(Henüz otomatik hesap verisi yok.)"


def trendler():
    """Trend ajanının son araştırması (en fazla 14 gün eski). Yoksa None."""
    yol = KOK / "ajan" / "trendler.json"
    if not yol.exists():
        return None
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
        zaman = datetime.datetime.strptime(v["tarih"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None
    if (datetime.datetime.now(datetime.timezone.utc) - zaman).days > 14:
        return None
    return v


def trend_blogu():
    v = trendler()
    if not v:
        return "# GÜNCEL TRENDLER\n(Trend araştırması yok ya da eski. Kendi araştırmana ve özgün fikre güven.)\n\n"
    satirlar = [f"# GÜNCEL TRENDLER (trend ajanı, {v['tarih']}; kaynaklı olanlar güvenilir, kaynaksızlar yalnızca esin)"]
    for o in v.get("oneriler", [])[:8]:
        etiket = "KAYNAKLI" if o.get("dogrulandi") else "kaynaksız"
        satirlar.append(f"- [{etiket}] {o.get('konu')} | neden: {o.get('neden_trend')} | açı: {o.get('kanca_acisi')} | "
                        f"basılabilir: {o.get('basilabilir')} | risk: {o.get('risk')}")
    if v.get("asiri_kullanilan"):
        satirlar.append("- AŞIRI KULLANILAN (kaçın): " + "; ".join(v["asiri_kullanilan"]))
    return "\n".join(satirlar) + "\n\n"


def govde_kokleri(metin):
    """Türkçe ek farklarını yutmak için kelimelerin ilk 5 harfi."""
    return {k[:5] for k in _norm(metin) if len(k) >= 3}


def benzerlik(a, b):
    x, y = govde_kokleri(a), govde_kokleri(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def persona_tarifi():
    """Karakterin sabit görünüm tarifini kanal.md'den alır (tek kaynak)."""
    m = re.search(r'"(Doctor Filament: [^"]+)"', oku("ajan/kanal.md"))
    return m.group(1) if m else "Doctor Filament: a fictional, eccentric but friendly inventor character, photorealistic."


def imza_cumleler():
    """Açılış ve kapanış imza cümlelerini kanal.md'den alır (tek kaynak)."""
    metin = oku("ajan/kanal.md")
    a = re.search(r'\*\*Açılış[^*]*\*\*\s*"([^"]+)"', metin)
    k = re.search(r'\*\*Kapanış[^*]*\*\*\s*"([^"]+)"', metin)
    return (a.group(1) if a else ""), (k.group(1) if k else "")


def _norm(metin):
    return re.sub(r"[^\w ]", "", metin.lower()).split()


def karakter_var_mi(prompt):
    """Karakter ancak promptta adı geçiyorsa sahnededir."""
    return bool(re.search(r"doctor filament", (prompt or "").lower()))


def imza_uyarilari(t):
    """Yalnızca video planı için: ilk sahnede açılış, son sahnede kapanış aynen geçmeli."""
    acilis, kapanis = imza_cumleler()
    sahneler = t.get("sahneler") or []
    uyari = []
    if acilis and sahneler and " ".join(_norm(acilis)) not in " ".join(_norm(sahneler[0].get("seslendirme", ""))):
        uyari.append("İlk sahne seslendirmesi imza açılış cümlesini aynen içermiyor.")
    if kapanis and sahneler and " ".join(_norm(kapanis)) not in " ".join(_norm(sahneler[-1].get("seslendirme", ""))):
        uyari.append("Son sahne seslendirmesi imza kapanış cümlesini aynen içermiyor.")
    return uyari


LATIN_DISI = re.compile(r"[^\x00-ɏ -⁯←-⇿\U0001F000-\U0001FFFF☀-➿]")


KARMASIK_MEKANIZMA = re.compile(r"hinge|fold|articulat|flex|spring|gear|mechanism|chain", re.I)


def carousel_uyarilari(t, slaytlar):
    """Seri ve slayt düzeni, karakter dağılımı, metin uzunluğu ve basılabilirlik denetimi."""
    uyari = []
    seri = (t.get("seri") or "").lower()
    if "5 şey" in seri and len(slaytlar) != 7:
        uyari.append(f"'Basılabilir 5 Şey' serisi tam 7 slayt olmalı (kanca + 5 nesne + çağrı); {len(slaytlar)} slayt var.")
    karakterli = [i for i, sl in enumerate(slaytlar, 1) if sl.get("karakter_gorunur")]
    if len(karakterli) > 3 or (karakterli and len(slaytlar) > 2 and len(karakterli) == len(slaytlar)):
        uyari.append(f"Karakter {len(karakterli)} slaytta görünüyor; yalnızca ilk ve son slaytta olmalı, ortada nesne yakın planı olmalı.")
    for i, sl in enumerate(slaytlar, 1):
        kelime = len((sl.get("metin") or "").split())
        if kelime > 12:
            uyari.append(f"Slayt {i}: metin {kelime} kelime, en fazla 12 olmalı.")
    if slaytlar and slaytlar[0].get("metin", "").strip().endswith("?") and len(slaytlar[0]["metin"].split()) < 6:
        uyari.append("1. slayt metni kısa bir soru: tek başına anlaşılıyor mu, net bir vaat içeriyor mu, kontrol et.")
    if any(KARMASIK_MEKANIZMA.search(sl.get("gorsel_promptu") or "") for sl in slaytlar):
        uyari.append("Menteşe, katlama, zincir gibi karmaşık bir mekanizma var: yapay zekâ görseli yanlış çizebilir, görselin gerçekten basılabilir göründüğünü kontrol et.")
    return uyari


def yasak_uyarilari(t):
    """Dolgu sözcüğü, yanlış süre iddiası, imza uyumu, yabancı karakter ve karakter tutarlılığı denetimi."""
    t_ = {k: v for k, v in t.items() if k not in ("seri", "konu", "format")}
    metin = json.dumps(t_, ensure_ascii=False).lower()
    uyari = [f"Dolgu sözcüğü bulundu: \"{k}\"" for k in YASAK_SOZCUKLER if k in metin]
    if re.search(r"\d+\s*(saniye|dakika|dk|sn)[a-zçğıöşü]*\s*(de|da|içinde)?\s*bas", metin):
        uyari.append("Gerçek baskı süresi iddiası olabilir ('X saniyede basılıyor'). Doğru mu, kontrol et.")
    if re.search(r"tedavi|ilaç|hastalığı iyileş|sağlık tavsiye", metin):
        uyari.append("Sağlık ya da tedavi çağrışımı var; 'doktor' yalnızca espri olmalı, sağlık iddiası olmamalı.")

    if t.get("format") == "reels":
        uyari += imza_uyarilari(t)
        ogeler = [(f"Sahne {i}", sh.get("sahne_promptu", ""), sh.get("karakter_gorunur"))
                  for i, sh in enumerate(t.get("sahneler") or [], 1)]
    else:
        slaytlar = t.get("slaytlar") or []
        ogeler = [(f"Slayt {i}", sl.get("gorsel_promptu", ""), sl.get("karakter_gorunur"))
                  for i, sl in enumerate(slaytlar, 1)]
        uyari += carousel_uyarilari(t, slaytlar)
    for ad, prompt, gorunur in ogeler:
        if gorunur and not karakter_var_mi(prompt):
            uyari.append(f"{ad}: karakter görünür işaretli ama promptta 'Doctor Filament' yok; karakter tarifi eklenmedi.")
        if LATIN_DISI.search(prompt or ""):
            uyari.append(f"{ad}: promptta İngilizce dışı karakter var (Kiril vb.); araca yapıştırmadan önce düzelt.")
    return uyari


TERCIH = {"format": "otomatik"}
SERI_KURALI = ('SERİ KURALI: "Basılabilir 5 Şey" yalnızca beş FARKLI nesneyi listeleyen içerik içindir. Tek bir nesneyi ya da tek bir hileyi '
               'anlatıyorsan seri "Katman Katman" ya da "Doktor Notu" olmalı.')


def format_talimati():
    f = TERCIH["format"]
    if f == "reels":
        return ('Format MUTLAKA "reels" olmalı ("slaytlar" boş kalsın). Sahibi videoyu yapay zekâ video araçlarıyla kendisi üretecek; klip kredisi sorun değil. '
                'Her sahne EN FAZLA 8 saniye olsun (video araçları klipleri 8 sn üretir) ve sahnedeki konuşma süreye sığsın (saniyede en fazla 2,5 kelime).')
    if f == "carousel":
        return 'Format MUTLAKA "carousel" olmalı ("sahneler" boş kalsın).'
    return 'Format "carousel" ya da "reels" olabilir; son içeriklere bakarak formatı değiştir (aynısını art arda üretme).'


def direktif_blogu(direktif):
    """Kanal sahibinin o güne özel isteği. Kanal kurallarını (yapay zekâ açıklaması, güvenlik, lisans) aşamaz."""
    direktif = " ".join((direktif or "").split())[:500]
    if not direktif:
        return ""
    return (
        "# SAHİBİN BUGÜNKÜ DİREKTİFİ\n"
        f"\"{direktif}\"\n"
        "Bu istek konuyu ve tarzı belirler. Yukarıdaki kanal profilindeki kuralları (yapay zekâ karakteri açıklaması, "
        "sağlık iddiası olmaması, basılabilir nesneler, ücretsiz lisans, marka logosu olmaması) asla aşma. "
        "Başkasının içeriğini kopyalama; yalnızca tarzdan ve konu başlığından esinlen.\n\n"
    )


def fikir_blogu(fikir):
    if not fikir:
        return ""
    return ("# SEÇİLEN FİKİR (ajan bu fikri 5 adaydan seçti; bunu geliştir, başka konuya kayma)\n"
            + json.dumps(fikir, ensure_ascii=False) + "\n\n")


def prompt_olustur(bugun, direktif="", fikir=None):
    sistem = (
        "Sen sosyal medya içerik ajanısın. Kanal profiline ve stratejiye kesinlikle uy. "
        "Yalnızca geçerli JSON döndür."
    )
    kullanici = f"""# KANAL PROFİLİ VE KURALLAR
{oku('ajan/kanal.md')}

# STRATEJİ NOTLARI
{oku('ajan/strateji.md')}

# FİKİR HAVUZU (başlangıç tohumları)
{oku('ajan/fikirler.md')}

# GÜNCEL HESAP DURUMU (gerçek veri, sayı uydurma)
{hesap_durumu()}

# SON İÇERİKLER (konuyu ve formatı tekrar etme)
{json.dumps(gecmis_konular(), ensure_ascii=False)}

{direktif_blogu(direktif)}{trend_blogu()}{fikir_blogu(fikir)}# GÖREV
Bugünün tarihi: {bugun}. Bugün için TEK bir içerik planı üret. {format_talimati()}
Seriyi de son içeriklere bakarak değiştir (aynısını art arda üretme). {SERI_KURALI}

JSON şeması (kullanılmayan alanı boş liste bırak):
{{
  "konu": "kısa başlık",
  "format": "carousel | reels",
  "seri": "Basılabilir 5 Şey | Doktor Notu | Katman Katman",
  "kanca": "ilk slaytta/ilk 2 saniyede söylenen ya da yazılan cümle",
  "slaytlar": [
    {{"baslik": "kısa başlık", "metin": "en fazla 12 kelime", "karakter_gorunur": true,
      "gorsel_promptu": "İngilizce. SADECE sahneyi anlat (özne, eylem, ortam, ışık). Karakter varsa 'Doctor Filament' adını kullan; görünüşünü ANLATMA, kod ekler. Yazı isteme."}}
  ],
  "sure_sn": 25,
  "sahneler": [
    {{"sure_sn": 4, "gorsel": "Türkçe sahne tarifi", "ekran_yazisi": "ekrandaki kısa yazı",
      "seslendirme": "Doktor Filament'in söyleyeceği cümle", "karakter_gorunur": true,
      "sahne_promptu": "İngilizce. SADECE bu sahnede ne olduğunu anlat; karakter varsa 'Doctor Filament' adını kullan, görünüşünü ANLATMA, kod ekler."}}
  ],
  "instagram_caption": "Türkçe, 3-5 kısa satır, sonunda tek çağrı",
  "youtube_baslik": "en fazla 60 karakter",
  "youtube_aciklama": "2-3 cümle, Türkçe",
  "facebook_caption": "Türkçe, 2-4 kısa satır",
  "hashtagler": ["#..."],
  "model_notu": "gösterilen nesne için nasıl bir serbest lisanslı model ya da basit kendi tasarım aranmalı"
}}

KALİTE KURALLARI:
- format "carousel" ise "sahneler" boş kalsın. Slayt metni en fazla 12 kelime.
  * seri "Basılabilir 5 Şey" ise TAM 7 slayt: 1. slayt kanca, 2-6. slaytlar BEŞ FARKLI basılabilir nesne (her slayt bir nesne, tek nesneyi yedi slaytta anlatma), 7. slayt yorum çağrısı (kapanış cümlesine yakın).
  * seri "Doktor Notu" ise 6-7 slayt: sorun/merak, tek ipucunun adımları, çağrı. "Katman Katman" ise 6-8 slayt: bir nesnenin oluşumu adım adım.
  * Karakter yalnızca 1. ve son slaytta görünsün (karakter_gorunur true); ortadaki slaytlar nesnenin yakın planı olsun (karakter_gorunur false, promptta "Doctor Filament" adı geçmesin).
  * 1. slayt metni TEK BAŞINA anlaşılır, net bir vaat ya da merak olsun. Belirsiz kısa soru yazma.
- format "reels" ise 4-7 sahne üret, "slaytlar" boş kalsın. Sahne sürelerinin TOPLAMI sure_sn'ye eşit olsun.
- Reels'te İLK sahnenin seslendirmesi İmza cümleler bölümündeki AÇILIŞ cümlesi, SON sahnenin seslendirmesi KAPANIŞ cümlesi olsun (kelimesi kelimesine, değiştirme, kısaltma, çevirme, araya ekleme yapma). Aradaki sahneler konuyu anlatsın.
- gorsel_promptu ve sahne_promptu YALNIZCA İngilizce (Latin harfleri) olsun, somut eylem ve görüntü içersin, boş ya da genel olmasın. Görselde yazı isteme.
- Karakter görünüyorsa promptta "Doctor Filament" adı geçsin ve karakter_gorunur true olsun; karakter yoksa bu adı hiç kullanma ve false yap. Gerçek bir yazıcının nozzle'ı için "printer nozzle" de.
- Doktor esprisi yalnızca espridir: sağlık, tedavi, ilaç iddiası YAZMA.
- Kanca doğru ve merak uyandıran olsun: doğrulanabilir bir rakam (ör. katman sayısı) uydurma; çelişki ya da soru kullan. Yasak sözcükler: mükemmel, harika, muhteşem, eğlenceli, inanılmaz, "biliyor musun".
- Gösterilen nesne gerçekten 3D yazıcıyla basılabilir olsun. Belirli model adı, tasarımcı, süre, gram, fiyat UYDURMA. "10 saniyede basılıyor" gibi gerçek baskı süresi iddiası YASAK.
- Caption ve açıklamalara hashtag YAZMA ve yapay zekâ açıklaması YAZMA (kod ekler). Slayt ve sahne metinlerine numara yazma. Her zaman 5-8 hashtag döndür.
- Türkçe doğal konuşma dilinde olsun; çeviri gibi ya da anlamsız kalıp cümleler yazma (ör. "en sessiz yardımcı", "baskı devreye girer"). Yüksek sesle okuyunca doğal durmayan cümleyi sadeleştir.
- Üç platform metni birbirinin kopyası olmasın; YouTube başlığı arama odaklı, Instagram ve Facebook daha samimi olsun."""
    return sistem, kullanici


def _istek(model, sistem, kullanici):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        sys.exit("OPENAI_API_KEY ortam değişkeni tanımlı değil.")
    govde = json.dumps({
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user", "content": kullanici},
        ],
    }).encode()
    istek = urllib.request.Request(
        f"{OPENAI_ADRES}/chat/completions",
        data=govde,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"},
    )
    with urllib.request.urlopen(istek, timeout=180) as yanit:
        veri = json.load(yanit)
    return json.loads(veri["choices"][0]["message"]["content"])


def openai_cagir(sistem, kullanici):
    """Seçilen modeli dener; model bulunamaz ya da parametre reddedilirse yedek modele düşer."""
    try:
        sonuc = _istek(MODEL, sistem, kullanici)
        print(f"Model: {MODEL}")
        return sonuc
    except urllib.error.HTTPError as e:
        if MODEL == YEDEK_MODEL or e.code not in (400, 404):
            raise
        try:
            mesaj = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:200]
        except Exception:
            mesaj = ""
        print(f"UYARI: '{MODEL}' modeli kullanılamadı (HTTP {e.code}: {mesaj}). Yedek model: {YEDEK_MODEL}")
        sonuc = _istek(YEDEK_MODEL, sistem, kullanici)
        print(f"Model: {YEDEK_MODEL} (yedek)")
        return sonuc


def simdi_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def zincir_yaz(taslak, cikti, notlar, direktif):
    """Her içeriğe bir kimlik verir ve zincir kaydını yazar (fikir -> senaryo -> video -> yayın -> ölçüm)."""
    zaman = simdi_utc()
    kimlik = "c" + zaman.strftime("%Y%m%d-%H%M%S")
    dizin = KOK / "zincir"
    dizin.mkdir(exist_ok=True)
    f = notlar.get("fikir") or {}
    e = notlar.get("elestiri") or {}
    tr = trendler()
    yenilendi = False
    if tr:
        try:
            yenilendi = (zaman - datetime.datetime.strptime(tr["tarih"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() < 1800
        except Exception:
            pass
    hashtagler = " ".join(dict.fromkeys(taslak.get("hashtagler") or VARSAYILAN_ETIKETLER))
    kayit = {
        "kimlik": kimlik,
        "olusturma": zaman.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "durum": "senaryo",
        "kaynak": "direktif" if direktif.strip() else "zincir",
        "direktif": " ".join(direktif.split())[:500],
        "konu": taslak.get("konu", ""),
        "format": taslak.get("format", ""),
        "seri": taslak.get("seri", ""),
        "kanca": taslak.get("kanca", ""),
        "taslak": str(cikti.relative_to(KOK)),
        "taslak_json": f"zincir/{kimlik}_taslak.json",
        "fikir": {"konu": f.get("konu"), "neden": f.get("neden_ilgi_ceker"), "trend_baglantisi": f.get("trend_baglantisi"),
                  "puan": f.get("_puan"), "benzerlik": f.get("_benzerlik")} if f else None,
        "elestiri": {"puan": e.get("puan"), "ilk_puan": e.get("ilk_puan"), "turlar": e.get("turlar"), "uygulandi": e.get("uygulandi")} if e else None,
        "trend": {"tarih": tr["tarih"] if tr else None, "yenilendi": yenilendi},
        "metinler": {"youtube_baslik": (taslak.get("youtube_baslik") or "")[:100],
                     "aciklama": "\n".join(x for x in [caption_temizle(taslak.get("instagram_caption", "")), "", hashtagler] if x is not None).strip()},
        "video": None,
        "yayinlar": [],
        "olcumler": [],
        "ogrenildi": False,
    }
    temiz = {k: v for k, v in taslak.items() if not k.startswith("_")}
    (dizin / f"{kimlik}_taslak.json").write_text(json.dumps(temiz, ensure_ascii=False, indent=2), encoding="utf-8")
    (dizin / f"{kimlik}.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    return kimlik


def baglam_metni(bugun, direktif):
    return f"""# KANAL PROFİLİ VE KURALLAR
{oku('ajan/kanal.md')}

# STRATEJİ NOTLARI
{oku('ajan/strateji.md')}

# FİKİR HAVUZU (başlangıç tohumları)
{oku('ajan/fikirler.md')}

# GÜNCEL HESAP DURUMU (gerçek veri, sayı uydurma)
{hesap_durumu()}

# SON İÇERİKLER (bunları ve benzerlerini TEKRAR ETME)
{json.dumps(gecmis_konular(), ensure_ascii=False)}

{direktif_blogu(direktif)}{trend_blogu()}Bugünün tarihi: {bugun}."""


def fikir_sec(bugun, direktif):
    """5 farklı aday fikir üretir; geçmişe benzeyenleri eler, puanı en yüksek olanı seçer."""
    sistem = ("Sen yaratıcı ve araştırmacı bir içerik stratejistisin. Kanalın geçmişine ve trendlere bakıp "
              "özgün, tekrara düşmeyen fikirler bulursun. Yalnızca geçerli JSON döndür.")
    kullanici = baglam_metni(bugun, direktif) + """

GÖREV: Bugün için 5 FARKLI aday içerik fikri üret. Aynı nesneyi, aynı kategoriyi ya da aynı kancayı tekrar etme.
- Trend listesi varsa en az 2 aday oradan esinlensin (özgün açıyla, kimseyi kopyalamadan); en az 1 aday trend dışı, tamamen özgün olsun.
- Nesne gerçekten ev tipi 3D yazıcıyla basılabilir olsun. Marka, lisanslı karakter, sağlık iddiası yok.
- Sahibinin direktifi varsa tüm adaylar ona uysun.
- """ + format_talimati() + """
- """ + SERI_KURALI + """
JSON: {"adaylar":[{"konu":"kısa somut başlık","format":"carousel | reels","seri":"Basılabilir 5 Şey | Doktor Notu | Katman Katman",
"kanca":"ilk cümle","neden_ilgi_ceker":"1 cümle","trend_baglantisi":"hangi trend ya da 'yok'",
"yenilik":1-10 (son içeriklerden ne kadar farklı),"ilgi":1-10,"uygulanabilirlik":1-10 (görselleri üretmek ne kadar kolay)}]}"""
    cevap = openai_cagir(sistem, kullanici)
    adaylar = [a for a in cevap.get("adaylar", []) if isinstance(a, dict) and a.get("konu")]
    if not adaylar:
        raise ValueError("aday fikir gelmedi")
    gecmis = gecmis_konular()
    for a in adaylar:
        a["_benzerlik"] = max([benzerlik(a["konu"], g) for g in gecmis] or [0.0])
        try:
            puan = float(a.get("yenilik", 5)) * 1.3 + float(a.get("ilgi", 5)) + float(a.get("uygulanabilirlik", 5)) * 0.7
        except (TypeError, ValueError):
            puan = 0.0
        if str(a.get("trend_baglantisi", "yok")).strip().lower() not in ("yok", "", "none"):
            puan += 1.0
        a["_puan"] = round(puan, 1)
    uygun = [a for a in adaylar if a["_benzerlik"] < 0.5] or adaylar
    secilen = max(uygun, key=lambda a: a["_puan"])
    return secilen, adaylar


def elestir(taslak, uyarilar, bugun):
    """Taslağı sert bir editör gibi eleştirir; gerekirse düzeltilmiş tam taslak döndürür."""
    sistem = ("Sen sert ama adil bir editörsün. Bir sosyal medya taslağını kanal kurallarına, kanca gücüne ve özgünlüğe göre "
              "değerlendirir, gerekirse düzeltirsin. Yalnızca geçerli JSON döndür.")
    kullanici = f"""# KANAL PROFİLİ VE KURALLAR
{oku('ajan/kanal.md')}

# SON İÇERİKLER (benzerse taslak zayıftır)
{json.dumps(gecmis_konular(), ensure_ascii=False)}

# DENETİM UYARILARI (kod bulgusu)
{json.dumps(uyarilar, ensure_ascii=False)}

# TASLAK
{json.dumps(taslak, ensure_ascii=False)}

GÖREV: Taslağı 1-10 puanla (kanca gücü, özgünlük, kurallara uyum, doğal Türkçe, doğruluk) ve somut sorunları listele.
Puan 8 ve üstüyse ve sorun yoksa "duzeltilmis" null olsun. Aksi halde sorunları gideren, AYNI JSON şemasına ve AYNI format/seri
kurallarına uyan TAM bir düzeltilmiş taslak ver (yalnızca gerçekten sorunlu yerleri değiştir, kanca ve kurallar korunsun).
Uydurma rakam, süre ya da marka ekleme. gorsel_promptu / sahne_promptu içine karakterin görünüşünü (kıyafet, başlık, gözlük, kulaklık vb.) YAZMA, kod ekler.
{format_talimati()} {SERI_KURALI}
JSON: {{"puan": 1-10, "sorunlar": ["..."], "duzeltilmis": null veya taslağın tamamı}}"""
    return openai_cagir(sistem, kullanici)


def elestir_uygula(taslak, notlar, bugun):
    """En fazla 3 eleştiri: her turda sorun varsa düzeltilmiş taslak benimsenir; son puan SON taslağa aittir."""
    bilgi = {"ilk_puan": None, "puan": None, "sorunlar": [], "uygulandi": False, "turlar": 0}
    for tur in range(3):
        uyari = yasak_uyarilari(taslak)
        try:
            c = elestir(taslak, uyari, bugun)
        except Exception as e:
            print(f"UYARI: öz eleştiri çalışmadı: {e}")
            bilgi["durum"] = f"çalışmadı ({type(e).__name__})"
            break
        puan = c.get("puan")
        bilgi["turlar"] = tur + 1
        bilgi["puan"] = puan
        if tur == 0:
            bilgi["ilk_puan"] = puan
            bilgi["sorunlar"] = c.get("sorunlar") or []
        yeni = c.get("duzeltilmis")
        try:
            iyi = float(puan) >= 8
        except (TypeError, ValueError):
            iyi = False
        if iyi or tur == 2 or not isinstance(yeni, dict):
            break
        gecerli = yeni.get("konu") and yeni.get("format") in ("carousel", "reels") and (TERCIH["format"] == "otomatik" or yeni.get("format") == TERCIH["format"])
        if gecerli and len(yasak_uyarilari(yeni)) <= len(uyari):
            taslak = yeni
            bilgi["uygulandi"] = True
        else:
            bilgi["durum"] = "düzeltme geçersiz ya da daha çok uyarı doğurduğu için kullanılmadı"
            break
    notlar["elestiri"] = bilgi
    return taslak


def caption_temizle(caption):
    """Model hashtag'leri caption'a da yazarsa kaldır (ayrıca ekliyoruz)."""
    satirlar = [
        s for s in (caption or "").splitlines()
        if not (s.strip() and all(k.startswith("#") for k in s.split()))
    ]
    return "\n".join(satirlar).strip()


def numara_temizle(metin):
    """Başındaki '1.' gibi numaraları at; numarayı biz ekliyoruz."""
    return re.sub(r"^\s*\d+[.)]\s*", "", metin or "")


def _prompt_birlestir(govde, karakter, sonek, persona):
    """Sahne/slayt promptunu birleştirir; karakter tarifini yalnızca karakter gerçekten sahnedeyse ekler."""
    govde = (govde or "").strip()
    if persona:
        # Model (ya da öz eleştiri) karakter tarifini promptun içine yazmış olabilir; kod ekliyor, tekrar etmesin
        for p in (persona, persona.rstrip(".")):
            govde = govde.replace(p, "")
        govde = re.sub(r"\s{2,}", " ", govde).strip(" ")
    if govde and govde[-1] not in ".!?":
        govde += "."
    parcalar = [govde]
    if karakter and karakter_var_mi(govde):
        parcalar.append(persona if persona.endswith(".") else persona + ".")
    parcalar.append(sonek)
    return " ".join(p for p in parcalar if p)


def video_promptu(sh, persona):
    return _prompt_birlestir(sh.get("sahne_promptu"), sh.get("karakter_gorunur"), VIDEO_SONEKI, persona)


def gorsel_promptu(sl, persona):
    return _prompt_birlestir(sl.get("gorsel_promptu"), sl.get("karakter_gorunur"), GORSEL_SONEKI, persona)


def markdown_yaz(t, bugun, notlar=None):
    hashtag = " ".join(dict.fromkeys(t.get("hashtagler") or VARSAYILAN_ETIKETLER))
    persona = persona_tarifi()
    bicim = t.get("format", "")
    satirlar = [
        f"# {t['konu']}",
        "",
        f"- **Tarih:** {bugun}",
        f"- **Format:** {bicim}",
        f"- **Seri:** {t.get('seri', '')}",
    ]
    if bicim == "reels":
        toplam = sum(int(sh.get("sure_sn") or 0) for sh in t.get("sahneler") or [])
        satirlar.append(f"- **Süre:** {toplam} sn (sahne toplamı), dikey 9:16")
    else:
        satirlar.append(f"- **Slayt sayısı:** {len(t.get('slaytlar') or [])}, dikey 4:5")
    satirlar += ["- **Durum:** onay bekliyor", "", "## Kanca", t.get("kanca", ""), ""]

    if bicim == "reels":
        satirlar += ["## Sahneler"]
        for i, sh in enumerate(t.get("sahneler") or [], 1):
            satirlar += [
                f"### Sahne {i} ({sh.get('sure_sn', '?')} sn)",
                f"- **Görsel:** {sh.get('gorsel', '')}",
                f"- **Ekran yazısı:** {sh.get('ekran_yazisi', '')}",
                f"- **Doktor Filament der ki:** {sh.get('seslendirme', '')}",
                f"- **Video/görsel promptu (Flow ya da Gemini'ye yapıştır, resmi referans görselini ekle):** {video_promptu(sh, persona)}",
                "",
            ]
    else:
        satirlar += ["## Slaytlar", "Her slayt için Gemini'ye promptu yapıştır ve **resmi Doktor Filament referans görselini ekle.** Slayt metnini sonradan görselin üstüne ekleyeceğiz.", ""]
        for i, sl in enumerate(t.get("slaytlar") or [], 1):
            satirlar += [
                f"### Slayt {i}: {sl.get('baslik', '')}",
                f"- **Slayt metni:** {numara_temizle(sl.get('metin', ''))}",
                f"- **Gemini promptu:** {gorsel_promptu(sl, persona)}",
                "",
            ]

    satirlar += [
        "## Instagram caption",
        caption_temizle(t.get("instagram_caption", "")),
        YZ_SATIRI,
        "",
        hashtag,
        "",
        "## YouTube Shorts" + (" (slayt gösterisi videosu olarak)" if bicim != "reels" else ""),
        *(["Not: Carousel video değildir. YouTube için slaytlar Claude'a yüklenir, yazı eklenip dikey bir slayt gösterisi videosuna çevrilir."] if bicim != "reels" else []),
        f"**Başlık:** {(t.get('youtube_baslik') or '')[:100]}",
        "",
        caption_temizle(t.get("youtube_aciklama", "")),
        YZ_SATIRI,
        "",
        "## Facebook caption",
        caption_temizle(t.get("facebook_caption", "")),
        YZ_SATIRI,
        "",
        "## Model / lisans notu",
        t.get("model_notu", ""),
    ]
    if notlar:
        satirlar += ["", "## Ajan notları"]
        f = notlar.get("fikir")
        if f:
            satirlar.append(f"- **Seçilen fikir:** {f.get('konu')} (puan {f.get('_puan')}, geçmişe benzerlik {f.get('_benzerlik', 0):.2f}). "
                            f"Neden: {f.get('neden_ilgi_ceker', '')}. Trend bağlantısı: {f.get('trend_baglantisi', 'yok')}.")
            diger = [a.get("konu") for a in notlar.get("adaylar", []) if a is not f]
            if diger:
                satirlar.append("- **Elenen adaylar:** " + "; ".join(diger))
        e = notlar.get("elestiri")
        if e:
            satirlar.append(f"- **Öz eleştiri:** ilk puan {e.get('ilk_puan')}/10, son taslak {e.get('puan')}/10 ({e.get('turlar')} tur). Düzeltme "
                            + ("uygulandı." if e.get("uygulandi") else "uygulanmadı.") + (f" ({e['durum']})" if e.get("durum") else ""))
            satirlar += [f"  - Sorun: {x}" for x in e.get("sorunlar", [])]
        if notlar.get("trend_tarihi"):
            satirlar.append(f"- **Trend araştırması:** {notlar['trend_tarihi']}")
    uyarilar = yasak_uyarilari(t)
    if uyarilar:
        satirlar += ["", "## ⚠ Kontrol et"] + [f"- {u}" for u in uyarilar]
    return "\n".join(satirlar) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API çağırma, sadece prompt'u yazdır")
    ap.add_argument("--direktif", default="", help="Sahibinin o güne özel isteği (isteğe bağlı)")
    ap.add_argument("--hizli", action="store_true", help="Fikir seçimi ve öz eleştiriyi atla (tek çağrı)")
    ap.add_argument("--format", choices=["otomatik", "reels", "carousel"], default="otomatik", help="İçerik biçimi (zincirde sahibi seçer)")
    ap.add_argument("--benzersiz", action="store_true", help="Taslak dosya adına saat ekle (aynı gün üzerine yazmasın); zincir için")
    args = ap.parse_args()
    TERCIH["format"] = args.format

    bugun = datetime.date.today().isoformat()
    sistem, kullanici = prompt_olustur(bugun, args.direktif)
    if args.dry_run:
        print(sistem, "\n---\n", kullanici)
        return

    notlar = {}
    fikir = None
    if not args.hizli:
        try:
            fikir, adaylar = fikir_sec(bugun, args.direktif)
            notlar["fikir"], notlar["adaylar"] = fikir, adaylar
            print(f"Seçilen fikir: {fikir['konu']} (puan {fikir['_puan']}, benzerlik {fikir['_benzerlik']:.2f})")
        except Exception as e:
            print(f"UYARI: fikir seçimi çalışmadı, tek çağrıyla devam: {e}")
    tr = trendler()
    if tr:
        notlar["trend_tarihi"] = tr["tarih"]
    sistem, kullanici = prompt_olustur(bugun, args.direktif, fikir)
    taslak = openai_cagir(sistem, kullanici)
    if args.format != "otomatik" and taslak.get("format") != args.format:
        print(f"UYARI: model '{taslak.get('format')}' üretti, '{args.format}' isteniyordu; bir kez daha deneniyor.")
        taslak = openai_cagir(sistem, kullanici + f"\n\nÖNCEKİ DENEMEDE FORMAT YANLIŞTI. Format MUTLAKA \"{args.format}\" olmalı.")
    if not args.hizli:
        taslak = elestir_uygula(taslak, notlar, bugun)
        e = notlar.get("elestiri", {})
        print(f"Öz eleştiri: puan {e.get('puan')}, düzeltme {'uygulandı' if e.get('uygulandi') else 'uygulanmadı'}")
    TASLAK_DIZINI.mkdir(exist_ok=True)
    if args.benzersiz:
        cikti = TASLAK_DIZINI / f"{bugun}_zincir_{simdi_utc():%H%M%S}.md"
    elif args.direktif.strip():
        cikti = TASLAK_DIZINI / f"{bugun}_direktif_{datetime.datetime.now(datetime.timezone.utc):%H%M%S}.md"
    else:
        cikti = TASLAK_DIZINI / f"{bugun}.md"
    cikti.write_text(markdown_yaz(taslak, bugun, notlar), encoding="utf-8")
    print(f"Taslak yazıldı: {cikti.relative_to(KOK)}")
    kimlik = zincir_yaz(taslak, cikti, notlar, args.direktif)
    print(f"Zincir kimliği: {kimlik}")


if __name__ == "__main__":
    main()
