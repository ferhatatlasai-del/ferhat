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
    return konular


def hesap_durumu():
    yol = KOK / "ajan" / "hesap_durumu.md"
    return yol.read_text(encoding="utf-8") if yol.exists() else "(Henüz otomatik hesap verisi yok.)"


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
        ogeler = [(f"Slayt {i}", sl.get("gorsel_promptu", ""), sl.get("karakter_gorunur"))
                  for i, sl in enumerate(t.get("slaytlar") or [], 1)]
    for ad, prompt, gorunur in ogeler:
        if gorunur and not karakter_var_mi(prompt):
            uyari.append(f"{ad}: karakter görünür işaretli ama promptta 'Doctor Filament' yok; karakter tarifi eklenmedi.")
        if LATIN_DISI.search(prompt or ""):
            uyari.append(f"{ad}: promptta İngilizce dışı karakter var (Kiril vb.); araca yapıştırmadan önce düzelt.")
    return uyari


def prompt_olustur(bugun):
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

# GÖREV
Bugünün tarihi: {bugun}. Bugün için TEK bir içerik planı üret. Format "carousel" ya da "reels" olabilir;
son içeriklere bakarak formatı ve seriyi değiştir (aynısını art arda üretme). Video klip kredisi sınırlı olduğu için
emin değilsen "carousel" seç.

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
- format "carousel" ise 6-8 slayt üret, "sahneler" boş kalsın. 1. slayt güçlü kanca, son slayt yorum çağrısı (kapanış cümlesine yakın). Slayt metni en fazla 12 kelime.
- format "reels" ise 4-7 sahne üret, "slaytlar" boş kalsın. Sahne sürelerinin TOPLAMI sure_sn'ye eşit olsun.
- Reels'te İLK sahnenin seslendirmesi İmza cümleler bölümündeki AÇILIŞ cümlesi, SON sahnenin seslendirmesi KAPANIŞ cümlesi olsun (kelimesi kelimesine, değiştirme, kısaltma, çevirme, araya ekleme yapma). Aradaki sahneler konuyu anlatsın.
- gorsel_promptu ve sahne_promptu YALNIZCA İngilizce (Latin harfleri) olsun, somut eylem ve görüntü içersin, boş ya da genel olmasın. Görselde yazı isteme.
- Karakter görünüyorsa promptta "Doctor Filament" adı geçsin ve karakter_gorunur true olsun; karakter yoksa bu adı hiç kullanma ve false yap. Gerçek bir yazıcının nozzle'ı için "printer nozzle" de.
- Doktor esprisi yalnızca espridir: sağlık, tedavi, ilaç iddiası YAZMA.
- Kanca doğru ve merak uyandıran olsun: doğrulanabilir bir rakam (ör. katman sayısı) uydurma; çelişki ya da soru kullan. Yasak sözcükler: mükemmel, harika, muhteşem, eğlenceli, inanılmaz, "biliyor musun".
- Gösterilen nesne gerçekten 3D yazıcıyla basılabilir olsun. Belirli model adı, tasarımcı, süre, gram, fiyat UYDURMA. "10 saniyede basılıyor" gibi gerçek baskı süresi iddiası YASAK.
- Caption ve açıklamalara hashtag YAZMA ve yapay zekâ açıklaması YAZMA (kod ekler). Slayt ve sahne metinlerine numara yazma. Her zaman 5-8 hashtag döndür.
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
        "https://api.openai.com/v1/chat/completions",
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


def markdown_yaz(t, bugun):
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
        "## YouTube Shorts",
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
    uyarilar = yasak_uyarilari(t)
    if uyarilar:
        satirlar += ["", "## ⚠ Kontrol et"] + [f"- {u}" for u in uyarilar]
    return "\n".join(satirlar) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API çağırma, sadece prompt'u yazdır")
    args = ap.parse_args()

    bugun = datetime.date.today().isoformat()
    sistem, kullanici = prompt_olustur(bugun)
    if args.dry_run:
        print(sistem, "\n---\n", kullanici)
        return

    taslak = openai_cagir(sistem, kullanici)
    TASLAK_DIZINI.mkdir(exist_ok=True)
    cikti = TASLAK_DIZINI / f"{bugun}.md"
    cikti.write_text(markdown_yaz(taslak, bugun), encoding="utf-8")
    print(f"Taslak yazıldı: {cikti.relative_to(KOK)}")


if __name__ == "__main__":
    main()
