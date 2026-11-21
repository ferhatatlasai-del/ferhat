#!/usr/bin/env python3
"""Başarı hafızası: istatistikçinin raporundan (istatistik/son.json) en çok izlenen içerikleri çıkarır ve içerik ajanına "ilham" verir.

- ornekler(): Instagram + YouTube'da en çok izlenen başlıklar (platform başına en yükseğe göre normalleştirilir; aynı içerik iki platformda ise birleşir).
- ilham_metni(): senaryo isteminin içine konan kısa özet ("bu başlıklar tuttu, kalıbı al ama konuyu ve cümleleri kopyalama").
- turev_konu(): yapay zekâdan, en çok izlenenlerle AYNI KALIBI izleyen ama daha önce yapılmamış YENİ bir konu ister.

Tasarım ilkeleri: örnek sayısı küçük olduğundan (ilk haftalar) hiçbir şey otomatik "öğrenilip" davranışı kökten değiştirmez; yalnızca öneri/ilham olarak kullanılır,
her 4 videonun biri "keşif" olarak listeden gelir (bkz. viral_video.otomatik_konu). Hiçbir veri kişi bilgisi içermez (yalnızca herkese açık başlık ve sayılar).
"""
import json
import os
import pathlib
import re
import urllib.request

KOK = pathlib.Path(os.environ.get("HIKAYE_KOK") or pathlib.Path(__file__).resolve().parent.parent)
SON = KOK / "istatistik" / "son.json"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
DURAK = set("bir ve ile de da mi mu mı mü neden nasıl ne nedir için icin olur olmaz gibi daha en çok cok hangi kadar bu şu o ama veya ya".split())


def jeton(metin):
    """Karşılaştırma için anlamlı sözcük kümesi (küçük harf, Türkçe karakterler sadeleştirilmiş, durak sözcükler atılmış)."""
    t = str(metin or "").lower().translate(str.maketrans("çğıöşüâî", "cgiosuai"))
    return {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in DURAK}


def benzerlik(a, b):
    x, y = jeton(a), jeton(b)
    return len(x & y) / max(1, min(len(x), len(y)))


