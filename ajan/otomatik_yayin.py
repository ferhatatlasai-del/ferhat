#!/usr/bin/env python3
"""Otomatik üretim ve yayın hattı (yönetici ajan, Kademe 3).

Akış (günde 3 tur: sunucu TR 10:05, 15:05, 20:05'te tetikler):
  1. Ayar kontrolü: yonetici/ayar.json → aktif + kademe 3 + otomatik_yayin ("deneme" ya da "acik"). Günlük sınır (3) ve tur aralığı.
  2. Üretim: viral_video.py --otomatik (video depoya YAZILMAZ; yalnızca küçük kayıt dosyaları commit edilir).
  3. İnceleme: yönetici videoyu "izler" (kareler + anlatı + bilgi tabanı; video_inceleme.py). Reddederse yayınlanmaz, nedeni kaydedilir; bir kez daha farklı konuyla denenir.
  4. Yayın ("acik" modda): geçici dal (yayin-gecici, tek commit; sonra silinir) → Instagram Reels + Instagram Hikâye + YouTube Shorts + YouTube normal video (yatay, bulanık arka planlı).
     "deneme" modda yayınlanmaz; video geçici dalda önizleme olarak bırakılır.
  5. Kayıt: yonetici/otomatik.json, ilgili shorts/<id>.json; bildirim.
YouTube günlük yükleme kotası (10.000 puan, yükleme 1.600): günde en çok 6 yükleme, hat 3 video x 2 = 6 kullanır.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402
import video_inceleme as VI  # noqa: E402
import yonetici as Y  # noqa: E402

KOK = pathlib.Path(__file__).resolve().parent.parent
REPO = Y.REPO
GUNLUK_VIDEO = 3
YT_GUNLUK_YUKLEME = 6
YZ_SATIRI = "🤖 Doktor Filament yapay zekâ ile üretilmiş bir karakterdir."
DAL_ADI = "yayin-gecici"
LOG = "yonetici/otomatik.json"


def yz_ekle(metin):
    if YZ_SATIRI in metin:
        return metin
    satir = metin.split("\n")
    i = next((k for k, l in enumerate(satir) if l.strip().startswith("#")), -1)
    if i < 0:
        satir += ["", YZ_SATIRI]
    else:
        satir[i:i] = [YZ_SATIRI, ""]
    return "\n".join(satir)


def sh(komut, **k):
    return subprocess.run(komut, capture_output=True, text=True, **k)


def log_oku():
    v, _ = Y.dosya_oku(LOG)
    return (v or {}).get("kayitlar", [])


def log_yaz(kayit):
    def ekle(v):
        v.setdefault("kayitlar", []).append(kayit)
        v["kayitlar"] = v["kayitlar"][-60:]
    Y.json_guncelle(LOG, ekle, {"kayitlar": []}, "Otomatik hat: kayıt")


# ---------- geçici dal (depo şişmesin) ----------

def uzak_adres():
    return os.environ.get("GIT_UZAK_ADRES") or f"https://x-access-token:{os.environ.get('GITHUB_TOKEN', '')}@github.com/{REPO}.git"


def raw_taban():
    return os.environ.get("YAYIN_RAW_TABAN") or f"https://raw.githubusercontent.com/{REPO}/{DAL_ADI}"


def gecici_dala_yukle(dosyalar):
    """dosyalar: {depo_yolu: yerel_yol}. Tek commit'lik yetim dal olarak zorla yazılır (eski içerik geçmişte kalmaz). Dönen: dizin."""
    g = pathlib.Path(tempfile.mkdtemp())
    sh(["git", "-C", str(g), "init", "-q"])
    sh(["git", "-C", str(g), "config", "user.name", "yonetici-ajan"])
    sh(["git", "-C", str(g), "config", "user.email", "yonetici-ajan@users.noreply.github.com"])
    for yol, yerel in dosyalar.items():
        hedef = g / yol
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yerel, hedef)
    sh(["git", "-C", str(g), "add", "-A"])
    sh(["git", "-C", str(g), "commit", "-q", "-m", "geçici yayın dosyası"])
    p = sh(["git", "-C", str(g), "push", "-q", "-f", uzak_adres(), f"HEAD:refs/heads/{DAL_ADI}"])
    if p.returncode != 0:
        raise RuntimeError("geçici dala yazılamadı: " + (p.stderr or "")[-160:].replace(os.environ.get("GITHUB_TOKEN", "x"), "***"))
    return g


def gecici_dali_sil(g):
    try:
        sh(["git", "-C", str(g), "push", "-q", uzak_adres(), "--delete", DAL_ADI])
    except Exception:
        pass


