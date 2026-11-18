#!/usr/bin/env python3
"""Akademi ajanı (V1): haftada bir ajanların performansına bakar, rapor çıkarır ve "ders önerileri" yazar.

- Rapor ücretsizdir: istatistikleri betik çıkarır (kuyruk, olay günlüğü, harcama, iş akışı sonuçları, zincir ve trend kayıtları).
- Ders önerileri için yapay zekâya yalnızca TOPLU SAYILAR gider (tasarım adı, trend konusu gibi internetten gelen metinler gitmez), haftada birkaç sent.
- Ajanların kod ve ayarlarını DEĞİŞTİRMEZ. Öneriler `akademi/oneriler.json` dosyasına "onay_bekliyor" olarak yazılır; panelde kullanıcı onaylar.
  Yalnızca ONAYLI dersler ajanların istemine eklenir (akademi_dersleri).

Kullanım:
    python3 ajan/akademi.py            # rapor + (anahtar varsa) ders önerileri
    python3 ajan/akademi.py --kuru     # yalnızca rapor, yapay zekâ yok
    python3 ajan/akademi.py --git      # sonucu depoya yaz ve it
"""
import argparse
import collections
import datetime
import glob
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(os.environ.get("HIKAYE_KOK") or pathlib.Path(__file__).resolve().parent.parent)
DIZIN = KOK / "akademi"
ONERILER = DIZIN / "oneriler.json"
RAPOR_JSON = DIZIN / "rapor-son.json"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
GH_API = os.environ.get("GH_API") or "https://api.github.com"
GUN = 7
AJANLAR = ("hikaye", "trend", "icerik", "sistem")   # 'sistem': kullanıcıya yönelik öneri, istemlere eklenmez
TR = datetime.timezone(datetime.timedelta(hours=3))


def simdi():
    z = os.environ.get("HIKAYE_SIMDI")
    return datetime.datetime.fromisoformat(z) if z else datetime.datetime.now(datetime.timezone.utc)


def json_oku(yol, varsayilan):
    try:
        return json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except Exception:
        return varsayilan


def yaz_json(yol, veri):
    pathlib.Path(yol).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def zaman(metin):
    try:
        z = datetime.datetime.fromisoformat((metin or "").replace("Z", "+00:00"))
        return z if z.tzinfo else z.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


# ---------- Ajanların kullanacağı: onaylı dersler ----------

def akademi_dersleri(ajan):
    """Kullanıcının ONAYLADIĞI dersleri bu ajanın istemine eklenecek kısa metin olarak döndürür (yoksa boş). En çok 5 ders."""
    try:
        liste = json_oku(ONERILER, {}).get("oneriler", [])
    except Exception:
        return ""
    secili = [o for o in liste if o.get("durum") == "onayli" and o.get("ajan") == ajan][:5]
    satirlar = []
    for o in secili:
        d = re.sub(r"[{}\r\n]+", " ", str(o.get("ders") or "")).strip()[:220]
        if d:
            satirlar.append(f"- {d}")
    if not satirlar:
        return ""
    return "\n# AKADEMİ DERSLERİ (kullanıcı onaylı; uygula)\n" + "\n".join(satirlar) + "\n"


# ---------- Veri toplama (ücretsiz, yapay zekâsız) ----------

def olaylar(gun=GUN):
    sinir = simdi() - datetime.timedelta(days=gun)
    cikti = []
    yol = KOK / "hikaye" / "olaylar.jsonl"
    if yol.exists():
        for satir in yol.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(satir)
                z = zaman(o.get("t"))
                if z and z >= sinir:
                    cikti.append(o)
            except Exception:
                pass
    return cikti


