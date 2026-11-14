#!/usr/bin/env python3
"""Günlük Instagram içerik taslağı üretir (OpenAI API, ek bağımlılık yok).

Kullanım:
    OPENAI_API_KEY=... python3 ajan/uret.py            # taslak üretir
    python3 ajan/uret.py --dry-run                     # API çağırmadan prompt'u gösterir
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
TASLAK_DIZINI = KOK / "taslaklar"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


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


def prompt_olustur(bugun):
    sistem = (
        "Sen bir Instagram içerik ajanısın. Aşağıdaki kanal profiline ve stratejiye "
        "kesinlikle uy. Yalnızca geçerli JSON döndür."
    )
    kullanici = f"""# KANAL PROFİLİ
{oku('ajan/kanal.md')}

# STRATEJİ NOTLARI
{oku('ajan/strateji.md')}

# SON KONULAR (tekrar etme)
{json.dumps(gecmis_konular(), ensure_ascii=False)}

# GÖREV
Bugünün tarihi: {bugun}. Bugün için TEK bir gönderi taslağı üret.
JSON şeması:
{{
  "konu": "kısa başlık",
  "sutun": "içerik sütunlarından biri",
  "format": "reels | carousel | tek_gorsel",
  "kanca": "ilk satır / ilk 3 saniyede söylenecek cümle",
  "caption": "tam caption, kanca dahil, Türkçe",
  "hashtagler": ["#..."],
  "gorsel_promptu": "görsel üretimi için İngilizce, ayrıntılı prompt",
  "reels_senaryosu": ["sahne 1", "sahne 2"],
  "carousel_slaytlari": ["slayt 1 metni", "slayt 2 metni"],
  "cekim_notu": "kullanıcının gerçekten çekmesi/basması gereken şey"
}}
Kullanılmayan alanları boş liste bırak."""
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


def markdown_yaz(t, bugun):
    satirlar = [
        f"# {t['konu']}",
        "",
        f"- **Tarih:** {bugun}",
        f"- **Sütun:** {t.get('sutun', '')}",
        f"- **Format:** {t.get('format', '')}",
        "- **Durum:** onay bekliyor",
        "",
        "## Kanca",
        t.get("kanca", ""),
        "",
        "## Caption",
        t.get("caption", ""),
        "",
        " ".join(t.get("hashtagler", [])),
        "",
        "## Çekim / basım notu",
        t.get("cekim_notu", ""),
        "",
        "## Görsel promptu",
        t.get("gorsel_promptu", ""),
    ]
    if t.get("reels_senaryosu"):
        satirlar += ["", "## Reels senaryosu"] + [f"{i}. {s}" for i, s in enumerate(t["reels_senaryosu"], 1)]
    if t.get("carousel_slaytlari"):
        satirlar += ["", "## Carousel slaytları"] + [f"{i}. {s}" for i, s in enumerate(t["carousel_slaytlari"], 1)]
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
