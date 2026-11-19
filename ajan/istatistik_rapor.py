#!/usr/bin/env python3
"""İstatistikçi ajan: tüm paylaşımların izlenmelerini toplar, telefona kısa rapor bildirimi gönderir.

Kaynaklar (yalnızca OKUR, hiçbir şey paylaşmaz ya da değiştirmez):
  - Instagram: Reels/videolar/gönderiler (izlenme, erişim, beğeni, yorum) ve hikayeler (izlenme, erişim)
  - YouTube: Shorts ve videolar (izlenme, beğeni, yorum)
Anahtar ya da izin yoksa ilgili kısım "izin yok" diye işaretlenir; rapor kalan veriyle yine çıkar.

Çıktılar (istatistik/ klasörü):
  son.json          en son anlık görüntü (panel bunu okur)
  gecmis.jsonl      her çalışmanın kısa özeti (artışı hesaplamak ve grafik için)
  hikayeler.json    hikayelerin en yüksek izlenme değerleri (hikaye 24 saatte silinir, değeri kaybetmeyelim)
  ayar.json         {aktif, artis_yoksa_atla}  (panelden değiştirilir)

Kullanım:
    python3 ajan/istatistik_rapor.py --git            # topla, yaz, bildir, depoya it
    python3 ajan/istatistik_rapor.py --git --elle     # elle başlatma: "artış yoksa atla" kuralını yok sayar
    python3 ajan/istatistik_rapor.py --kuru           # bildirim göndermez, depoya yazmaz (yalnızca ekrana yazar)
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import istatistik as IG  # noqa: E402  (Instagram okuma yardımcıları)

KOK = pathlib.Path(__file__).resolve().parent.parent
KLASOR = KOK / "istatistik"
VARSAYILAN_AYAR = {"aktif": True, "artis_yoksa_atla": False}
HIKAYE_SAAT = 36          # yayınlandıktan sonra bu kadar saat boyunca hikaye değerleri yeniden okunur
GECMIS_SINIR = 400        # gecmis.jsonl'de en çok bu kadar satır (günde 5 çalışma ≈ 80 gün)


def simdi():
    return datetime.datetime.now(datetime.timezone.utc)


def tr_saat(an=None):
    return (an or simdi()) + datetime.timedelta(hours=3)


def json_oku(yol, varsayilan):
    try:
        return json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return varsayilan


def json_yaz(yol, veri):
    pathlib.Path(yol).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sayi(n):
    """1240 -> 1.240 (Türkçe binlik ayracı)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return "?"


def isaretli(n):
    return ("+" if n > 0 else "") + sayi(n)


# ---------- Instagram ----------

def metrik_oku(taban, medya_id, listeler):
    """Metrik listelerini sırayla dener; ilk çalışanın sonucunu döndürür. (None = izin/destek yok)"""
    son_hata = ""
    for metrikler in listeler:
        try:
            veri = IG.al(taban, f"{medya_id}/insights", metric=metrikler)
            sonuc = {}
            for m in veri.get("data", []):
                if "values" in m and m["values"]:
                    sonuc[m["name"]] = m["values"][0].get("value", 0)
                elif "total_value" in m:
                    sonuc[m["name"]] = m["total_value"].get("value", 0)
            if sonuc:
                return sonuc, ""
        except urllib.error.HTTPError as e:
            son_hata = IG.hata_ozeti(e)
        except Exception as e:
            son_hata = type(e).__name__
    return None, son_hata