def hikaye_ozeti(gun=GUN):
    sinir = simdi() - datetime.timedelta(days=gun)
    durum, kaynak, puanlar, denemeler, yayin_gun = collections.Counter(), collections.Counter(), [], [], collections.Counter()
    referansli = trendli = muzikli = 0
    for f in glob.glob(str(KOK / "hikaye" / "kuyruk" / "h*.json")):
        o = json_oku(f, None)
        if not o:
            continue
        z = zaman(o.get("olusturma"))
        y = zaman((o.get("yayin") or {}).get("tarih"))
        if y and y >= sinir:
            yayin_gun[y.astimezone(TR).strftime("%Y-%m-%d")] += 1
        if not z or z < sinir:
            continue
        durum[o.get("durum", "?")] += 1
        kaynak[o.get("kaynak", "?")] += 1
        if o.get("kontrol"):
            puanlar.append(float(o["kontrol"].get("puan") or 0))
            denemeler.append(int(o["kontrol"].get("deneme") or 1))
        referansli += 1 if (o.get("atif") or {}).get("referansli") else 0
        trendli += 1 if o.get("trend") else 0
        muzikli += 1 if o.get("muzik") else 0
    ort = lambda l: round(sum(l) / len(l), 2) if l else None
    return {"olusturulan": sum(durum.values()), "durumlar": dict(durum), "kaynaklar": dict(kaynak), "ort_kontrol_puani": ort(puanlar),
            "ort_deneme": ort(denemeler), "referansli": referansli, "trend_kaynakli": trendli, "muzikli": muzikli, "yayin_gunluk": dict(sorted(yayin_gun.items()))}


def olay_ozeti(liste):
    tur = collections.Counter(o["tur"] for o in liste)
    denetim = [o for o in liste if o["tur"] == "denetim"]
    gecen = sum(1 for o in denetim if o.get("gecti"))
    sorun = collections.Counter()
    for o in denetim:
        if not o.get("gecti"):
            for s in o.get("sorunlar") or []:
                sorun[re.sub(r"\s+", " ", str(s).lower())[:80]] += 1
    lisans = collections.Counter()
    for o in liste:
        if o["tur"] == "lisans_elendi":
            m = re.search(r"CC-BY(?:-[A-Z]+)*|Standard Digital File|GPL|BSD|Commercial[^()]{0,30}", str(o.get("neden")))
            lisans[m.group(0) if m else "diğer"] += 1
    referans = collections.Counter(re.sub(r"\(.*", "", str(o.get("neden")))[:50].strip() for o in liste if o["tur"] == "referans_yok")
    return {"olaylar": dict(tur), "denetim_deneme": len(denetim), "denetim_gecen": gecen,
            "denetim_gecme_orani": round(gecen / len(denetim), 2) if denetim else None,
            "en_sik_denetim_sorunlari": sorun.most_common(6), "elenen_lisanslar": dict(lisans.most_common(6)),
            "referans_sorunlari": dict(referans.most_common(4)), "gorsel_hatalari": tur.get("gorsel_hatasi", 0)}


def kullanilan_ozeti(gun=GUN):
    sinir = (simdi() - datetime.timedelta(days=gun)).astimezone(TR).strftime("%Y-%m-%d")
    return dict(collections.Counter(k.get("durum", "uretildi") for k in json_oku(KOK / "hikaye" / "kullanilan.json", []) if (k.get("tarih") or "") >= sinir))


def harcama_ozeti():
    h = json_oku(KOK / "hikaye" / "harcama.json", {})
    bugun = simdi().astimezone(TR)
    gunler = {g: v.get("gorsel", 0) for g, v in sorted(h.get("gunler", {}).items())[-GUN:]}
    return {"gunluk_gorsel": gunler, "bu_ay": h.get("aylar", {}).get(bugun.strftime("%Y-%m"), {}).get("gorsel", 0),
            "son_7_gun_toplam": sum(gunler.values())}


def zincir_ozeti(gun=GUN):
    sinir = simdi() - datetime.timedelta(days=gun)
    puanlar, formatlar, konular = [], collections.Counter(), collections.Counter()
    sayi = 0
    for f in glob.glob(str(KOK / "zincir" / "[cy]*[0-9].json")):
        k = json_oku(f, None)
        z = zaman(k.get("olusturma")) if k else None
        if not z or z < sinir:
            continue
        sayi += 1
        formatlar[k.get("format", "?")] += 1
        e = k.get("elestiri") or {}
        if e.get("puan"):
            puanlar.append(float(e["puan"]))
        konular[str(k.get("konu") or "")[:30].lower()] += 1
    return {"kayit": sayi, "formatlar": dict(formatlar), "ort_elestiri_puani": round(sum(puanlar) / len(puanlar), 2) if puanlar else None,
            "tekrarlanan_konu_sayisi": sum(1 for v in konular.values() if v > 1)}