def adres_hazir(url, sn=90):
    son = time.time() + sn
    while time.time() < son:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as y:
                if y.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(4)
    return False


# ---------- yatay (normal) video ----------

def yatay_yap(video, cikis):
    """Dikey videoyu 1920x1080 yatay çerçeveye, arkası bulanık olacak şekilde yerleştirir (YouTube bunu normal video sayar)."""
    f = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=30:6[bg];"
         "[b]scale=-2:1080:force_original_aspect_ratio=decrease[on];[bg][on]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    c = sh(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-filter_complex", f, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", "30",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(cikis)], timeout=900)
    if c.returncode != 0 or not pathlib.Path(cikis).exists():
        raise RuntimeError("yatay video üretilemedi: " + (c.stderr or "")[-160:])
    return cikis


# ---------- üretim ve inceleme ----------

def uret(g):
    """viral_video.py --otomatik ile bir video üretir; (sonuc_dict, plan_yolu) döndürür."""
    sonuc, plan = g / "sonuc.json", g / "plan.json"
    komut = [sys.executable, str(KOK / "ajan" / "viral_video.py"), "--git", "--otomatik", "--hemen", "--cikti", str(g / "video.mp4"), "--plan-kaydet", str(plan), "--sonuc-dosyasi", str(sonuc)]
    komut += os.environ.get("OTOMATIK_EK_ARG", "").split()   # test için (ör. --sessiz --olcek 0.5)
    print("Üretim başlıyor:", " ".join(komut[1:]))
    p = subprocess.run(komut, cwd=str(KOK))
    if p.returncode != 0 or not sonuc.exists() or not (g / "video.mp4").exists():
        raise RuntimeError(f"video üretilemedi (çıkış kodu {p.returncode})")
    return json.loads(sonuc.read_text(encoding="utf-8")), plan


def taslak_guncelle(kimlik, **alanlar):
    try:
        Y.json_guncelle(f"shorts/{kimlik}.json", lambda v: v.update(alanlar), {}, "Otomatik hat: taslak durumu")
    except Exception as e:
        print(f"UYARI: taslak güncellenemedi ({type(e).__name__})")


# ---------- yayın ----------

def komut_cikti(p):
    return (p.stdout or "") + "\n" + (p.stderr or "")


