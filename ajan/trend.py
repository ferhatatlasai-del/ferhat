#!/usr/bin/env python3
"""Trend ajanı: internetten güncel 3D baskı / maker kısa video trendlerini araştırır.

OpenAI'ın web arama aracını (Responses API) kullanır. Sonuç ajan/trendler.json ve ajan/trendler.md dosyalarına yazılır;
içerik ajanı (uret.py) bunu fikir üretirken okur.

Kurallar:
- Başkasının içeriğini, görselini ya da ses/metnini kopyalamak için değil, konu ve açı fikri toplamak için.
- Kaynak bağlantıları yalnızca web aramasının gerçekten döndürdüğü adreslerle doğrulanır; doğrulanamayan öneri "zayıf" işaretlenir.
- Hiçbir şey yayınlamaz.

Kullanım:
    OPENAI_API_KEY=... python3 ajan/trend.py
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
MODEL = os.environ.get("OPENAI_TREND_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
ARAC_TURLERI = ["web_search", "web_search_preview"]
OPENAI_ADRES = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"

PROMPT = """Sen 3D baskı ve maker alanında kısa video / carousel trendlerini araştıran bir araştırma ajanısın.
İnternette ARA ve son 2-4 haftanın en çok ilgi gören konularını bul. Bakılacak yerler: YouTube Shorts, Instagram Reels,
TikTok, Pinterest, Reddit (r/3Dprinting, r/functionalprint, r/3Dprintmything), Printables, MakerWorld ve 3D baskı haber/blog siteleri.

Hedef kanal: Türkçe, 3D yazıcıyla basılabilen pratik ve ilginç nesneleri anlatan bir kanal. Karakter: yapay zekâ ile üretilmiş,
kurgusal bir mucit (Doktor Filament). İzleyici: Türkiye'deki yeni başlayanlar ve meraklılar.

İSTENEN: 6-8 somut öneri. Her biri için:
- konu: Türkçe, kısa ve somut (örn. bir nesne ya da bir baskı hatası, genel kategori değil)
- neden_trend: Türkçe, 1-2 cümle, aramada GÖRDÜĞÜN kanıtla (ne yükseliyor, nerede)
- kaynaklar: yalnızca aramada gerçekten açtığın sayfaların adresleri
- basilabilir: gerçekten ev tipi bir 3D yazıcıyla basılabiliyor mu (true/false) ve nedeni
- kanca_acisi: Türkçe, bu konuyu bizim kanalda ÖZGÜN anlatmak için bir açı (kimseyi kopyalama)
- format_onerisi: "carousel" ya da "reels"
- risk: lisans/telif/marka sorunu varsa yaz (örn. marka logosu, lisanslı karakter), yoksa "yok"
- guven: "yuksek" (birden fazla kaynak), "orta" (tek kaynak) ya da "dusuk"

Ayrıca "asiri_kullanilan" alanına izleyicinin artık bıktığı 3-5 klişe konu yaz.

KURALLAR: Uydurma. Bulamadığın şeyi yazma, öneri sayısı az kalırsa az yaz. Rakam, istatistik, tasarımcı adı UYDURMA.
Markalı ya da lisanslı karakter/ürün (film, oyun, spor kulübü logosu vb.) önerme. Sağlık iddiası içeren konu önerme.

