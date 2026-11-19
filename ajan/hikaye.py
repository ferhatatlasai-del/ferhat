#!/usr/bin/env python3
"""Hikaye ajanı: kuyruktaki fotoğraf ve videoları, sahibinin belirlediği aralıkta Instagram hikayesi olarak yayınlar.

Veri (depoda):
  hikaye/ayar.json            aktif, günlük sayı, saat aralığı, günler, hata sınırı
  hikaye/kuyruk/<kimlik>.json her hikaye için kayıt (durum: onay_bekliyor, planli, yayinlaniyor, yayinda, hata, reddedildi)
  hikaye/gorseller/<kimlik>.jpg ya da .mp4  hazır 9:16 fotoğraf / video (video uygun değilse <kimlik>_hazir.mp4 üretilir)

Güvenlik:
  - Çift yayın olmasın diye önce "yayinlaniyor" işareti depoya yazılır (yazılamazsa yayınlanmaz), sonra yayınlanır.
  - Ardışık hata sınırı aşılırsa ajan kendini duraklatır ve bildirim gönderir.
  - Zamanlanmış çalışma ayarda aktif=false ise hiçbir şey yayınlamaz. Elle çalıştırmada --hemen bir tane yayınlar.
  - Hikaye API'si yazı, anket, bağlantı eklemez; yalnızca görsel gider.

Kullanım:
    python3 ajan/hikaye.py yayinla --kuru        # ne yapacağını yazar, yayınlamaz
    python3 ajan/hikaye.py yayinla --git         # zamanı geldiyse bir hikaye yayınlar, durumu depoya yazar
    python3 ajan/hikaye.py yayinla --hemen --git # aktif/saat denetimini atlar, sıradaki hikayeyi yayınlar
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
import time
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(os.environ.get("HIKAYE_KOK") or pathlib.Path(__file__).resolve().parent.parent)
API = os.environ.get("IG_API_ADRESI") or "https://graph.facebook.com/v21.0"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ig_ortak  # noqa: E402  (anahtar türüne göre adres ve hesap)
AYAR = KOK / "hikaye" / "ayar.json"
KUYRUK = KOK / "hikaye" / "kuyruk"
GORSELLER = KOK / "hikaye" / "gorseller"
MAKS_VIDEO_SN, MIN_VIDEO_SN = 60, 3
VARSAYILAN = {"aktif": False, "mod": "otomatik", "gunluk_sayi": 4, "baslangic_saat": 10, "bitis_saat": 22,
              "gunler": [1, 2, 3, 4, 5, 6, 7], "min_aralik_dk": 60, "ardisik_hata": 0, "hata_siniri": 3, "son_not": ""}
TR = datetime.timezone(datetime.timedelta(hours=3))   # Türkiye sabit UTC+3


def simdi():
    zaman = os.environ.get("HIKAYE_SIMDI")   # test için
    return datetime.datetime.fromisoformat(zaman) if zaman else datetime.datetime.now(datetime.timezone.utc)


def ayar_oku():
    a = dict(VARSAYILAN)
    if AYAR.exists():
        a.update(json.loads(AYAR.read_text(encoding="utf-8")))
    return a


def ayar_yaz(a):
    AYAR.parent.mkdir(parents=True, exist_ok=True)
    AYAR.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")


def kuyruk_oku():
    ogeler = []
    for yol in sorted(KUYRUK.glob("h*.json")):
        try:
            o = json.loads(yol.read_text(encoding="utf-8"))
            o["_yol"] = yol
            ogeler.append(o)
        except Exception:
            pass
    return ogeler


def oge_yaz(o):
    yol = o.pop("_yol")
    yol.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    o["_yol"] = yol


def tr_zaman(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TR)


def bugun_yayinlananlar(ogeler, an):
    bugun = an.astimezone(TR).date()
    return [o for o in ogeler if o.get("durum") in ("yayinda", "yayinlaniyor") and (o.get("yayin") or {}).get("tarih")
            and tr_zaman(o["yayin"]["tarih"]).date() == bugun]


def karar(ayar, ogeler, an, hemen=False, kimlik=None):
    """(yayinlanacak_mi, neden, secilen_oge). Saat dilimi: Türkiye."""
    sirada = sorted([o for o in ogeler if o.get("durum") == "planli"], key=lambda o: o.get("olusturma", ""))
    if kimlik:   # belirli bir hikayeyi hemen yayınla (ör. panelden "aynı anda yayınla")
        secilen = [o for o in sirada if o.get("id") == kimlik]
        return (True, f"{kimlik} elle istendi", secilen[0]) if secilen else (False, f"{kimlik} bulunamadı ya da planlı değil", None)
    if hemen:
        return (True, "elle istendi", sirada[0]) if sirada else (False, "kuyrukta planlı hikaye yok", None)
    if not ayar["aktif"]:
        return False, "ajan duraklatılmış (aktif=false)", None
    yerel = an.astimezone(TR)
    if yerel.isoweekday() not in ayar["gunler"]:
        return False, f"bugün ({yerel.isoweekday()}. gün) yayın günü değil", None
    n = max(1, int(ayar["gunluk_sayi"]))
    bas, bit = float(ayar["baslangic_saat"]), float(ayar["bitis_saat"])
    if bit <= bas:
        return False, "saat aralığı geçersiz (bitiş başlangıçtan büyük olmalı)", None
    saat = yerel.hour + yerel.minute / 60
    slotlar = [bas + i * (bit - bas) / n for i in range(n)]
    gelen = sum(1 for s in slotlar if saat >= s)
    if saat > bit + 0.5 or gelen == 0:
        return False, f"şu an ({yerel:%H:%M}) yayın aralığı dışında ({bas:g}:00-{bit:g}:00)", None
    bugun = bugun_yayinlananlar(ogeler, an)
    if len(bugun) >= gelen:
        return False, f"bugün {len(bugun)} hikaye yayınlandı, şu ana kadar {gelen} slot geldi; sıradaki slot bekleniyor", None
    if bugun:
        son = max(tr_zaman(o["yayin"]["tarih"]) for o in bugun)
        gecen = (yerel - son).total_seconds() / 60
        # Alt sınır slot aralığından büyük olamaz: yoksa kontrol saatindeki küçük gecikmeler bir sonraki slotu kaçırtır
        # ve gün sonunda ayarlanan sayıya ulaşılamaz. Slot aralığının %60'ı ile ayardaki en düşük değer kullanılır.
        slot_dk = (bit - bas) * 60 / n
        alt_sinir = min(float(ayar["min_aralik_dk"]), 0.6 * slot_dk)
        if gecen < alt_sinir:
            return False, f"son hikayeden {gecen:.0f} dk geçti, en az {alt_sinir:.0f} dk gerekir", None
    if not sirada:
        return False, "kuyrukta planlı hikaye yok (kuyruk boş)", None
    return True, f"slot {gelen}/{n} geldi, {len(bugun)} yayınlandı", sirada[0]


# ---------- Git ----------

def git(*arglar, kontrol=True):
    return subprocess.run(["git", "-C", str(KOK), *arglar], capture_output=True, text=True, check=kontrol)


def git_kaydet(mesaj, yollar, deneme=4):
    """Değişiklikleri commit'le ve it. Çakışmada çek-ve-yeniden-dene. Başarısızsa False."""
    git("config", "user.name", "hikaye-ajani")
    git("config", "user.email", "hikaye-ajani@users.noreply.github.com")
    git("add", "-A", "--", *[str(y) for y in yollar])
    if git("diff", "--cached", "--quiet", kontrol=False).returncode == 0:
        return True
    git("commit", "-q", "-m", mesaj)
    for i in range(deneme):
        git("pull", "--rebase", "-q", kontrol=False)
        if git("push", "-q", kontrol=False).returncode == 0:
            return True
        time.sleep(2 + i * 2)
    return False


