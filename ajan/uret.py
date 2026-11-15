#!/usr/bin/env python3
"""Günlük kısa video taslağı üretir (Nozzle karakteri; Instagram, YouTube Shorts, Facebook). OpenAI API, ek bağımlılık yok.

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
YZ_SATIRI = "🤖 Nozzle yapay zekâ ile üretilmiş bir karakterdir."
VARSAYILAN_ETIKETLER = ["#3dprinting", "#3dyazici", "#3dprint", "#nozzle", "#shorts"]
YASAK_SOZCUKLER = ["mükemmel", "harika", "muhteşem", "eğlenceli", "biliyor musun", "inanılmaz"]
VIDEO_SONEKI = "Vertical 9:16 short-form video, smooth camera motion, no on-screen text, no logos, no watermark."


def nozzle_tarifi():
    """Nozzle'un sabit görünüm tarifini kanal.md'den alır (tek kaynak)."""
    m = re.search(r'"(Nozzle: [^"]+)"', oku("ajan/kanal.md"))
    return m.group(1) if m else "Nozzle: a small friendly cartoon robot with a copper-brass 3D printer nozzle as its head."


def imza_cumleler():
    """Açılış ve kapanış imza cümlelerini kanal.md'den alır (tek kaynak)."""
    metin = oku("ajan/kanal.md")
    a = re.search(r'\*\*Açılış[^*]*\*\*\s*"([^"]+)"', metin)
    k = re.search(r'\*\*Kapanış[^*]*\*\*\s*"([^"]+)"', metin)
    return (a.group(1) if a else ""), (k.group(1) if k else "")


def _norm(metin):
    return re.sub(r"[^\w ]", "", metin.lower()).split()


def imza_uyarilari(t):
    acilis, kapanis = imza_cumleler()
    sahneler = t.get("sahneler", [])
    uyari = []
    if acilis and sahneler and " ".join(_norm(acilis)) not in " ".join(_norm(sahneler[0].get("seslendirme", ""))):
        uyari.append("İlk sahne seslendirmesi imza açılış cümlesini aynen içermiyor.")
    if kapanis and sahneler and " ".join(_norm(kapanis)) not in " ".join(_norm(sahneler[-1].get("seslendirme", ""))):
        uyari.append("Son sahne seslendirmesi imza kapanış cümlesini aynen içermiyor.")
    return uyari


def yasak_uyarilari(t):
    """Dolgu sözcüklerini ve boş kancayı bulup taslağın sonuna uyarı olarak yazar."""
    t_ = {k: v for k, v in t.items() if k not in ("seri", "konu")}
    metin = json.dumps(t_, ensure_ascii=False).lower()
    uyari = [f"Dolgu sözcüğü bulundu: \"{k}\"" for k in YASAK_SOZCUKLER if k in metin]
    if re.search(r"\d+\s*(saniye|dakika|dk|sn)[a-zçğıöşü]*\s*(de|da|içinde)?\s*bas", metin):
        uyari.append("Gerçek baskı süresi iddiası olabilir ('X saniyede basılıyor'). Doğru mu, kontrol et; hızlandırılmış video ise öyle yaz.")
    uyari += imza_uyarilari(t)
    for sh in t.get("sahneler", []):
        if re.search(r"[^\x00-\u024f\u2000-\u206f\u2190-\u21ff\U0001F000-\U0001FFFF\u2600-\u27bf]", sh.get("sahne_promptu", "")):
            uyari.append("Sahne promptunda İngilizce dışı karakter var (Kiril vb.); video aracına yapıştırmadan önce düzelt.")
            break
    return uyari


def oku(yol):
    return (KOK / yol).read_text(encoding="utf-8")


def gecmis_konular(adet=20):
    """Tekrarı önlemek için son taslakların konu başlıklarını toplar."""
    konular = []
    for dosya in sorted(TASLAK_DIZINI.glob("*.md"))[-adet:]:
        for satir in dosya.read_text(encoding="utf-8").splitlines():
            if satir.startswith("# "):
                konular.append(satir[2:].strip())
                break
    return konular


def hesap_durumu():
    yol = KOK / "ajan" / "hesap_durumu.md"
    return yol.read_text(encoding="utf-8") if yol.exists() else "(Henüz otomatik hesap verisi yok.)"