Yalnızca geçerli JSON döndür, başka metin yazma:
{"oneriler":[{"konu":"","neden_trend":"","kaynaklar":["https://..."],"basilabilir":true,"basilabilir_notu":"","kanca_acisi":"","format_onerisi":"carousel","risk":"yok","guven":"orta"}],"asiri_kullanilan":["",""]}"""


def hata(m):
    print(f"HATA: {m}", file=sys.stderr)
    sys.exit(1)


def istek(arac_turu):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        hata("OPENAI_API_KEY tanımlı değil.")
    govde = json.dumps({"model": MODEL, "tools": [{"type": arac_turu}], "input": PROMPT}).encode()
    r = urllib.request.Request(
        f"{OPENAI_ADRES}/responses", data=govde, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(r, timeout=300) as y:
        return json.load(y)


def yanit_coz(veri):
    """Yanıttan metni ve web aramasının döndürdüğü doğrulanmış adresleri çıkarır."""
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
    return metin, adresler


def temiz_adres(u):
    return re.sub(r"[?&]utm_[^&]*", "", u or "").rstrip("/?&")


def temiz_metin(t):
    """Modelin metne gömdüğü ham bağlantı işaretlerini ([site](url)) temizler; kaynaklar ayrı alanda."""
    t = re.sub(r"\s*\(\[[^\]]*\]\([^)]*\)\)", "", t or "")
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t).strip()


def json_ayikla(metin):
    m = re.search(r"\{.*\}", metin, re.S)
    if not m:
        hata("Yanıtta JSON bulunamadı.")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        hata(f"JSON okunamadı: {e}")


def taze_mi(gun):
    yol = KOK / "ajan" / "trendler.json"
    if not yol.exists():
        return None
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
        z = datetime.datetime.strptime(v["tarih"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None
    yas = (datetime.datetime.now(datetime.timezone.utc) - z).total_seconds() / 86400
    return yas if yas < gun else None


def main():
    if "--en-fazla-gun" in sys.argv:
        try:
            gun = float(sys.argv[sys.argv.index("--en-fazla-gun") + 1])
        except (IndexError, ValueError):
            hata("--en-fazla-gun bir sayı bekliyor.")
        yas = taze_mi(gun)
        if yas is not None:
            print(f"Trendler taze ({yas:.1f} gün önce araştırıldı, sınır {gun:g} gün); yeniden araştırma atlandı.")
            return
    veri, kullanilan = None, None
    for tur in ARAC_TURLERI:
        try:
            veri = istek(tur)
            kullanilan = tur
            break
        except urllib.error.HTTPError as e:
            try:
                ayrinti = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:200]
            except Exception:
                ayrinti = ""
            print(f"UYARI: '{tur}' aracı olmadı (HTTP {e.code}: {ayrinti})")
    if veri is None:
        hata("Web arama aracı kullanılamadı; trend araştırması yapılamadı.")

    metin, dogrulanan = yanit_coz(veri)
    sonuc = json_ayikla(metin)
    oneriler = []
    for o in sonuc.get("oneriler", []):
        if not (o.get("konu") or "").strip():
            continue
        kaynaklar = [k for k in (o.get("kaynaklar") or []) if temiz_adres(k) in dogrulanan]
        for alan in ("neden_trend", "basilabilir_notu", "kanca_acisi"):
            o[alan] = temiz_metin(o.get(alan))
        o["kaynaklar"] = kaynaklar
        o["dogrulandi"] = bool(kaynaklar)
        if not kaynaklar:
            o["guven"] = "dusuk"
        oneriler.append(o)
    if not oneriler:
        hata("Hiç öneri alınamadı.")

    simdi = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cikti = {"tarih": simdi, "model": MODEL, "arac": kullanilan, "oneriler": oneriler,
             "asiri_kullanilan": sonuc.get("asiri_kullanilan", [])}
    (KOK / "ajan" / "trendler.json").write_text(json.dumps(cikti, ensure_ascii=False, indent=2), encoding="utf-8")

    satirlar = [f"# Güncel trendler", "", f"- **Araştırma zamanı:** {simdi}",
                f"- **Doğrulanan öneri:** {sum(1 for o in oneriler if o['dogrulandi'])} / {len(oneriler)}", ""]
    for o in oneriler:
        satirlar += [f"## {o['konu']}",
                     f"- **Neden trend:** {o.get('neden_trend', '')}",
                     f"- **Basılabilir:** {'evet' if o.get('basilabilir') else 'hayır'}. {o.get('basilabilir_notu', '')}",
                     f"- **Bizim açımız:** {o.get('kanca_acisi', '')}",
                     f"- **Format:** {o.get('format_onerisi', '')} · **Güven:** {o.get('guven', '')} · **Risk:** {o.get('risk', '')}"]
        satirlar += [f"- Kaynak: {k}" for k in o["kaynaklar"]] or ["- Kaynak: doğrulanamadı (zayıf öneri)"]
        satirlar.append("")
    if cikti["asiri_kullanilan"]:
        satirlar += ["## Aşırı kullanılan (kaçın)"] + [f"- {k}" for k in cikti["asiri_kullanilan"]] + [""]
    (KOK / "ajan" / "trendler.md").write_text("\n".join(satirlar), encoding="utf-8")
    print(f"{len(oneriler)} trend yazıldı ({sum(1 for o in oneriler if o['dogrulandi'])} doğrulanmış kaynaklı). Model: {MODEL}, araç: {kullanilan}")


if __name__ == "__main__":
    main()