# ---------- Instagram ----------

def api(yontem, yol, **parametre):
    parametre["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    govde = urllib.parse.urlencode(parametre)
    taban = ig_ortak.api_adresi()
    if yontem == "GET":
        istek = urllib.request.Request(f"{taban}/{yol}?{govde}")
    else:
        istek = urllib.request.Request(f"{taban}/{yol}", data=govde.encode(), method="POST")
    with urllib.request.urlopen(istek, timeout=120) as y:
        return json.load(y)


def hata_ozeti(e):
    try:
        h = json.loads(e.read().decode("utf-8")).get("error", {})
        return f"HTTP {e.code} kod={h.get('code')} alt={h.get('error_subcode')}: {str(h.get('message'))[:260]}"
    except Exception:
        return f"HTTP {e.code}"


def ffmpeg_hazir():
    """ffprobe/ffmpeg yoksa (GitHub çalıştırıcısında hazır gelmeyebilir) yalnızca gerektiğinde kur."""
    if shutil.which("ffprobe") and shutil.which("ffmpeg"):
        return
    if os.environ.get("GITHUB_ACTIONS"):
        print("ffmpeg kuruluyor…")
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, capture_output=True, text=True)
    if not (shutil.which("ffprobe") and shutil.which("ffmpeg")):
        raise RuntimeError("ffmpeg/ffprobe yüklü değil, video denetlenemedi")