def prompt_olustur(bugun):
    sistem = (
        "Sen kısa video içerik ajanısın. Kanal profiline ve stratejiye kesinlikle uy. "
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

# SON KONULAR (tekrar etme)
{json.dumps(gecmis_konular(), ensure_ascii=False)}

# GÖREV
Bugünün tarihi: {bugun}. Bugün için TEK bir kısa video planı üret (20-30 saniye, dikey).
Seriyi son konulara bakarak değiştir (aynı seriyi art arda kullanma).
JSON şeması:
{{
  "konu": "kısa başlık",
  "seri": "10 Saniyede Basım | Basılabilir 5 Şey | Nozzle Notu",
  "sure_sn": 25,
  "kanca": "ilk 2 saniyede söylenen/yazılan cümle",
  "sahneler": [
    {{"sure_sn": 3, "gorsel": "Türkçe sahne tarifi", "ekran_yazisi": "ekrandaki kısa yazı",
      "seslendirme": "Nozzle'un söyleyeceği cümle", "nozzle_gorunur": true,
      "sahne_promptu": "İngilizce. SADECE bu sahnede ne olduğunu anlat: özne, hareket, kamera, ışık. Nozzle'un görünüşünü ANLATMA, kod ekler."}}
  ],
  "instagram_caption": "Türkçe, 3-5 kısa satır, sonunda tek çağrı",
  "youtube_baslik": "en fazla 60 karakter",
  "youtube_aciklama": "2-3 cümle, Türkçe",
  "facebook_caption": "Türkçe, 2-4 kısa satır",
  "hashtagler": ["#..."],
  "model_notu": "gösterilen nesne için nasıl bir serbest lisanslı model ya da basit kendi tasarım aranmalı"
}}

KALİTE KURALLARI:
- 4-7 sahne; sahne sürelerinin TOPLAMI sure_sn'ye eşit olsun.
- İLK sahnenin seslendirmesi, kanal.md'deki İmza cümleler bölümündeki AÇILIŞ cümlesi olsun (kelimesi kelimesine). SON sahnenin seslendirmesi KAPANIŞ cümlesi olsun. Bu cümleleri değiştirme, çevirme, kısaltma; araya başka cümle ekleme. Aradaki sahneler konuyu anlatsın.
- sahne_promptu o sahnenin somut eylemini ve görüntüsünü içersin (ör. "close-up of a printer nozzle laying orange filament layer by layer"). Boş ya da genel prompt yazma.
- sahne_promptu YALNIZCA İngilizce (Latin harfleri) olsun, başka dilden kelime karıştırma.
- nozzle_gorunur true ise sahne_promptu Nozzle'un NE YAPTIĞINI de söylesin (ör. "Nozzle points at the print bed"); Nozzle sahnede yoksa false yap. Gerçek yazıcının nozzle'ı ile karakter Nozzle'u karıştırma: karakterden "the robot Nozzle", yazıcı parçasından "printer nozzle" diye bahset.
- "10 Saniyede Basım" serisi, uzun bir baskının videoda 10 saniyeye HIZLANDIRILMASI demektir. Baskının gerçekten 10 saniyede yapıldığını ASLA iddia etme. Gerçek baskı süresi, gram, maliyet yazma.
- Kanca merak uyandırsın ama DOĞRU olsun: doğrulanabilir bir rakam (ör. katman sayısı gibi) uydurma; çelişki ya da soru kullan. Yasak sözcükler: mükemmel, harika, muhteşem, eğlenceli, inanılmaz, "biliyor musun".
- Her zaman 5-8 hashtag döndür.
- Gösterilen nesne gerçekten 3D yazıcıyla basılabilir olsun. Belirli bir model adı, tasarımcı, süre, gram ya da fiyat UYDURMA.
- Caption ve açıklamalara hashtag YAZMA ve yapay zekâ açıklaması YAZMA (kod ekler). Sahnelere numara yazma.
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
        s for s in caption.splitlines()
        if not (s.strip() and all(k.startswith("#") for k in s.split()))
    ]
    return "\n".join(satirlar).strip()


def numara_temizle(metin):
    """Başındaki '1.' gibi numaraları at; numarayı biz ekliyoruz."""
    return re.sub(r"^\s*\d+[.)]\s*", "", metin)


def markdown_yaz(t, bugun):
    hashtag = " ".join(dict.fromkeys(t.get("hashtagler") or VARSAYILAN_ETIKETLER))
    toplam = sum(int(sh.get("sure_sn") or 0) for sh in t.get("sahneler", []))
    nozzle = nozzle_tarifi()
    satirlar = [
        f"# {t['konu']}",
        "",
        f"- **Tarih:** {bugun}",
        f"- **Seri:** {t.get('seri', '')}",
        f"- **Süre:** {toplam} sn (sahne toplamı), dikey 9:16",
        "- **Durum:** onay bekliyor",
        "",
        "## Kanca",
        t.get("kanca", ""),
        "",
        "## Sahneler",
    ]
    for i, sh in enumerate(t.get("sahneler", []), 1):
        satirlar += [
            f"### Sahne {i} ({sh.get('sure_sn', '?')} sn)",
            f"- **Görsel:** {sh.get('gorsel', '')}",
            f"- **Ekran yazısı:** {sh.get('ekran_yazisi', '')}",
            f"- **Nozzle der ki:** {sh.get('seslendirme', '')}",
            f"- **Video promptu (Higgsfield'a yapıştır):** {sh.get('sahne_promptu', '')} {nozzle if sh.get('nozzle_gorunur') else ''} {VIDEO_SONEKI}".replace("  ", " "),
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
        f"**Başlık:** {t.get('youtube_baslik', '')[:100]}",
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
