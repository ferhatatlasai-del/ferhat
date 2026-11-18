#!/usr/bin/env python3
"""Shorts / Reels üretici: yayınlanmış ya da kuyruktaki yapay zekâ hikaye görsellerinden 4 sahneli, müzikli, dikey kısa video hazırlar.

- Yeni görsel ÜRETMEZ (görsel maliyeti yok): hikaye ajanının zaten ürettiği, atıflı ve etiketli görselleri kullanır.
- Başlık, ekran kancası ve açıklama için yapay zekâya yalnızca temizlenmiş tasarım adları gider (birkaç sent altı); anahtar yoksa sabit şablon kullanılır.
- Açıklamaya her tasarımın adı, tasarımcısı, lisansı ve bağlantısı yazılır (CC BY atfı) ve "yapay zekâ görseli" notu eklenir.
- Hiçbir şeyi YAYINLAMAZ: videoyu `videolar/` altına, taslağı `shorts/` altına yazar (durum "onay_bekliyor"). Panelden onaylanınca mevcut YouTube/Instagram akışı yayınlar.

Kullanım:
    python3 ajan/kisa_video.py [--sahne 4] [--hemen] [--kuru] [--git]
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402
import hikaye_muzik as MZ  # noqa: E402
import hikaye_uret as U  # noqa: E402
import shorts_uret as SU  # noqa: E402

KOK = H.KOK
DIZIN = KOK / "shorts"
AYAR = DIZIN / "ayar.json"
KULLANILAN = DIZIN / "kullanilan.json"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
VARSAYILAN = {"aktif": True, "sahne_sayisi": 4, "en_cok_bekleyen": 3}
SAHNE_SURESI, GECIS, FPS = 5.0, 0.6, 30


def json_oku(yol, varsayilan):
    try:
        return json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(varsayilan))


def yaz(yol, veri):
    pathlib.Path(yol).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def aday_hikayeler(kullanilan, sayi):
    """Kısa videoda daha önce kullanılmamış, atıflı yapay zekâ hikayeleri (yeniden eskiye)."""
    adaylar = []
    for o in sorted(H.kuyruk_oku(), key=lambda x: x.get("olusturma", ""), reverse=True):
        if o.get("kaynak") != "uretim" or not o.get("atif") or o.get("durum") not in ("yayinda", "planli", "onay_bekliyor"):
            continue
        if o["id"] in kullanilan or not (KOK / o["gorsel"]).exists():
            continue
        adaylar.append(o)
        if len(adaylar) >= sayi:
            break
    return adaylar


def kare_al(o, hedef):
    """Hikayenin görselini PNG olarak hedefe yazar (video ise ilk kare)."""
    kaynak = KOK / o["gorsel"]
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(kaynak), "-frames:v", "1", str(hedef)], capture_output=True, text=True)
    if r.returncode != 0 or not hedef.exists():
        raise RuntimeError("kare alınamadı: " + (r.stderr or "")[-120:])


# ---------- Metin ----------

def sahne_adi(o):
    return U.kisalt(U.yazi_temizle(U.ad_temizle(o["atif"]["ad"])), 24)


SABLON = {"baslik": "Bu hafta ilgi çeken {n} 3D baskı tasarımı", "kanca": "Bu hafta ilgimi çeken {n} tasarım",
          "aciklama": "Yazıcıda denemelik {n} pratik ve ilginç tasarım. Hangisini basardın?"}


def metin_uret(adlar):
    """(baslik, kanca, aciklama, sahne_altlari). Yapay zekâ yoksa ya da hata verirse sabit şablon."""
    n = len(adlar)
    sablon = {"baslik": SABLON["baslik"].format(n=n), "kanca": SABLON["kanca"].format(n=n), "aciklama": SABLON["aciklama"].format(n=n),
              "altlar": ["3D baskı fikri"] * n}
    if not os.environ.get("OPENAI_API_KEY"):
        return sablon
    istem = ("3D baskı hakkında Türkçe bir YouTube Shorts / Instagram Reels videosu için metin yaz. Videoda şu tasarımlar sırayla gösteriliyor: "
             + "; ".join(f"{i + 1}) {a}" for i, a in enumerate(adlar)) + ".\n"
             "KURALLAR: Tasarım hakkında olmayan özellik, süre, gram, fiyat, 'ben bastım' iddiası UYDURMA (görseller yapay zekâ ile üretilmiş temsili uyarlamalardır). "
             "Sağlık iddiası yok. Yasak sözcükler: mükemmel, harika, muhteşem, inanılmaz. Doğal Türkçe.\n"
             'Yalnızca JSON: {"baslik":"arama odaklı, en çok 70 karakter","kanca":"ekranda ilk sahnede görünecek kısa merak cümlesi, en çok 38 karakter",'
             '"aciklama":"2-3 kısa satır, samimi, son satırda yoruma davet","altlar":["her sahne için en çok 26 karakterlik kısa alt başlık (nesnenin ne işe yaradığı)"]}')
    govde = {"model": MODEL, "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": "Sen Türkçe kısa video metni yazan bir içerik editörüsün. Yalnızca geçerli JSON döndür."},
                          {"role": "user", "content": istem}]}
    try:
        r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
        with urllib.request.urlopen(r, timeout=90) as y:
            j = json.loads(json.load(y)["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"UYARI: metin için yapay zekâ kullanılamadı ({type(e).__name__}); şablon kullanılıyor.")
        return sablon
    temiz = lambda m, k: U.yazi_temizle(str(m or "")).replace("http", "")[:k].strip()
    altlar = [temiz(x, 26) for x in (j.get("altlar") or [])][:n]
    return {"baslik": temiz(j.get("baslik"), 70) or sablon["baslik"], "kanca": temiz(j.get("kanca"), 38) or sablon["kanca"],
            "aciklama": (str(j.get("aciklama") or "")[:400].replace("http", "").strip() or sablon["aciklama"]),
            "altlar": altlar + ["3D baskı fikri"] * (n - len(altlar))}


def aciklama_olustur(m, hikayeler):
    atif = ["", "Tasarımlar:"] + [f"• {U.ad_temizle(o['atif']['ad'])} — {o['atif'].get('tasarimci') or '?'} ({o['atif'].get('lisans')}) {U.temiz_adres(o["atif"].get("url"))}" for o in hikayeler]
    return (m["aciklama"].strip() + "\n" + "\n".join(atif) + "\n\nGörseller yapay zekâ ile üretilmiş temsili uyarlamalardır; tasarımların sahiplerine aittir.\n\n"
            "#3Dprinting #3Dbaski #3Dyazici #Shorts")


# ---------- Montaj ----------

def video_yap(kareler, adlar, altlar, kanca, cikti, stil, ton):
    font = SU.font_bul()
    n = len(kareler)
    toplam = n * SAHNE_SURESI - (n - 1) * GECIS
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        girdiler, filtre = [], []
        for i, kare in enumerate(kareler):
            girdiler += ["-loop", "1", "-t", str(SAHNE_SURESI + GECIS), "-i", str(kare)]
            (g / f"b{i}.txt").write_text(adlar[i], encoding="utf-8")
            (g / f"a{i}.txt").write_text(altlar[i], encoding="utf-8")
            kare_say = int((SAHNE_SURESI + GECIS) * FPS)
            ek = ""
            if i == 0:   # ilk sahnede ekran kancası
                (g / "k.txt").write_text(kanca, encoding="utf-8")
                ek = (f",drawtext=fontfile={font}:textfile={g / 'k.txt'}:expansion=none:fontsize=58:fontcolor=white:borderw=5:bordercolor=black@0.85:"
                      f"box=1:boxcolor=0x7c5cff@0.75:boxborderw=18:x=(w-text_w)/2:y=1500:enable='lte(t,3.2)'")
            filtre.append(f"[{i}:v]scale=2160:-1,zoompan=z='min(1+0.0006*on,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare_say}:s=1080x1920:fps={FPS},"
                          f"drawtext=fontfile={font}:textfile={g / f'b{i}.txt'}:expansion=none:fontsize=76:fontcolor=white:borderw=5:bordercolor=black@0.8:x=(w-text_w)/2:y=230,"
                          f"drawtext=fontfile={font}:textfile={g / f'a{i}.txt'}:expansion=none:fontsize=40:fontcolor=white:borderw=4:bordercolor=black@0.8:x=(w-text_w)/2:y=330"
                          f"{ek},format=yuv420p,setsar=1[v{i}]")
        son = "v0"
        for i in range(1, n):
            filtre.append(f"[{son}][v{i}]xfade=transition=fade:duration={GECIS}:offset={i * (SAHNE_SURESI - GECIS):.2f}[x{i}]")
            son = f"x{i}"
        (g / "s.txt").write_text("Takip et  @gurtechs3d", encoding="utf-8")
        filtre.append(f"[{son}]drawtext=fontfile={font}:textfile={g / 's.txt'}:expansion=none:fontsize=52:fontcolor=white:borderw=5:bordercolor=black@0.8:"
                      f"x=(w-text_w)/2:y=1560:enable='gte(t,{toplam - 3:.2f})'[v]")
        MZ.muzik_uret(g / "muzik.wav", int(toplam) + 1, stil, ton)
        komut = ["ffmpeg", "-y", "-loglevel", "error", *girdiler, "-i", str(g / "muzik.wav"), "-filter_complex", ";".join(filtre), "-map", "[v]", "-map", f"{n}:a",
                 "-t", f"{toplam:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(cikti)]
        r = subprocess.run(komut, capture_output=True, text=True)
        if r.returncode != 0 or not pathlib.Path(cikti).exists():
            raise RuntimeError("video hazırlanamadı: " + (r.stderr or "")[-300:])
    return toplam


def calis(a):
    ayar = dict(VARSAYILAN)
    ayar.update(json_oku(AYAR, {}))
    if not ayar["aktif"] and not a.hemen:
        print("Karar: bekle (kısa video üretimi kapalı)")
        return 0
    bekleyen = sum(1 for f in DIZIN.glob("s*.json") if json_oku(f, {}).get("durum") == "onay_bekliyor")
    if bekleyen >= ayar["en_cok_bekleyen"] and not a.hemen:
        print(f"Karar: bekle ({bekleyen} taslak onay bekliyor; yenisi üretilmez)")
        return 0
    sayi = max(3, min(int(a.sahne or ayar["sahne_sayisi"]), 6))
    kullanilan = set(json_oku(KULLANILAN, []))
    hikayeler = aday_hikayeler(kullanilan, sayi)
    if len(hikayeler) < 3:
        print(f"Karar: bekle (kullanılmamış hikaye görseli yetersiz: {len(hikayeler)}, en az 3 gerekir)")
        return 0
    H.ffmpeg_hazir()
    adlar = [sahne_adi(o) for o in hikayeler]
    m = metin_uret(adlar) if not a.kuru else {"baslik": SABLON["baslik"].format(n=len(adlar)), "kanca": SABLON["kanca"].format(n=len(adlar)),
                                              "aciklama": SABLON["aciklama"].format(n=len(adlar)), "altlar": ["3D baskı fikri"] * len(adlar)}
    z = H.simdi().astimezone(datetime.timezone.utc)
    damga = z.strftime("%Y%m%d%H%M%S")
    mevcut = len(list(DIZIN.glob("s*.json")))
    stil, ton = (mevcut + 3) % len(MZ.STILLER), MZ.TON_KAYMALARI[((mevcut + 3) // len(MZ.STILLER)) % len(MZ.TON_KAYMALARI)]
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        kareler = []
        for i, o in enumerate(hikayeler):
            kare_al(o, g / f"k{i}.png")
            kareler.append(g / f"k{i}.png")
        video_yolu = f"videolar/yukleme_{damga}.mp4"
        (KOK / "videolar").mkdir(parents=True, exist_ok=True)
        sure = video_yap(kareler, adlar, m["altlar"], m["kanca"], KOK / video_yolu, stil, ton)
    kimlik = f"s{z.strftime('%Y%m%d-%H%M%S')}"
    taslak = {"id": kimlik, "olusturma": z.strftime("%Y-%m-%dT%H:%M:%SZ"), "durum": "onay_bekliyor", "video": video_yolu, "sure": round(sure, 1),
              "baslik": m["baslik"], "aciklama": aciklama_olustur(m, hikayeler), "muzik": MZ.STILLER[stil]["ad"],
              "tasarimlar": [{"ad": U.ad_temizle(o["atif"]["ad"]), "tasarimci": o["atif"].get("tasarimci"), "lisans": o["atif"].get("lisans"), "url": o["atif"].get("url")} for o in hikayeler],
              "hikayeler": [o["id"] for o in hikayeler]}
    yaz(DIZIN / f"{kimlik}.json", taslak)
    yaz(KULLANILAN, sorted(kullanilan | {o["id"] for o in hikayeler})[-300:])
    print(f"Taslak hazır: {kimlik} ({sure:.1f} sn, müzik: {MZ.STILLER[stil]['ad']}); başlık: {m['baslik']}")
    if a.git:
        H.git_kaydet(f"Shorts üretici: {kimlik} taslağı", [DIZIN, KOK / "videolar"])
        H.bildir("Yeni Shorts taslağı hazır", f"{m['baslik']} — panelde onayını bekliyor.", adres="/", etiket="shorts")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sahne", type=int, help="sahne sayısı (3-6)")
    ap.add_argument("--hemen", action="store_true", help="kapalı ya da taslak limiti dolu olsa bile bir kez üret")
    ap.add_argument("--kuru", action="store_true", help="yapay zekâ kullanma (sabit metin)")
    ap.add_argument("--git", action="store_true", help="sonucu depoya yaz ve it")
    sys.exit(calis(ap.parse_args()))


if __name__ == "__main__":
    main()