class IcerikHatasi(Exception):
    """Videonun kendisinden kaynaklanan sorun (anahtar/servis sorunu değil); ardışık hata sayılmaz."""


def video_bilgi(yol):
    ffmpeg_hazir()
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                        "-of", "json", str(yol)], capture_output=True, text=True)
    if r.returncode != 0:
        raise IcerikHatasi("video dosyası okunamadı (bozuk ya da desteklenmeyen biçim)")
    j = json.loads(r.stdout or "{}")
    v = next((x for x in j.get("streams", []) if x.get("codec_type") == "video"), None)
    a = next((x for x in j.get("streams", []) if x.get("codec_type") == "audio"), None)
    if not v:
        raise IcerikHatasi("dosyada görüntü yok")
    return {"g": int(v.get("width", 0)), "y": int(v.get("height", 0)), "kodek": v.get("codec_name"),
            "ses": a.get("codec_name") if a else None, "sure": float(j.get("format", {}).get("duration") or 0)}


def video_uygun_mu(b):
    """Instagram hikayesi için olduğu gibi kullanılabilir mi? (dikey 9:16, H.264, ses yoksa ya da AAC, 3-60 sn)"""
    return (b["y"] > 0 and abs(b["g"] / b["y"] - 9 / 16) < 0.015 and b["g"] >= 540 and b["kodek"] == "h264"
            and b["ses"] in (None, "aac"))


def video_hazirla(o):
    """Videoyu denetler. Uygunsa dokunmaz (None döner); değilse 1080x1920 H.264/AAC'ye çevirir ve yeni yolu döndürür."""
    kaynak = KOK / o["gorsel"]
    b = video_bilgi(kaynak)
    if b["sure"] > MAKS_VIDEO_SN + 0.5:
        raise IcerikHatasi(f"video {b['sure']:.0f} sn; hikaye videosu en fazla {MAKS_VIDEO_SN} sn olabilir")
    if b["sure"] < MIN_VIDEO_SN:
        raise IcerikHatasi(f"video {b['sure']:.1f} sn; hikaye videosu en az {MIN_VIDEO_SN} sn olmalı")
    if video_uygun_mu(b):
        print(f"Video hikayeye uygun ({b['g']}x{b['y']}, {b['sure']:.0f} sn); olduğu gibi kullanılacak.")
        return None
    cikti = GORSELLER / f"{o['id']}_hazir.mp4"
    filtre = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:6,eq=brightness=-0.18[bg];"
              "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    komut = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(kaynak), "-filter_complex", filtre, "-map", "[v]"]
    komut += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"] if b["ses"] else ["-an"]
    komut += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-r", "30", "-movflags", "+faststart", "-t", str(MAKS_VIDEO_SN), str(cikti)]
    r = subprocess.run(komut, capture_output=True, text=True)
    if r.returncode != 0 or not cikti.exists():
        raise IcerikHatasi("video dönüştürülemedi: " + (r.stderr or "")[-160:])
    print(f"Video hikaye biçimine çevrildi: {b['g']}x{b['y']} -> 1080x1920 ({cikti.stat().st_size // 1024} KB).")
    return str(cikti.relative_to(KOK))


def adres_hazir_mi(adres, sn=90):
    """Yeni itilen dosya raw adresinde görünene kadar bekle (Instagram'ın indirebilmesi için)."""
    bitis = time.time() + sn
    while True:
        try:
            istek = urllib.request.Request(adres, headers={"Range": "bytes=0-0"})
            with urllib.request.urlopen(istek, timeout=20) as y:
                if y.status in (200, 206):
                    return True
        except Exception:
            pass
        if time.time() > bitis:
            return False
        time.sleep(5)