def yayinla(g, bilgi, ayar_kuru):
    """4 platforma yayın; her biri bağımsız (biri hata verse diğerleri sürer). Dönen: {anahtar: {durum, link, hata}}"""
    ad = bilgi["id"]
    video = g / "video.mp4"
    sure = bilgi["sure"]
    sonuc = {}
    # metinler
    ig_metin = yz_ekle(bilgi["aciklama"].strip())
    (g / "ig.txt").write_text(ig_metin + "\n", encoding="utf-8")
    baslik = re.sub(r"[<>]", "", bilgi["baslik"])[:100]
    yt_short = baslik + "\n" + (ig_metin if "#shorts" in ig_metin.lower() else ig_metin + "\n\n#Shorts") + "\n"
    (g / "yt_short.txt").write_text(yt_short, encoding="utf-8")
    yt_normal = baslik + "\n" + re.sub(r"#shorts\b", "", ig_metin, flags=re.I).strip() + "\n"
    (g / "yt_normal.txt").write_text(yt_normal, encoding="utf-8")
    yatay = None
    # geçici dal: Instagram videoyu herkese açık adresten indirir
    dal_dizin = None
    try:
        dal_dizin = gecici_dala_yukle({f"videolar/{ad}.mp4": video})
        url = f"{raw_taban()}/videolar/{ad}.mp4"
        if not ayar_kuru and not adres_hazir(url):
            raise RuntimeError("video adresi 90 sn içinde erişilebilir olmadı")
    except Exception as e:
        return {"hepsi": {"durum": "hata", "hata": f"geçici yayın dosyası: {e}"}}, None
    env = dict(os.environ)

    def calistir(ad_, komut, etiket, bekleme=1800):
        if ayar_kuru:
            print(f"[KURU] {ad_}: {etiket}")
            return {"durum": "kuru", "link": "", "hata": ""}
        try:
            p = sh(komut, env=env, timeout=bekleme)
            cikti = komut_cikti(p)
            m = re.search(r"(https://(?:www\.)?(?:instagram|youtube)\.com/[^\s]+)", cikti)
            if p.returncode != 0:
                son = [l for l in cikti.strip().splitlines() if l.strip()][-1:] or ["?"]
                return {"durum": "hata", "link": "", "hata": son[0][:200]}
            return {"durum": "ok", "link": m.group(1) if m else "", "hata": ""}
        except Exception as e:
            return {"durum": "hata", "link": "", "hata": f"{type(e).__name__}: {str(e)[:120]}"}

    sonuc["ig_reels"] = calistir("Instagram Reels", [sys.executable, str(KOK / "ajan" / "yayinla.py"), "--video-url", url, "--aciklama-dosyasi", str(g / "ig.txt"), "--yayinla"], "reels")
    # hikâye: en çok 60 sn
    if sure > 59.5:
        sonuc["ig_hikaye"] = {"durum": "atlandi", "link": "", "hata": f"video {sure:.0f} sn (hikâye en çok 60)"}
    elif ayar_kuru:
        sonuc["ig_hikaye"] = {"durum": "kuru", "link": "", "hata": ""}
    else:
        try:
            os.environ["HIKAYE_GORSEL_ADRESI"] = url
            medya, link = H.hikaye_yayinla({"tur": "video", "gorsel": f"videolar/{ad}.mp4"})
            sonuc["ig_hikaye"] = {"durum": "ok", "link": link or "", "hata": ""}
        except Exception as e:
            sonuc["ig_hikaye"] = {"durum": "hata", "link": "", "hata": f"{type(e).__name__}: {str(e)[:150]}"}
        finally:
            os.environ.pop("HIKAYE_GORSEL_ADRESI", None)
    yt_bugun = sum(2 if k.get("durum") == "yayinlandi" else 0 for k in log_oku() if str(k.get("zaman", ""))[:10] == Y.simdi_tr().strftime("%Y-%m-%d"))
    if yt_bugun + 2 > YT_GUNLUK_YUKLEME:
        for kk in ("yt_shorts", "yt_video"):
            sonuc[kk] = {"durum": "atlandi", "link": "", "hata": "YouTube günlük yükleme kotası dolmak üzere"}
    else:
        sonuc["yt_shorts"] = calistir("YouTube Shorts", [sys.executable, str(KOK / "ajan" / "youtube_yukle.py"), "--video", str(video), "--metin-dosyasi", str(g / "yt_short.txt"), "--gizlilik", "public", "--yukle"], "shorts")
        try:
            yatay = yatay_yap(video, g / "yatay.mp4")
            sonuc["yt_video"] = calistir("YouTube video", [sys.executable, str(KOK / "ajan" / "youtube_yukle.py"), "--video", str(yatay), "--metin-dosyasi", str(g / "yt_normal.txt"), "--gizlilik", "public", "--normal", "--yukle"], "normal video") if not ayar_kuru else {"durum": "kuru", "link": "", "hata": ""}
        except Exception as e:
            sonuc["yt_video"] = {"durum": "hata", "link": "", "hata": str(e)[:150]}
    return sonuc, dal_dizin