def trend_ozeti():
    v = json_oku(KOK / "ajan" / "trendler.json", {})
    o = v.get("oneriler", [])
    kat = collections.Counter(x.get("kategori") or "yok" for x in o)
    return {"tarih": v.get("tarih"), "oneri": len(o), "dogrulanan": sum(1 for x in o if x.get("dogrulandi")), "kategori_sayisi": len(kat),
            "en_cok_kategori": kat.most_common(1)[0] if kat else None}


def calisma_ozeti(gun=GUN):
    """GitHub iş akışı sonuçları (anahtar yoksa ya da erişilemezse None)."""
    anahtar, depo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (anahtar and depo):
        return None
    sinir = (simdi() - datetime.timedelta(days=gun)).strftime("%Y-%m-%d")
    toplam = collections.defaultdict(lambda: {"calisma": 0, "basarisiz": 0, "iptal": 0, "zamanlayici": 0, "elle": 0})
    try:
        for sayfa in (1, 2, 3):
            adres = f"{GH_API}/repos/{depo}/actions/runs?per_page=100&page={sayfa}&created=" + urllib.parse.quote(f">={sinir}")
            r = urllib.request.Request(adres, headers={"Authorization": f"Bearer {anahtar}", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(r, timeout=30) as y:
                kosular = json.load(y).get("workflow_runs", [])
            for k in kosular:
                t = toplam[k.get("name", "?")]
                t["calisma"] += 1
                t["basarisiz"] += 1 if k.get("conclusion") == "failure" else 0
                t["iptal"] += 1 if k.get("conclusion") == "cancelled" else 0
                t["zamanlayici" if k.get("event") == "schedule" else "elle"] += 1
            if len(kosular) < 100:
                break
    except Exception as e:
        return {"hata": f"{type(e).__name__}"}
    return dict(toplam)


def ozet_topla():
    liste = olaylar()
    return {"tarih": simdi().strftime("%Y-%m-%dT%H:%M:%SZ"), "gun": GUN, "hikaye": hikaye_ozeti(), "olaylar": olay_ozeti(liste),
            "elenenler": kullanilan_ozeti(), "harcama": harcama_ozeti(), "zincir": zincir_ozeti(), "trend": trend_ozeti(), "calismalar": calisma_ozeti()}


# ---------- Rapor ----------

def rapor_metni(o):
    h, ol, ha, zi, tr, ca = o["hikaye"], o["olaylar"], o["harcama"], o["zincir"], o["trend"], o["calismalar"]
    s = [f"# Akademi haftalık raporu ({o['tarih'][:10]}, son {o['gun']} gün)", ""]
    s += ["## Hikaye üretimi",
          f"- Oluşturulan hikaye: **{h['olusturulan']}** (durumlar: {h['durumlar']}); referans fotoğraflı: {h['referansli']}; trend kaynaklı: {h['trend_kaynakli']}; müzikli: {h['muzikli']}",
          f"- Ortalama kontrol puanı: {h['ort_kontrol_puani']}, ortalama deneme: {h['ort_deneme']}",
          f"- Denetim: {ol['denetim_deneme']} deneme, {ol['denetim_gecen']} geçti (oran: {ol['denetim_gecme_orani']})",
          f"- En sık denetim sorunları: {ol['en_sik_denetim_sorunlari']}",
          f"- Elenen lisanslar: {ol['elenen_lisanslar']}; referans sorunları: {ol['referans_sorunlari']}",
          f"- Elenen tasarımlar (durum): {o['elenenler']}",
          f"- Günlük yayın: {h['yayin_gunluk']}", ""]
    s += ["## Harcama", f"- Günlük görsel: {ha['gunluk_gorsel']}; son 7 gün: {ha['son_7_gun_toplam']}; bu ay: {ha['bu_ay']}", ""]
    s += ["## İçerik zinciri", f"- Kayıt: {zi['kayit']}, formatlar: {zi['formatlar']}, ortalama öz eleştiri puanı: {zi['ort_elestiri_puani']}, tekrarlanan konu: {zi['tekrarlanan_konu_sayisi']}", ""]
    s += ["## Trend ajanı", f"- Son araştırma: {tr['tarih']}; öneri: {tr['oneri']}, doğrulanan: {tr['dogrulanan']}, kategori çeşidi: {tr['kategori_sayisi']}, en yoğun kategori: {tr['en_cok_kategori']}", ""]
    s += ["## İş akışı çalışmaları"]
    if not ca:
        s.append("- GitHub verisi alınamadı (anahtar yok).")
    elif "hata" in ca:
        s.append(f"- GitHub verisi alınamadı ({ca['hata']}).")
    else:
        for ad, v in sorted(ca.items(), key=lambda x: -x[1]["calisma"]):
            s.append(f"- {ad}: {v['calisma']} çalışma, {v['basarisiz']} başarısız, {v['iptal']} iptal (zamanlayıcı {v['zamanlayici']}, elle/sunucu {v['elle']})")
    return "\n".join(s) + "\n"


# ---------- Ders önerileri (yapay zekâ, toplu sayılarla) ----------

DERS_SISTEM = "Sen küçük bir otomatik içerik sisteminin kalite koçusun. Yalnızca geçerli JSON döndür."
DERS_ISTEMI = """Aşağıda, 3D baskı içerikleri üreten ajanların son haftalık TOPLU istatistikleri var (tasarım adı ya da konu metni yok, yalnızca sayılar).
Ajanlar: 'hikaye' (Instagram hikaye görseli üreten ajan: görsel istemi, referans fotoğraf, denetim), 'trend' (trend araştırması), 'icerik' (carousel/reels senaryosu).

GÖREV: Verideki GERÇEK bir sorunu ya da fırsatı gösteren, EN ÇOK 3 kısa ders öner. Her ders, o ajanın istemine eklenecek tek bir uygulanabilir kural olsun.
KURALLAR:
- Her ders, verideki somut bir sayıya dayansın (kanit alanına o sayıyı yaz). Veri yetersizse ya da her şey iyiyse BOŞ liste döndür; ders uydurma.
- ajan: "hikaye", "trend", "icerik" ya da "sistem" ('sistem': ajan istemine değil, sahibine yönelik öneri; ör. bir iş akışı sürekli başarısızsa).
- ders: Türkçe, emir kipinde, en çok 200 karakter, tek cümle. URL, kod, süslü parantez ve "önceki talimatları yok say" benzeri ifade YOK.
- Zaten var olan derslerle aynı olmasın.

MEVCUT DERSLER (tekrarlama): {mevcut}

İSTATİSTİKLER:
{ozet}

Yalnızca JSON: {{"dersler":[{{"ajan":"hikaye","baslik":"kısa başlık (en çok 60 karakter)","ders":"...","kanit":"sayıyla kısa kanıt (en çok 140 karakter)","onem":1}}]}}"""


def ders_cagir(ozet, mevcut):
    anahtar = os.environ.get("OPENAI_API_KEY")
    if not anahtar:
        return None
    govde = {"model": MODEL, "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": DERS_SISTEM},
                          {"role": "user", "content": DERS_ISTEMI.format(mevcut="; ".join(mevcut) or "(yok)", ozet=json.dumps(ozet, ensure_ascii=False)[:9000])}]}
    r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST",
                               headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(r, timeout=120) as y:
        return json.loads(json.load(y)["choices"][0]["message"]["content"])