def gorsel_adresi(o):
    """Instagram'ın indirebileceği, görseli içeren commit'e sabitlenmiş adres."""
    depo = os.environ.get("GITHUB_REPOSITORY", "")
    yol = o.get("hazir") or o["gorsel"]
    sha = git("log", "-n1", "--format=%H", "--", yol, kontrol=False).stdout.strip() or os.environ.get("GITHUB_SHA", "main")
    return os.environ.get("HIKAYE_GORSEL_ADRESI") or f"https://raw.githubusercontent.com/{depo}/{sha}/{yol}"


def hikaye_yayinla(o):
    """Görseli hikaye olarak yayınlar. (medya_kimligi, link) döndürür."""
    kimlik = ig_ortak.kimlik()
    video = o.get("tur") == "video"
    adres = gorsel_adresi(o)
    if not os.environ.get("HIKAYE_GORSEL_ADRESI") and not adres_hazir_mi(adres):
        raise RuntimeError("Dosya adresi 90 sn içinde erişilebilir olmadı")
    anahtar = "video_url" if video else "image_url"
    kap = api("POST", f"{kimlik}/media", media_type="STORIES", **{anahtar: adres})["id"]
    deneme, aralik = (36, 10) if video else (12, 5)   # video işleme birkaç dakika sürebilir
    for _ in range(deneme):
        veri = api("GET", kap, fields="status_code,status")
        durum = veri.get("status_code", "FINISHED")
        if durum == "FINISHED":
            break
        if durum in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram {'videoyu' if video else 'görseli'} işleyemedi ({durum}: {str(veri.get('status', ''))[:120]})")
        time.sleep(aralik)
    else:
        raise RuntimeError("Instagram medyayı zamanında işleyemedi")
    medya = api("POST", f"{kimlik}/media_publish", creation_id=kap)["id"]
    link = ""
    try:
        link = api("GET", medya, fields="permalink").get("permalink", "")
    except urllib.error.HTTPError:
        pass
    return medya, link


# ---------- Bildirim ----------

def bildir(baslik, govde, gorsel="", adres="", etiket="hikaye"):
    """Sunucuya web push gönderme isteği (anahtarlar yoksa ya da başarısızsa sessizce geçer; yayını bozmaz)."""
    ofis, sir = os.environ.get("OFIS_ADRES"), os.environ.get("BILDIRIM_SIRRI")
    if not (ofis and sir):
        print("Bildirim atlandı (OFIS_ADRES ya da BILDIRIM_SIRRI tanımlı değil).")
        return
    try:
        istek = urllib.request.Request(ofis.rstrip("/") + "/api/bildir", method="POST",
                                       data=json.dumps({"baslik": baslik, "govde": govde, "gorsel": gorsel, "adres": adres, "etiket": etiket}).encode(),
                                       headers={"Content-Type": "application/json", "X-Bildirim": sir})
        with urllib.request.urlopen(istek, timeout=40) as y:
            print("Bildirim gönderildi:", y.read().decode()[:120])
    except Exception as e:
        print(f"Bildirim gönderilemedi: {type(e).__name__}")


# ---------- Ana akış ----------

def sistem_hatasi(ayar, oge, ozet, a):
    """Anahtar/servis/altyapı sorunu: hikaye sıraya geri döner (5 denemeye kadar), ardışık hata sayılır, sınırda ajan duraklar."""
    oge["deneme"] = oge.get("deneme", 0) + 1
    oge["durum"], oge["hata"], oge["yayin"] = ("planli" if oge["deneme"] < 5 else "hata"), ozet, None
    oge_yaz(oge)
    ayar["ardisik_hata"] = ayar.get("ardisik_hata", 0) + 1
    durdu = ayar["ardisik_hata"] >= ayar["hata_siniri"]
    if durdu:
        ayar["aktif"], ayar["son_not"] = False, f"{ayar['ardisik_hata']} ardışık hata nedeniyle otomatik duraklatıldı"
    ayar_yaz(ayar)
    if a.git:
        git_kaydet(f"Hikaye: {oge['id']} hata", [KUYRUK, AYAR])
    bildir("Hikaye yayınlanamadı" + (" ve ajan duraklatıldı" if durdu else ""), ozet[:160], adres="/")
    return 1