def calis(a):
    ayar, _ = Y.dosya_oku(Y.AYAR)
    ayar = {**Y.VARSAYILAN_AYAR, **(ayar or {})}
    mod = ayar.get("otomatik_yayin") or "kapali"
    if not (ayar["aktif"] and int(ayar.get("kademe") or 0) == 3 and mod in ("deneme", "acik")) and not a.elle:
        print(f"Otomatik hat çalışmıyor (aktif={ayar['aktif']}, kademe={ayar.get('kademe')}, mod={mod}); atlandı.")
        return 0
    bugun = Y.simdi_tr().strftime("%Y-%m-%d")
    kayitlar = log_oku()
    say = sum(1 for k in kayitlar if str(k.get("zaman", ""))[:10] == bugun and k.get("durum") in ("yayinlandi", "deneme"))
    if say >= GUNLUK_VIDEO and not a.elle:
        print(f"Bugün {say} video işlendi (sınır {GUNLUK_VIDEO}); atlandı.")
        return 0
    if kayitlar and not a.elle:
        try:
            son = datetime.datetime.strptime(kayitlar[-1]["zaman"], "%Y-%m-%d %H:%M")
            if (Y.simdi_tr().replace(tzinfo=None) - son).total_seconds() < 100 * 60:
                print("Son tur 100 dakikadan yakın; çift tetik olabilir, atlandı.")
                return 0
        except Exception:
            pass
    yonerge, bilgi_tabani = ayar.get("yonerge", ""), (KOK / "yonetici" / "bilgi.md").read_text(encoding="utf-8") if (KOK / "yonetici" / "bilgi.md").exists() else ""
    nk, _ = Y.dosya_oku("shorts/viral_noktalar.json")
    for deneme in range(2):
        g = pathlib.Path(tempfile.mkdtemp())
        try:
            bilgi, plan = uret(g)
        except Exception as e:
            print(f"HATA: {e}")
            log_yaz({"zaman": Y.simdi_tr().strftime("%Y-%m-%d %H:%M"), "durum": "hata", "ayrinti": str(e)[:200]})
            H.bildir("Otomatik video üretilemedi", str(e)[:100], adres="/#yonetici", etiket="yonetici")
            return 1
        onceki = [n for v in (nk or {}).get("videolar", []) for n in v.get("noktalar", [])]
        onceki = [n for n in onceki if n not in bilgi["noktalar"]]
        print(f"Video hazır ({bilgi['sure']:.0f} sn): {bilgi['baslik']}; yönetici izliyor…")
        try:
            inc = VI.incele(g / "video.mp4", bilgi, yonerge, bilgi_tabani, onceki)
        except Exception as e:
            inc = {"karar": "reddet", "puan": 0, "sorunlar": [f"inceleme yapılamadı: {type(e).__name__}: {str(e)[:100]}"], "gerekce": "inceleme çalışmadı (güvenli tarafta: yayınlanmadı)", "model": "-", "teknik": [], "olcum": {}}
        print(f"İnceleme: {inc['karar'].upper()} (puan {inc['puan']}) — {inc['gerekce']}")
        for s in inc["sorunlar"]:
            print("  -", s)
        ozet_inc = {k: inc.get(k) for k in ("karar", "puan", "sorunlar", "gerekce", "model", "iddialar")}
        zaman = Y.simdi_tr().strftime("%Y-%m-%d %H:%M")
        kayit = {"zaman": zaman, "id": bilgi["id"], "konu": bilgi["konu"], "baslik": bilgi["baslik"], "inceleme": ozet_inc, "mod": mod}
        if inc["karar"] != "yayinla":
            taslak_guncelle(bilgi["id"], durum="reddedildi", red_tarihi=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), admin_inceleme=ozet_inc)
            kayit.update(durum="reddedildi")
            log_yaz(kayit)
            H.bildir("Yönetici videoyu reddetti", f"{bilgi['baslik'][:60]}: {(inc['sorunlar'] or [inc['gerekce']])[0][:70]}", adres="/#yonetici", etiket="yonetici")
            if deneme == 0 and not a.elle:
                print("Farklı konuyla bir kez daha denenecek.")
                continue
            return 0
        if mod == "deneme":
            try:
                gd = gecici_dala_yukle({f"videolar/{bilgi['id']}.mp4": g / "video.mp4"})   # önizleme için dalda bırakılır (silinmez)
                onizleme = f"{raw_taban()}/videolar/{bilgi['id']}.mp4"
            except Exception as e:
                onizleme = ""
                print(f"UYARI: önizleme dalı yazılamadı: {e}")
            taslak_guncelle(bilgi["id"], durum="deneme", onizleme_url=onizleme, admin_inceleme=ozet_inc)
            kayit.update(durum="deneme", onizleme=onizleme)
            log_yaz(kayit)
            H.bildir("Deneme video hazır (yayınlanmadı)", f"{bilgi['baslik'][:70]} — yönetici onayladı (puan {inc['puan']}).", adres="/#yonetici", etiket="yonetici")
            return 0
        sonuc, dal = yayinla(g, bilgi, a.kuru)
        if dal:
            gecici_dali_sil(dal)
        basarili = [k for k, v in sonuc.items() if v.get("durum") in ("ok", "kuru")]
        hatali = {k: v.get("hata") for k, v in sonuc.items() if v.get("durum") == "hata"}
        taslak_guncelle(bilgi["id"], durum="yayinlandi" if basarili else "reddedildi", yayinlanan=[x for x, ok in (("instagram", "ig_reels"), ("youtube", "yt_shorts")) if sonuc.get(ok, {}).get("durum") in ("ok", "kuru")],
                        yayin_tarihi=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), hikaye_tarihi=(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if sonuc.get("ig_hikaye", {}).get("durum") in ("ok", "kuru") else None) or None,
                        linkler={k: v.get("link") for k, v in sonuc.items() if v.get("link")}, admin_inceleme=ozet_inc)
        kayit.update(durum="yayinlandi" if basarili else "hata", sonuc=sonuc)
        log_yaz(kayit)
        ozet = ", ".join(f"{k}:{v.get('durum')}" for k, v in sonuc.items())
        print("Yayın sonucu:", ozet)
        H.bildir("Otomatik video yayınlandı" if not hatali else "Otomatik yayında hata var", f"{bilgi['baslik'][:60]} — {ozet}"[:140], adres="/#yonetici", etiket="yonetici")
        return 0
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elle", action="store_true", help="ayar/sınır/aralık kontrolünü yok say (deneme)")
    ap.add_argument("--kuru", action="store_true", help="yayın komutlarını çalıştırma, yalnızca ne yapılacağını yaz")
    return calis(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