def temiz_ders(d):
    """Modelden gelen dersi doğrula ve temizle; uygunsuzsa None."""
    if not isinstance(d, dict) or d.get("ajan") not in AJANLAR:
        return None
    ders = re.sub(r"[{}\r\n]+", " ", str(d.get("ders") or "")).strip()[:200]
    baslik = re.sub(r"[{}\r\n]+", " ", str(d.get("baslik") or "")).strip()[:60]
    kanit = re.sub(r"[{}\r\n]+", " ", str(d.get("kanit") or "")).strip()[:140]
    if len(ders) < 15 or not baslik or not re.search(r"\d", kanit):
        return None
    if re.search(r"https?://|<script|talimat|ignore|yok say", ders, re.I):
        return None
    onem = d.get("onem") if d.get("onem") in (1, 2, 3) else 1
    return {"ajan": d["ajan"], "baslik": baslik, "ders": ders, "kanit": kanit, "onem": onem}


def dersleri_kaydet(yeni):
    kayit = json_oku(ONERILER, {"oneriler": []})
    liste = kayit.get("oneriler", [])
    var = {(o["ajan"], o["baslik"].lower()) for o in liste}
    bugun = simdi().astimezone(TR).strftime("%Y%m%d")
    n = sum(1 for o in liste if str(o.get("id", "")).startswith("o" + bugun))
    eklenen = []
    for d in yeni:
        if (d["ajan"], d["baslik"].lower()) in var:
            continue
        n += 1
        d.update({"id": f"o{bugun}-{n}", "tarih": simdi().strftime("%Y-%m-%dT%H:%M:%SZ"), "durum": "onay_bekliyor"})
        liste.append(d)
        eklenen.append(d)
    # eski reddedilenleri temizle, toplamı sınırla
    liste = [o for o in liste if o.get("durum") != "reddedildi"][-40:] + [o for o in liste if o.get("durum") == "reddedildi"][-10:]
    kayit["oneriler"] = sorted(liste, key=lambda o: o.get("tarih", ""))
    yaz_json(ONERILER, kayit)
    return eklenen