def _oku():
    try:
        return json.loads(SON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def icerikler():
    """[{baslik, izlenme: {platform: sayı}, puan}] puana göre azalan. Başlığı olmayan (eski/başlıksız) gönderiler atlanır."""
    o = _oku()
    ham = []
    ig = (o.get("instagram") or {}).get("gonderiler") or []
    yt = (o.get("youtube") or {}).get("videolar") or []
    for plat, liste in (("Instagram", ig), ("YouTube", yt)):
        olcek = max([x.get("izlenme") or 0 for x in liste] + [1])
        for x in liste:
            iz, baslik = x.get("izlenme"), " ".join(str(x.get("baslik") or "").split())
            if iz is None or len(baslik) < 8 or re.search(r"tanış|gurtech|hoş geldin|kanal", baslik.lower()):
                continue   # kanal tanıtımı gibi konu olmayan içerikler örnek alınmaz
            ham.append({"baslik": baslik, "plat": plat, "izlenme": int(iz), "puan": iz / olcek})
    # aynı içerik iki platformda: benzer başlıkları birleştir
    sonuc = []
    for h in sorted(ham, key=lambda x: -x["puan"]):
        for s in sonuc:
            if benzerlik(h["baslik"], s["baslik"]) >= 0.6 and h["plat"] not in s["izlenme"]:
                s["izlenme"][h["plat"]] = h["izlenme"]
                s["puan"] = (s["puan"] + h["puan"]) / 2 + 0.15   # iki platformda da tutan içerik bonus alır
                break
        else:
            sonuc.append({"baslik": h["baslik"], "izlenme": {h["plat"]: h["izlenme"]}, "puan": h["puan"]})
    return sorted(sonuc, key=lambda x: -x["puan"])


def ornekler(n=5):
    return icerikler()[:n]


def yapilmis_basliklar():
    """Daha önce ürettiğimiz viral video başlık ve konuları (tekrar etmemek için)."""
    liste = []
    for f in sorted((KOK / "shorts").glob("s*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("tur") == "viral":
            liste += [x for x in (d.get("baslik"), d.get("konu")) if x]
    return liste


def ilham_metni(n=5):
    """Senaryo isteminin içine konacak metin; veri yoksa boş döner (istem değişmez)."""
    ork = ornekler(n)
    if not ork:
        return ""
    satir = "\n".join("- «{}» ({})".format(x["baslik"][:80], ", ".join("{} {:,} izlenme".format(p, v).replace(",", ".") for p, v in x["izlenme"].items())) for x in ork)
    return ("\nGEÇMİŞ PERFORMANS (kendi kanalımızın en çok izlenen içerikleri):\n" + satir +
            "\nBu başlıkların ORTAK özelliklerini örnek al: konuyu seçme biçimi (günlük bir sorun + pratik çözüm gibi), başlığın kancası (soru, sayı, 'çoğu kişi…'), tempo ve yapı. "
            "Ama bu başlıkları ya da cümlelerini KOPYALAMA; konu ve açı yeni olsun.\n")


def _sohbet(istem, sicaklik=0.8):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    govde = {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": sicaklik,
             "messages": [{"role": "system", "content": "Sen Türkçe 3D baskı içerik stratejisti bir editörsün. Yalnızca geçerli JSON döndür."},
                          {"role": "user", "content": istem}]}
    r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                               headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(r, timeout=90) as y:
        return json.loads(json.load(y)["choices"][0]["message"]["content"])


def turev_konu(n=5, eski=None):
    """En çok izlenenlerin KALIBINI izleyen, daha önce yapılmamış yeni bir konu: (konu, ipucu, ilham_basliklari) ya da None."""
    ork = ornekler(n)
    if not ork:
        return None
    eski = list(eski if eski is not None else yapilmis_basliklar())
    istem = ("Kanalımızın (3D yazıcı ve 3D baskı, Türkçe Shorts/Reels) EN ÇOK izlenen içerikleri:\n" +
             "\n".join("- {} ({})".format(x["baslik"][:80], ", ".join("{} izlenme {}".format(p, v) for p, v in x["izlenme"].items())) for x in ork) +
             "\n\nDaha önce ürettiğimiz konular/başlıklar (BUNLARI TEKRAR ETME, çok benzer konu da önerme):\n" + "\n".join("- " + e[:80] for e in eski[-40:]) +
             "\n\nGÖREV: Bu başarılı içeriklerin KALIBINI (sorun türü, kanca, yapı) izleyen ama konusu YENİ ve farklı olan 3 video konusu öner. "
             "Konu 3D baskı topluluğunda yaygın, gerçek bir ihtiyaç olsun; uydurma iddia, marka veya fiyat içermesin.\n"
             'Yalnızca JSON: {"konular":[{"konu":"en çok 70 karakter, arama odaklı","ipucu":"video için 1-2 cümle: hangi doğru bilgiler/ipuçları işlenecek"}]}')
    try:
        j = _sohbet(istem)
    except Exception as e:
        print(f"UYARI: türev konu alınamadı ({type(e).__name__}); konu listesi kullanılacak.")
        return None
    for k in (j or {}).get("konular", []):
        konu, ipucu = " ".join(str(k.get("konu") or "").split())[:80], " ".join(str(k.get("ipucu") or "").split())[:300]
        if len(konu) < 8:
            continue
        if any(benzerlik(konu, e) >= 0.6 for e in eski):
            continue   # çok benzer: atla
        return konu, ipucu, [x["baslik"] for x in ork]
    return None


if __name__ == "__main__":
    for x in ornekler(8):
        print(round(x["puan"], 2), x["baslik"][:60], x["izlenme"])
    print(ilham_metni())