def yayinla_komutu(a):
    ayar = ayar_oku()
    ogeler = kuyruk_oku()
    an = simdi()
    yay, neden, oge = karar(ayar, ogeler, an, a.hemen, a.kimlik)
    print(f"Karar: {'YAYINLA' if yay else 'bekle'} ({neden})")
    if not yay or a.kuru:
        return 0
    for gerekli in ("IG_ACCESS_TOKEN", "IG_USER_ID"):
        if not os.environ.get(gerekli):
            print(f"{gerekli} tanımlı değil.")
            return 1
    if not (KOK / oge["gorsel"]).exists():
        oge["durum"], oge["hata"] = "hata", "görsel dosyası bulunamadı"
        oge_yaz(oge)
        if a.git:
            git_kaydet(f"Hikaye: {oge['id']} görseli yok", [KUYRUK])
        return 1

    # 0) Video ise denetle/gerekirse dönüştür (içerik sorunu ajanı duraklatmaz, yalnızca o hikaye "hata" olur)
    if oge.get("tur") == "video":
        try:
            hazir = video_hazirla(oge)
            if hazir:
                oge["hazir"] = hazir
        except IcerikHatasi as e:
            print(f"Video hikaye reddedildi: {e}")
            oge["durum"], oge["hata"] = "hata", str(e)[:200]
            oge_yaz(oge)
            if a.git:
                git_kaydet(f"Hikaye: {oge['id']} video uygun değil", [KUYRUK])
            bildir("Video hikayesi yayınlanamadı", str(e)[:160], adres="/")
            return 1
        except Exception as e:   # ffmpeg yok, dosya okunamadı vb.: altyapı sorunu, ardışık hata sayılır
            ozet = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"Video hazırlanamadı: {ozet}")
            oge.pop("hazir", None)
            return sistem_hatasi(ayar, oge, ozet, a)

    # 1) Önce "yayınlanıyor" işaretini depoya yaz; yazılamazsa çift yayın riski olduğu için yayınlama
    oge["durum"] = "yayinlaniyor"
    oge["yayin"] = {"tarih": an.strftime("%Y-%m-%dT%H:%M:%SZ")}
    oge_yaz(oge)
    if a.git and not git_kaydet(f"Hikaye: {oge['id']} yayınlanıyor", [KUYRUK, GORSELLER]):
        print("Durum işareti depoya yazılamadı; çift yayını önlemek için yayınlanmadı.")
        return 1

    # 2) Yayınla
    try:
        medya, link = hikaye_yayinla(oge)
    except Exception as e:
        ozet = hata_ozeti(e) if isinstance(e, urllib.error.HTTPError) else f"{type(e).__name__}: {str(e)[:200]}"
        print(f"Instagram hikaye hatası: {ozet}")
        return sistem_hatasi(ayar, oge, ozet, a)

    # 3) Sonucu yaz
    oge["durum"], oge["hata"] = "yayinda", ""
    oge["yayin"] = {"tarih": simdi().strftime("%Y-%m-%dT%H:%M:%SZ"), "medya_kimligi": medya, "link": link}
    oge_yaz(oge)
    ayar["ardisik_hata"] = 0
    ayar_yaz(ayar)
    if a.git and not git_kaydet(f"Hikaye: {oge['id']} yayında", [KUYRUK, AYAR]):
        print("UYARI: yayın sonrası durum depoya yazılamadı; yayınlaniyor işareti kalır (çift yayını önler).")
    print(f"YAYINLANDI. Medya kimliği: {medya}  Bağlantı: {link}")
    if oge.get("tur") == "video":
        bildir("Video hikayesi yayınlandı", oge.get("baslik") or "Yeni video hikayesi", adres=link or "https://www.instagram.com/")
    else:
        bildir("Hikaye yayınlandı", oge.get("baslik") or "Yeni hikaye", gorsel=gorsel_adresi(oge), adres=link or "https://www.instagram.com/")
    return 0


def main():
    ap = argparse.ArgumentParser()
    alt = ap.add_subparsers(dest="komut", required=True)
    y = alt.add_parser("yayinla")
    y.add_argument("--kuru", action="store_true", help="Yalnızca karar ver, yayınlama")
    y.add_argument("--hemen", action="store_true", help="Aktif/saat/slot denetimini atla (elle)")
    y.add_argument("--git", action="store_true", help="Durumu depoya yaz ve it")
    y.add_argument("--kimlik", help="Yalnızca bu hikayeyi hemen yayınla (sıradaki yerine)")
    a = ap.parse_args()
    if a.kimlik and not re.fullmatch(r"h\d{8}-\d{6}-[a-z0-9]{3}", a.kimlik):
        sys.exit("Geçersiz hikaye kimliği.")
    sys.exit(yayinla_komutu(a))


if __name__ == "__main__":
    main()