def instagram_topla():
    sonuc = {"durum": "atlandi", "izin": False, "takipci": None, "gonderiler": [], "hata": ""}
    if not os.environ.get("IG_ACCESS_TOKEN"):
        sonuc["hata"] = "IG_ACCESS_TOKEN tanımlı değil"
        return sonuc, None
    hatalar = []
    for taban, kimlik in IG.ADAYLAR:
        ad = taban.split("//")[1].split("/")[0]
        profil = medya = None
        son_hata = ""
        for alanlar in ("username,followers_count,media_count", "username,followers_count", "username,media_count"):
            try:
                profil = IG.al(taban, kimlik, fields=alanlar)
                break
            except urllib.error.HTTPError as e:
                son_hata = "profil: " + IG.hata_ozeti(e)
            except Exception as e:
                son_hata = f"profil: alınamadı ({type(e).__name__})"
        if profil is None:
            hatalar.append(f"{ad} {son_hata}")
            continue
        # gönderi alanları kademeli: en zengin liste kabul edilmezse eski, çalıştığı bilinen listeye dön
        for alanlar in ("id,caption,media_type,media_product_type,like_count,comments_count,timestamp,permalink",
                        "id,caption,media_type,like_count,comments_count,timestamp,permalink",
                        "id,caption,media_type,like_count,comments_count,timestamp"):
            try:
                medya = IG.al(taban, f"{kimlik}/media", fields=alanlar, limit=30)
                break
            except urllib.error.HTTPError as e:
                son_hata = "gönderiler: " + IG.hata_ozeti(e)
            except Exception as e:
                son_hata = f"gönderiler: alınamadı ({type(e).__name__})"
        if medya is None:
            hatalar.append(f"{ad} {son_hata}")
            continue
        sonuc["durum"] = "tamam"
        sonuc["takipci"] = profil.get("followers_count")
        izinli = 0
        for m in medya.get("data", []):
            tur = m.get("media_product_type") or ""
            ad = "Reels" if tur == "REELS" or (m.get("media_type") == "VIDEO" and tur != "STORY") else ("Carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else "Gönderi")
            kayit = {"id": m["id"], "tur": ad, "tarih": (m.get("timestamp") or "")[:19], "baslik": (m.get("caption") or "").split("\n")[0][:60],
                     "begeni": m.get("like_count", 0), "yorum": m.get("comments_count", 0), "link": m.get("permalink", ""),
                     "izlenme": None, "erisim": None}
            # yalnızca son 45 günün gönderileri için metrik çek (gereksiz çağrı olmasın)
            try:
                yas = (simdi() - datetime.datetime.fromisoformat((m.get("timestamp") or "")[:19] + "+00:00")).days
            except Exception:
                yas = 0
            if yas <= 45:
                met, hata = metrik_oku(taban, m["id"], ("views,reach,saved,shares", "reach,saved", "reach"))
                if met is not None:
                    izinli += 1
                    kayit["izlenme"] = met.get("views", met.get("plays"))
                    kayit["erisim"] = met.get("reach")
                elif hata and not sonuc["hata"]:
                    sonuc["hata"] = hata
            sonuc["gonderiler"].append(kayit)
        sonuc["izin"] = izinli > 0
        sonuc["anahtar_izinleri"] = anahtar_izinleri(taban)
        if hatalar and not sonuc["hata"]:
            sonuc["hata"] = " | ".join(hatalar)
        return sonuc, taban
    sonuc["hata"] = " | ".join(hatalar) or sonuc["hata"]
    sonuc["tani"] = anahtar_tani()
    return sonuc, None


def anahtar_izinleri(taban):
    """Anahtara verilmiş izinlerin adları (anahtarın kendisi değil). Hangi iznin eksik olduğunu görmek için."""
    try:
        veri = IG.al(taban, "me/permissions")
        return sorted(f"{x.get('permission')}" + ("" if x.get("status") == "granted" else f"({x.get('status')})") for x in veri.get("data", []))
    except Exception:
        return None


def anahtar_tani():
    """Instagram profili okunamadığında: anahtar hangi izinlere ve hangi Instagram hesaplarına erişebiliyor? (anahtar yazılmaz)"""
    taban = "https://graph.facebook.com/v21.0"
    cikti = {}
    try:
        veri = IG.al(taban, "me/permissions")
        cikti["izinler"] = sorted(f"{x.get('permission')}" + ("" if x.get("status") == "granted" else f"({x.get('status')})") for x in veri.get("data", []))
    except urllib.error.HTTPError as e:
        cikti["izinler"] = "okunamadı: " + IG.hata_ozeti(e)[:120]
    except Exception as e:
        cikti["izinler"] = f"okunamadı ({type(e).__name__})"
    try:
        veri = IG.al(taban, "me/accounts", fields="instagram_business_account", limit=25)
        sayfalar = veri.get("data", [])
        cikti["sayfa_sayisi"] = len(sayfalar)
        cikti["instagram_kimlikleri"] = [str((x.get("instagram_business_account") or {}).get("id")) for x in sayfalar if x.get("instagram_business_account")]
    except urllib.error.HTTPError as e:
        cikti["sayfalar"] = "okunamadı: " + IG.hata_ozeti(e)[:120]
    except Exception as e:
        cikti["sayfalar"] = f"okunamadı ({type(e).__name__})"
    return cikti


def hikayeleri_topla(taban):
    """Kuyruktaki yayınlanmış hikayelerin Instagram değerlerini oku; en yüksek değeri sakla (hikaye 24 saatte silinir)."""
    depo = json_oku(KLASOR / "hikayeler.json", {})
    izin = False
    kuyruk = KOK / "hikaye" / "kuyruk"
    kayitlar = []
    if kuyruk.exists():
        for f in sorted(kuyruk.glob("*.json")):
            o = json_oku(f, {})
            y = o.get("yayin") or {}
            if o.get("durum") == "yayinda" and y.get("medya_kimligi") and y.get("tarih"):
                kayitlar.append((o, y))
    for o, y in kayitlar:
        mid = str(y["medya_kimligi"])
        e = depo.setdefault(mid, {"tarih": y["tarih"], "baslik": (o.get("baslik") or (o.get("atif") or {}).get("ad") or "")[:60] or "Hikaye", "izlenme": 0, "erisim": 0, "okundu": False})
        try:
            yas_saat = (simdi() - datetime.datetime.fromisoformat(y["tarih"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception:
            yas_saat = 999
        if taban and yas_saat <= HIKAYE_SAAT:
            met, _ = metrik_oku(taban, mid, ("views,reach,replies,shares", "views,reach", "reach,replies", "reach"))
            if met is not None:
                izin = True
                e["okundu"] = True
                e["izlenme"] = max(e.get("izlenme", 0), int(met.get("views", met.get("impressions", 0)) or 0))
                e["erisim"] = max(e.get("erisim", 0), int(met.get("reach", 0) or 0))
                e["yanit"] = max(e.get("yanit", 0), int(met.get("replies", 0) or 0))
    # eskileri buda (en yeni 400)
    if len(depo) > 400:
        for k in sorted(depo, key=lambda x: depo[x].get("tarih", ""))[:len(depo) - 400]:
            depo.pop(k, None)
    return depo, izin


# ---------- YouTube ----------

def sure_saniye(iso):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    s, d, h = int(m.group(3) or 0), int(m.group(2) or 0), int(m.group(1) or 0)
    return h * 3600 + d * 60 + s


def yt_istek(yol, belirtec, **p):
    p = {k: v for k, v in p.items() if v is not None}
    r = urllib.request.Request((os.environ.get("YT_API_ADRES") or "https://www.googleapis.com/youtube/v3/") + yol + "?" + urllib.parse.urlencode(p), headers={"Authorization": "Bearer " + belirtec})
    with urllib.request.urlopen(r, timeout=40) as y:
        return json.load(y)


def youtube_topla():
    sonuc = {"durum": "atlandi", "izin": False, "videolar": [], "hata": ""}
    # Yükleme anahtarı yalnızca video yükleme izni taşır; izlenmeyi okumak için ayrı bir okuma anahtarı (YT_OKU_REFRESH_TOKEN) kullanılır.
    yenileme = os.environ.get("YT_OKU_REFRESH_TOKEN") or os.environ.get("YT_REFRESH_TOKEN")
    if not (os.environ.get("YT_CLIENT_ID") and os.environ.get("YT_CLIENT_SECRET") and yenileme):
        sonuc["hata"] = "YouTube anahtarları tanımlı değil"
        return sonuc
    try:
        veri = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                       "refresh_token": yenileme, "grant_type": "refresh_token"}).encode()
        with urllib.request.urlopen(urllib.request.Request(os.environ.get("YT_TOKEN_ADRES") or "https://oauth2.googleapis.com/token", data=veri), timeout=40) as y:
            belirtec = json.load(y)["access_token"]
    except Exception as e:
        sonuc["hata"] = f"YouTube girişi başarısız ({type(e).__name__})"
        return sonuc
    try:
        kanal = yt_istek("channels", belirtec, part="contentDetails", mine="true")
        liste = kanal["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ogeler = yt_istek("playlistItems", belirtec, part="contentDetails", playlistId=liste, maxResults=30).get("items", [])
        kimlikler = [o["contentDetails"]["videoId"] for o in ogeler]
        if not kimlikler:
            sonuc["durum"] = "tamam"
            sonuc["izin"] = True
            return sonuc
        videolar = yt_istek("videos", belirtec, part="snippet,statistics,contentDetails", id=",".join(kimlikler)).get("items", [])
    except urllib.error.HTTPError as e:
        try:
            ayrinti = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:140]
        except Exception:
            ayrinti = ""
        sonuc["hata"] = f"YouTube HTTP {e.code}: {ayrinti}" if e.code != 403 else f"YouTube okuma izni yok (HTTP 403): YT_OKU_REFRESH_TOKEN gerekir. {ayrinti}"
        return sonuc
    except Exception as e:
        sonuc["hata"] = f"YouTube okunamadı ({type(e).__name__})"
        return sonuc
    for v in videolar:
        st = v.get("statistics", {})
        sn = sure_saniye((v.get("contentDetails") or {}).get("duration"))
        sonuc["videolar"].append({"id": v["id"], "tur": "Short" if 0 < sn <= 180 else "Video", "tarih": (v["snippet"].get("publishedAt") or "")[:19],
                                  "baslik": (v["snippet"].get("title") or "")[:60], "izlenme": int(st.get("viewCount", 0) or 0),
                                  "begeni": int(st.get("likeCount", 0) or 0), "yorum": int(st.get("commentCount", 0) or 0),
                                  "link": "https://www.youtube.com/watch?v=" + v["id"]})
    sonuc["durum"] = "tamam"
    sonuc["izin"] = True
    return sonuc


# ---------- Birleştirme ----------

def toplamlar(ig, yt, hikayeler):
    def topla(liste, tur=None, alan="izlenme"):
        return sum((x.get(alan) or 0) for x in liste if (tur is None or x.get("tur") == tur))
    reels = topla(ig["gonderiler"], "Reels")
    carousel = topla(ig["gonderiler"], "Carousel") + topla(ig["gonderiler"], "Gönderi")
    short = topla(yt["videolar"], "Short")
    yt_video = topla(yt["videolar"], "Video")
    hikaye = sum(e.get("izlenme", 0) for e in hikayeler.values())
    return {"reels": reels, "gonderi": carousel, "short": short, "youtube_video": yt_video, "hikaye": hikaye,
            "toplam": reels + carousel + short + yt_video + hikaye,
            "begeni": topla(ig["gonderiler"], None, "begeni") + topla(yt["videolar"], None, "begeni"),
            "yorum": topla(ig["gonderiler"], None, "yorum") + topla(yt["videolar"], None, "yorum")}


def en_iyi(ig, yt, hikayeler):
    adaylar = [(x.get("izlenme") or 0, f"{x['tur']}: {x['baslik'] or 'başlıksız'}") for x in ig["gonderiler"] + yt["videolar"]]
    adaylar += [(e.get("izlenme", 0), f"Hikaye: {e.get('baslik') or 'Hikaye'}") for e in hikayeler.values()]
    adaylar = [a for a in adaylar if a[0] > 0]
    return max(adaylar) if adaylar else None


def bildirim_metni(an, ig, yt, hikayeler, top, onceki, eksikler, hikaye_izin=False):
    fark = top["toplam"] - (onceki or {}).get("toplam", top["toplam"])
    bugun_hikaye = sum(1 for e in hikayeler.values() if (e.get("tarih") or "")[:10] == simdi().strftime("%Y-%m-%d"))
    baslik = f"📊 İzlenme raporu {tr_saat(an).strftime('%H:%M')}"
    eksik_veri = not ig["izin"] or not yt["izin"]
    parca = [f"Toplam {sayi(top['toplam'])}" + (" (eksik veri)" if eksik_veri else (f" ({isaretli(fark)})" if onceki else ""))]
    parca.append(f"Reels {sayi(top['reels'])}" if ig["izin"] else "Reels ?")
    parca.append(f"Short {sayi(top['short'])}" if yt["izin"] else "Short ?")
    if top["hikaye"] > 0 or hikaye_izin:
        parca.append(f"Hikaye {sayi(top['hikaye'])}" + (f" ({bugun_hikaye} bugün)" if bugun_hikaye else ""))
    else:
        parca.append("Hikaye ?")
    if ig.get("takipci") is not None:
        pf = ((onceki or {}).get("takipci"))
        parca.append(f"Takipçi {sayi(ig['takipci'])}" + (f" ({isaretli(ig['takipci'] - pf)})" if isinstance(pf, int) and ig["takipci"] != pf else ""))
    govde = " · ".join(parca)
    iyi = en_iyi(ig, yt, hikayeler)
    if iyi and len(govde) < 150:
        govde += f" · En iyi {iyi[1][:28]} {sayi(iyi[0])}"
    if eksikler and len(govde) < 170:
        govde += " · " + "; ".join(eksikler)
    return baslik, govde[:200], fark


def depoya_it(mesaj):
    c = lambda *a: subprocess.run(["git", "-C", str(KOK), *a], check=False)  # noqa: E731
    c("config", "user.name", "istatistik-ajani")
    c("config", "user.email", "istatistik-ajani@users.noreply.github.com")
    c("add", "-A", "--", "istatistik")
    if subprocess.run(["git", "-C", str(KOK), "diff", "--cached", "--quiet"]).returncode != 0:
        c("commit", "-q", "-m", mesaj)
        for _ in range(4):
            c("pull", "--rebase", "-q")
            if subprocess.run(["git", "-C", str(KOK), "push", "-q"]).returncode == 0:
                break


def calis(a):
    ayar = {**VARSAYILAN_AYAR, **json_oku(KLASOR / "ayar.json", {})}
    if not ayar.get("aktif") and not a.elle:
        print("İstatistik raporu duraklatılmış (panelden açılabilir); atlandı.")
        return 0
    an = simdi()
    # İstatistik için ayrı bir anahtar tanımlıysa onu kullan: yayın anahtarı (IG_ACCESS_TOKEN) deneme yüzünden bozulmasın
    ozel = (os.environ.get("IG_ISTATISTIK_TOKEN") or "").strip()
    if ozel:
        os.environ["IG_ACCESS_TOKEN"] = ozel
        print("Instagram: istatistik için ayrı anahtar (IG_ISTATISTIK_TOKEN) kullanılıyor.")
    ig, taban = instagram_topla()
    hikayeler, hikaye_izin = hikayeleri_topla(taban)
    yt = youtube_topla()
    top = toplamlar(ig, yt, hikayeler)
    gecmis_yol = KLASOR / "gecmis.jsonl"
    satirlar = [json.loads(s) for s in gecmis_yol.read_text(encoding="utf-8").splitlines() if s.strip()] if gecmis_yol.exists() else []
    onceki = satirlar[-1] if satirlar else None
    eksikler = []
    if ig["durum"] == "tamam" and not ig["izin"]:
        eksikler.append("Instagram izlenme izni yok")
    elif ig["durum"] != "tamam":
        eksikler.append("Instagram okunamadı")
    if yt["durum"] != "tamam":
        eksikler.append("YouTube okunamadı")
    elif not yt["izin"]:
        eksikler.append("YouTube izni yok")
    baslik, govde, fark = bildirim_metni(an, ig, yt, hikayeler, top, onceki, eksikler, hikaye_izin)
    satir = {"t": an.strftime("%Y-%m-%dT%H:%M:%SZ"), "toplam": top["toplam"], "reels": top["reels"], "short": top["short"], "hikaye": top["hikaye"],
             "gonderi": top["gonderi"], "youtube_video": top["youtube_video"], "begeni": top["begeni"], "yorum": top["yorum"], "takipci": ig.get("takipci")}
    son = {"tarih": satir["t"], "tr_saat": tr_saat(an).strftime("%d.%m.%Y %H:%M"), "toplam": top, "fark": fark if onceki else None,
           "instagram": {k: ig.get(k) for k in ("durum", "izin", "takipci", "hata", "gonderiler", "anahtar_izinleri")}, "hikaye_izin": hikaye_izin,
           "hikayeler": sorted(({"id": k, **v} for k, v in hikayeler.items()), key=lambda x: x.get("tarih", ""), reverse=True)[:40],
           "youtube": yt, "eksikler": eksikler, "bildirim": {"baslik": baslik, "govde": govde}}
    print(baslik)
    print(govde)
    if eksikler:
        print("Eksik:", "; ".join(eksikler), "| IG:", ig.get("hata", ""), "| YT:", yt.get("hata", ""))
    if ig.get("tani"):
        print("Anahtar tanısı:", json.dumps(ig["tani"], ensure_ascii=False))
    if ig.get("anahtar_izinleri") is not None:
        print("Instagram anahtarındaki izinler:", ", ".join(ig["anahtar_izinleri"]) or "(boş)")
    if a.kuru:
        return 0
    json_yaz(KLASOR / "son.json", son)
    json_yaz(KLASOR / "hikayeler.json", hikayeler)
    satirlar.append(satir)
    gecmis_yol.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in satirlar[-GECMIS_SINIR:]) + "\n", encoding="utf-8")
    if not json_oku(KLASOR / "ayar.json", None):
        json_yaz(KLASOR / "ayar.json", ayar)
    atla = ayar.get("artis_yoksa_atla") and not a.elle and onceki and fark == 0 and not eksikler
    if atla:
        print("Artış yok ve 'artış yoksa atla' açık: bildirim gönderilmedi.")
    else:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import hikaye as HK  # noqa: E402
        HK.bildir(baslik, govde, adres="/#ozet", etiket="istatistik")
    if a.git:
        depoya_it("İstatistikçi: izlenme raporu " + tr_saat(an).strftime("%d.%m %H:%M"))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--git", action="store_true", help="sonucu depoya yaz ve it")
    ap.add_argument("--elle", action="store_true", help="elle başlatma: duraklatma ve 'artış yoksa atla' kurallarını yok say")
    ap.add_argument("--kuru", action="store_true", help="yalnızca ekrana yaz; bildirim ve depo yazımı yok")
    sys.exit(calis(ap.parse_args()))


if __name__ == "__main__":
    main()
