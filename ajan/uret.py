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
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
TASLAK_DIZINI = KOK / "taslaklar"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
YZ_SATIRI = "🤖 Nozzle yapay zekâ ile üretilmiş bir karakterdir."


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
      "seslendirme": "Nozzle'un söyleyeceği cümle", "video_promptu": "İngilizce, video aracı için; Nozzle görünüm tarifini aynen içerir"}}
  ],
  "instagram_caption": "Türkçe, 3-5 kısa satır, sonunda tek çağrı",
  "youtube_baslik": "en fazla 60 karakter",
  "youtube_aciklama": "2-3 cümle, Türkçe",
  "facebook_caption": "Türkçe, 2-4 kısa satır",
  "hashtagler": ["#..."],
  "model_notu": "gösterilen nesne için nasıl bir serbest lisanslı model ya da basit kendi tasarım aranmalı"
}}

KALİTE KURALLARI:
- 4-7 sahne, toplam süre sure_sn ile uyumlu. Her sahnenin video_promptu Nozzle'un görünüm tarifini kelimesi kelimesine içersin.
- Kanca merak uyandırsın: rakam, çelişki ya da şaşırtıcı bir iddia. "Biliyor musun?" ve "mükemmel/harika" gibi dolgu yok.
- Gösterilen nesne gerçekten 3D yazıcıyla basılabilir olsun. Belirli bir model adı, tasarımcı, süre, gram ya da fiyat UYDURMA.
- Caption ve açıklamalara hashtag YAZMA ve yapay zekâ açıklaması YAZMA (kod ekler). Sahnelere numara yazma.
- Üç platform metni birbirinin kopyası olmasın; YouTube başlığı arama odaklı, Instagram ve Facebook daha samimi olsun."""
    return sistem, kullanici


def openai_cagir(sistem, kullanici):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        sys.exit("OPENAI_API_KEY ortam değişkeni tanımlı değil.")
    govde = json.dumps({
        "model": MODEL,
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
    with urllib.request.urlopen(istek, timeout=120) as yanit:
        veri = json.load(yanit)
    return json.loads(veri["choices"][0]["message"]["content"])


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
    hashtag = " ".join(dict.fromkeys(t.get("hashtagler", [])))
    satirlar = [
        f"# {t['konu']}",
        "",
        f"- **Tarih:** {bugun}",
        f"- **Seri:** {t.get('seri', '')}",
        f"- **Süre:** {t.get('sure_sn', '')} sn, dikey 9:16",
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
            f"- **Video promptu:** {sh.get('video_promptu', '')}",
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