def calis(a):
    ozet = ozet_topla()
    DIZIN.mkdir(parents=True, exist_ok=True)
    yaz_json(RAPOR_JSON, ozet)
    hafta = simdi().astimezone(TR).strftime("%G-W%V")
    (DIZIN / f"rapor-{hafta}.md").write_text(rapor_metni(ozet), encoding="utf-8")
    print(rapor_metni(ozet))
    eklenen = []
    if not a.kuru:
        mevcut = [o.get("baslik", "") for o in json_oku(ONERILER, {}).get("oneriler", [])][-20:]
        try:
            sonuc = ders_cagir({k: v for k, v in ozet.items() if k != "calismalar" or v}, mevcut)
        except Exception as e:
            print(f"Ders önerileri alınamadı ({type(e).__name__}); rapor yine de yazıldı.")
            sonuc = None
        if sonuc:
            yeni = [d for d in (temiz_ders(x) for x in (sonuc.get("dersler") or [])[:3]) if d]
            eklenen = dersleri_kaydet(yeni)
            print(f"Ders önerisi: {len(eklenen)} yeni (onay bekliyor).")
            for d in eklenen:
                print(f"  - [{d['ajan']}] {d['baslik']}: {d['ders']} (kanıt: {d['kanit']})")
        elif sonuc is None and not os.environ.get("OPENAI_API_KEY"):
            print("OPENAI_API_KEY yok; yalnızca rapor yazıldı.")
    if a.git:
        subprocess.run(["git", "-C", str(KOK), "config", "user.name", "akademi-ajani"], check=False)
        subprocess.run(["git", "-C", str(KOK), "config", "user.email", "akademi-ajani@users.noreply.github.com"], check=False)
        subprocess.run(["git", "-C", str(KOK), "add", "-A", "--", "akademi"], check=False)
        if subprocess.run(["git", "-C", str(KOK), "diff", "--cached", "--quiet"]).returncode != 0:
            subprocess.run(["git", "-C", str(KOK), "commit", "-q", "-m", f"Akademi: haftalık rapor ve {len(eklenen)} ders önerisi"], check=False)
            for i in range(4):
                subprocess.run(["git", "-C", str(KOK), "pull", "--rebase", "-q"], check=False)
                if subprocess.run(["git", "-C", str(KOK), "push", "-q"]).returncode == 0:
                    break
    return eklenen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true", help="yapay zekâ kullanma, yalnızca rapor")
    ap.add_argument("--git", action="store_true", help="sonucu depoya yaz ve it")
    calis(ap.parse_args())


if __name__ == "__main__":
    main()
