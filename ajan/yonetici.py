#!/usr/bin/env python3
"""Yönetici ajan (admin): sahibinin amacını ve tarzını yönergeden + geçmiş kararlarından taklit ederek sistemi izler, ajanlara talimat verir ve günde 2 kez rapor yazar.

Yetki kademeleri (panelden seçilir, ajan Aç/Kapat düğmesiyle birlikte):
  1 Öneri: hiçbir şeyi değiştirmez; yapılacakları "önerildi" olarak rapora yazar.
  2 Güvenli işler: iş akışı tetikler (Nöbetçi/İstatistik/Yorum taraması), günlük hikâye sayısını ±2 ayarlar (3-12), öncelikli video konusu ekler, taslağa "admin notu" düşer.
  3 Onay yetkisi: 2'ye ek olarak risksiz yorum yanıtlarını (övgü/teşekkür/soru…) onaylar (turda en çok 5).
Her kademede DEĞİŞMEYEN sert sınırlar: bütçe/anahtar/sır değiştirmez, kalıcı silmez, video YAYINLAMAZ, günlük 15 işlemden fazlasını yapmaz.
Tüm kararlar yonetici/rapor.json "defter" bölümüne yazılır. Model: ANTHROPIC_API_KEY varsa Claude, yoksa OpenAI.
"""
import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402

GH_API = os.environ.get("GH_API") or "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO") or ""
DAL = os.environ.get("GITHUB_REF_NAME") or os.environ.get("GH_DAL") or "main"
OPENAI = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
ANTHROPIC = os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
import yz_model as YZ  # noqa: E402
OPENAI_MODEL = YZ.model("yonetici", "gpt-5.4-mini")
CLAUDE_MODEL = os.environ.get("YONETICI_MODEL") or "claude-sonnet-5-5"
AYAR = "yonetici/ayar.json"
RAPOR = "yonetici/rapor.json"
GUNLUK_ISLEM = 15
SERBEST_AKISLAR = {"nobetci.yml": {}, "istatistik-rapor.yml": {"elle": "EVET"}, "yorum-ajani.yml": {"elle": "EVET"}}
YORUM_ONAY_KATEGORILERI = {"övgü", "teşekkür", "soru", "öneri", "emoji", "diğer"}
SHORTS_RE = re.compile(r"^s\d{8}-\d{6}$")
VARSAYILAN_AYAR = {"aktif": False, "kademe": 2, "yonerge": "", "otomatik_yayin": "kapali"}


def simdi_tr():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)


def slug(metin):
    t = metin.lower().translate(str.maketrans("çğıöşü", "cgiosu"))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


# ---------- GitHub ----------

def gh(yontem, yol, govde=None):
    istek = urllib.request.Request(GH_API + yol, method=yontem, data=json.dumps(govde).encode() if govde is not None else None,
                                   headers={"Authorization": "Bearer " + os.environ.get("GITHUB_TOKEN", ""), "Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "yonetici-ajan"})
    with urllib.request.urlopen(istek, timeout=60) as y:
        d = y.read()
        return json.loads(d) if d else {}


def dosya_oku(yol):
    try:
        d = gh("GET", f"/repos/{REPO}/contents/{yol}?ref={urllib.parse.quote(DAL)}")
        return json.loads(base64.b64decode(d["content"]).decode("utf-8")), d["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise


def klasor_adlari(yol):
    try:
        return [f["name"] for f in gh("GET", f"/repos/{REPO}/contents/{yol}?ref={urllib.parse.quote(DAL)}")]
    except urllib.error.HTTPError:
        return []


def json_guncelle(yol, degistir, varsayilan, mesaj):
    for i in range(5):
        veri, sha = dosya_oku(yol)
        veri = veri if veri is not None else json.loads(json.dumps(varsayilan))
        if degistir(veri) is False:
            return False
        govde = {"message": mesaj, "content": base64.b64encode(json.dumps(veri, ensure_ascii=False, indent=2).encode()).decode(), "branch": DAL}
        if sha:
            govde["sha"] = sha
        try:
            gh("PUT", f"/repos/{REPO}/contents/{yol}", govde)
            return True
        except urllib.error.HTTPError as e:
            if e.code not in (409, 422):
                raise
            time.sleep(1 + i)
    return False


# ---------- durum özeti (modele verilen) ----------

def durum_ozeti():
    o = {}
    ayar, _ = dosya_oku("hikaye/ayar.json")
    uretim, _ = dosya_oku("hikaye/uretim.json")
    harcama, _ = dosya_oku("hikaye/harcama.json")
    saglik, _ = dosya_oku("hikaye/saglik.json")
    gun, ay = simdi_tr().strftime("%Y-%m-%d"), simdi_tr().strftime("%Y-%m")
    o["hikaye"] = {"aktif": (ayar or {}).get("aktif"), "gunluk_sayi": (ayar or {}).get("gunluk_sayi"), "saat": [(ayar or {}).get("baslangic_saat"), (ayar or {}).get("bitis_saat")],
                   "butce_usd": (uretim or {}).get("aylik_butce_usd"), "bugun_gorsel": ((harcama or {}).get("gunler", {}).get(gun) or {}).get("gorsel", 0), "ay_gorsel": ((harcama or {}).get("aylar", {}).get(ay) or {}).get("gorsel", 0), "not": (ayar or {}).get("son_not")}
    o["saglik"] = [f"{c.get('ad')}: {c.get('durum')} ({str(c.get('not'))[:60]})" for c in (saglik or {}).get("kontroller", [])]
    ist, _ = dosya_oku("istatistik/son.json")
    if ist:
        izl = []
        for g in (ist.get("instagram", {}).get("gonderiler") or []):
            izl.append((g.get("izlenme") or 0, "IG", str(g.get("baslik") or "")[:60]))
        for v in (ist.get("youtube", {}).get("videolar") or []):
            izl.append((v.get("izlenme") or 0, "YT", str(v.get("baslik") or "")[:60]))
        o["istatistik"] = {"toplam": (ist.get("toplam") or {}).get("toplam"), "fark": ist.get("fark"), "en_cok": [f"{p} {n:,}: {b}".replace(",", ".") for n, p, b in sorted(izl, reverse=True)[:5]]}
    tas = []
    for ad in sorted(n for n in klasor_adlari("shorts") if re.fullmatch(r"s\d{8}-\d{6}\.json", n))[-6:]:
        d, _ = dosya_oku("shorts/" + ad)
        if d:
            tas.append({"id": d.get("id"), "durum": d.get("durum"), "baslik": str(d.get("baslik"))[:70], "yayinlanan": d.get("yayinlanan"), "admin_oneri": d.get("admin_oneri"), "konu": str(d.get("konu"))[:80], "sahne_tipleri": [z.get("tip") for z in (d.get("zamanlama") or [])], "sure": d.get("sure")})
    o["video_taslaklari"] = tas
    nk, _ = dosya_oku("shorts/viral_noktalar.json")
    o["son_video_noktalari"] = [{"konu": str(v.get("konu"))[:60], "noktalar": [str(n)[:50] for n in v.get("noktalar", [])[:8]]} for v in (nk or {}).get("videolar", [])[-3:]]
    yk, _ = dosya_oku("yorum/kuyruk.json")
    ya, _ = dosya_oku("yorum/ayar.json")
    yo = (yk or {}).get("ogeler", [])
    o["yorum"] = {"mod": (ya or {}).get("mod", "onay"), "aktif": (ya or {}).get("aktif", True), "sayilar": {d: sum(1 for x in yo if x.get("durum") == d) for d in ("onay_bekliyor", "onaylandi", "gonderildi", "atlandi", "reddedildi", "hata")},
                "bekleyenler": [{"id": x["id"], "kategori": x.get("kategori"), "yorum": str(x.get("yorum"))[:80], "yanit": str(x.get("yanit"))[:120]} for x in yo if x.get("durum") == "onay_bekliyor"][:8]}
    va, _ = dosya_oku("shorts/viral_ayar.json")
    kul, _ = dosya_oku("shorts/viral_kullanilan.json")
    kul = kul or []
    bek = [k["konu"] for k in (va or {}).get("oncelikli", []) if "anlat-" + slug(k["konu"]) not in kul]
    o["video_konulari"] = {"oncelikli_kalan": bek[:6], "uretilmis_sayi": len(kul)}
    ot, _ = dosya_oku("yonetici/otomatik.json")
    kay = (ot or {}).get("kayitlar", [])
    o["otomatik_hat"] = {"mod": None, "bugun": [f"{k.get('zaman', '')[11:]} {str(k.get('baslik') or k.get('ayrinti'))[:50]} → {k.get('durum')}" + (f" (puan {k['inceleme'].get('puan')}; {'; '.join(k['inceleme'].get('sorunlar', [])[:2])})" if k.get("inceleme") else "") for k in kay if str(k.get("zaman", ""))[:10] == gun],
                         "son_5": [f"{k.get('zaman')} {str(k.get('baslik') or k.get('ayrinti'))[:40]} → {k.get('durum')}" for k in kay[-5:]]}
    try:
        runs = gh("GET", f"/repos/{REPO}/actions/runs?per_page=40").get("workflow_runs", [])
        esik = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hatalar = {}
        for r in runs:
            if r.get("created_at", "") >= esik and r.get("conclusion") == "failure":
                hatalar[r["name"][:40]] = hatalar.get(r["name"][:40], 0) + 1
        o["son_24s_basarisiz_is_akislari"] = hatalar
    except Exception:
        pass
    yon, _ = dosya_oku(AYAR)
    o["otomatik_hat"]["mod"] = (yon or {}).get("otomatik_yayin", "kapali")
    return o, {"ayar": ayar or {}}


# ---------- model ----------

def llm(sistem, kullanici):
    anth = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if anth:
        govde = {"model": CLAUDE_MODEL, "max_tokens": 3000, "system": sistem, "messages": [{"role": "user", "content": kullanici}]}
        r = urllib.request.Request(f"{ANTHROPIC}/v1/messages", data=json.dumps(govde).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "x-api-key": anth, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(r, timeout=180) as y:
            metin = "".join(b.get("text", "") for b in json.load(y).get("content", []) if b.get("type") == "text")
        kaynak = f"Claude ({CLAUDE_MODEL})"
    else:
        anahtar = os.environ.get("OPENAI_API_KEY")
        if not anahtar:
            raise RuntimeError("ne ANTHROPIC_API_KEY ne OPENAI_API_KEY tanımlı")
        govde = {"model": OPENAI_MODEL, "response_format": {"type": "json_object"}, "temperature": 0.4, "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}]}
        r = urllib.request.Request(f"{OPENAI}/chat/completions", data=json.dumps(govde).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
        with urllib.request.urlopen(r, timeout=180) as y:
            metin = json.load(y)["choices"][0]["message"]["content"]
        kaynak = f"OpenAI ({OPENAI_MODEL})"
    m = re.search(r"\{.*\}", metin, re.S)
    return json.loads(m.group(0)), kaynak


SISTEM = """Sen "Yönetici" ajansın: Gür-Techs 3D (@gurtechs3d, 3D yazıcı içerikleri, Türkçe Reels/Shorts/hikâye) kanalının sahibinin (admin) amacını, tarzını ve tercihlerini taklit ederek sistemi izlersin.
Sahibinin yönergesi aşağıda. Ona göre karar ver; emin değilsen karar verme, öneri yaz. Yalnızca geçerli JSON döndür.
DÜRÜST OL: durum özetinde olmayan bir şeyi uydurma; veri yoksa "veri yok" de.
OTOMATİK HAT (bilmen gereken): Kademe 3'te ve panelden "otomatik_yayin" açıkken sistem günde 3 video (TR 10:05, 15:05, 20:05) üretir; videoyu SEN izlersin (kareler + anlatı + bilgi tabanı) ve saçma/yanlış/bozuk bulursan reddedersin, yalnızca onayladıklarını Instagram Reels, Instagram Hikâye, YouTube Shorts ve YouTube normal video olarak yayınlarsın. Mod: kapali / deneme (üret+izle, yayınlama) / acik. Durum özetindeki "otomatik_hat" bugünkü turları gösterir. Bu hattın modunu DEĞİŞTİREMEZSİN (sahibi panelden belirler); aksaklık, art arda ret ya da kota sorununu raporda belirt ve öner.
BİLGİ TABANI (3D baskı doğruluk ölçütleri):
{bilgi}
KADEME {kademe}: {kademe_aciklama}
KULLANABİLECEĞİN EYLEMLER (başka eylem yazma):
{eylemler}
SERT SINIRLAR (hiçbir kademede yapma): bütçe tavanını ya da anahtar/sır değiştirmek, kalıcı silmek, video yayınlamak, yorum modunu otomatiğe almak.
ÇIKTI: {{"rapor": ["madde", ...] (4-7 kısa Türkçe madde, sahibine "sen" diye hitap eden, ne gördün/ne yaptın/ne öneriyorsun), "kararlar": [{{"eylem": "...", "params": {{...}}, "neden": "kısa"}}], "oneriler": ["sahibine öneri", ...], "uyarilar": ["acil bir şey varsa", ...]}}"""
EYLEM_2 = """- workflow_tetikle {"akis": "nobetci.yml" | "istatistik-rapor.yml" | "yorum-ajani.yml"}: ilgili ajanı bir kez çalıştırır (yalnızca gerçekten gerektiğinde).
- hikaye_ayar {"gunluk_sayi": 3-12}: günlük hikâye sayısını en çok ±2 değiştirir (bütçe ve izlenmeye göre).
- konu_oncelik_ekle {"konu": "...", "ipucu": "..."}: yeni video konusunu sıraya ekler (bekleyen öncelikli konu 3'ten azsa; başarılı içeriklerin kalıbına yakın ve daha önce yapılmamış olsun).
- taslak_isaretle {"id": "sYYYYMMDD-HHMMSS", "oneri": "incele"|"reddet", "not": "kısa neden"}: onay bekleyen video taslağına sahibi için not düşer (kendisi onaylamaz/reddetmez). Videonun İÇERİĞİNİ GÖRMEZSİN (yalnızca başlık, konu, sahne tipleri ve noktalar): bu yüzden "onayla" önerme; yalnızca somut bir nedenin varsa (konu önceki videoyla çok benziyor, sahne çeşitliliği az, başlık kural dışı) "incele" ya da "reddet" yaz. Aynı taslağa zaten not düşüldüyse tekrar yazma."""
EYLEM_3 = """- yorum_onayla {"idler": ["ig-..."]}: onay bekleyen RİSKSİZ yorum yanıtlarını (nazik, kısa, kurallara uygun) onaylar; turda en çok 5."""
KADEME_ACIKLAMA = {1: "Yalnızca ÖNERİ: hiçbir eylem yürütülmez; eylem yazarsan 'önerildi' olarak kaydedilir.", 2: "Güvenli işleri kendin yaparsın (aşağıdaki eylemler).", 3: "Kademe 2 + onay yetkisi (yorum yanıtlarını onaylayabilirsin)."}


def eylem_yurut(e, kademe, ozet):
    """Bir kararı SERT SINIRLARA göre doğrular ve (kademe >= 2) yürütür. Dönen: (durum, ayrıntı)."""
    ad, p = str(e.get("eylem") or ""), (e.get("params") if isinstance(e.get("params"), dict) else {})
    izinli = {"workflow_tetikle", "hikaye_ayar", "konu_oncelik_ekle", "taslak_isaretle"} | ({"yorum_onayla"} if kademe >= 3 else set())
    if ad not in izinli:
        return "reddedildi", f"'{ad}' bu kademede izinli değil ya da tanımsız"
    # --- doğrulama (model ne yazarsa yazsın) ---
    if ad == "workflow_tetikle":
        if p.get("akis") not in SERBEST_AKISLAR:
            return "reddedildi", "izinli olmayan iş akışı"
    elif ad == "hikaye_ayar":
        try:
            yeni = int(p.get("gunluk_sayi"))
        except (TypeError, ValueError):
            return "reddedildi", "gunluk_sayi sayı değil"
        mevcut = int((ozet["hikaye"].get("gunluk_sayi") or 0) or 0)
        if not 3 <= yeni <= 12 or abs(yeni - mevcut) > 2 or yeni == mevcut:
            return "reddedildi", f"{mevcut}→{yeni} sınır dışı (3-12, en çok ±2, aynı değil)"
    elif ad == "konu_oncelik_ekle":
        konu, ipucu = " ".join(str(p.get("konu") or "").split())[:100], " ".join(str(p.get("ipucu") or "").split())[:300]
        if len(konu) < 12 or len(ozet["video_konulari"]["oncelikli_kalan"]) >= 3:
            return "reddedildi", "konu kısa ya da bekleyen öncelikli konu zaten yeterli"
        if any(slug(konu) == slug(k) for k in ozet["video_konulari"]["oncelikli_kalan"]):
            return "reddedildi", "bu konu zaten sırada"
        p = {"konu": konu, "ipucu": ipucu}
    elif ad == "taslak_isaretle":
        if not SHORTS_RE.match(str(p.get("id") or "")) or p.get("oneri") not in ("incele", "reddet"):
            return "reddedildi", "geçersiz taslak kimliği ya da öneri"
    elif ad == "yorum_onayla":
        idler = [str(i) for i in (p.get("idler") or []) if re.fullmatch(r"ig-\d{5,30}", str(i))][:5]
        if not idler:
            return "reddedildi", "geçerli yorum kimliği yok"
        p = {"idler": idler}
    if kademe < 2:
        return "onerildi", "Kademe 1: yürütülmedi, öneri olarak kaydedildi"
    # --- yürütme ---
    try:
        if ad == "workflow_tetikle":
            gh("POST", f"/repos/{REPO}/actions/workflows/{p['akis']}/dispatches", {"ref": DAL, "inputs": SERBEST_AKISLAR[p["akis"]]})
            return "yapildi", p["akis"] + " tetiklendi"
        if ad == "hikaye_ayar":
            json_guncelle("hikaye/ayar.json", lambda v: v.update(gunluk_sayi=int(p["gunluk_sayi"])), {}, "Yönetici: günlük hikâye sayısı")
            return "yapildi", f"günlük hikâye sayısı {p['gunluk_sayi']}"
        if ad == "konu_oncelik_ekle":
            json_guncelle("shorts/viral_ayar.json", lambda v: v.setdefault("oncelikli", []).append({"konu": p["konu"], "ipucu": p["ipucu"]}), {}, "Yönetici: öncelikli video konusu")
            return "yapildi", p["konu"]
        if ad == "taslak_isaretle":
            def isaretle(v):
                if v.get("durum") != "onay_bekliyor" or v.get("admin_oneri") == p["oneri"]:   # onay beklemiyorsa ya da aynı öneri zaten yazılıysa dokunma
                    return False
                v.update(admin_notu=str(p.get("not") or "")[:160], admin_oneri=p["oneri"])
            ok = json_guncelle(f"shorts/{p['id']}.json", isaretle, {}, "Yönetici: taslak notu")
            return ("yapildi", f"{p['id']}: {p['oneri']} önerisi") if ok else ("reddedildi", "taslak onay beklemiyor, bulunamadı ya da aynı öneri zaten yazılı")
        if ad == "yorum_onayla":
            sonuc = []

            def isle(v):
                for o in v.get("ogeler", []):
                    if o.get("id") in p["idler"] and o.get("durum") == "onay_bekliyor" and o.get("yanit") and len(o["yanit"]) <= 220 and (o.get("kategori") or "diğer") in YORUM_ONAY_KATEGORILERI:
                        o["durum"] = "onaylandi"
                        sonuc.append(o["id"])
                if not sonuc:
                    return False
            json_guncelle("yorum/kuyruk.json", isle, {"ogeler": []}, "Yönetici: yorum yanıtları onaylandı")
            if sonuc:
                try:
                    gh("POST", f"/repos/{REPO}/actions/workflows/yorum-ajani.yml/dispatches", {"ref": DAL, "inputs": {"sadece_gonder": "EVET"}})
                except Exception:
                    pass
            return ("yapildi", f"{len(sonuc)} yanıt onaylandı") if sonuc else ("reddedildi", "uygun bekleyen yanıt yok")
    except Exception as ex:
        return "hata", f"{type(ex).__name__}: {str(ex)[:100]}"
    return "reddedildi", "bilinmeyen"


def bekleyen_video_incele(ozet, kademe, yonerge, bilgi_tabani):
    """Onay bekleyen (elle yayınlanacak) en yeni video taslağını, daha önce incelenmediyse İZLER (karelerle); sonucu özete ve (Kademe 2+) taslağa not olarak yazar."""
    import tempfile
    import video_inceleme as VI
    adaylar = [t for t in reversed(ozet.get("video_taslaklari", [])) if t.get("durum") == "onay_bekliyor"]
    for t in adaylar[:1]:
        d, _ = dosya_oku(f"shorts/{t['id']}.json")
        if not d or d.get("admin_inceleme") or not d.get("video"):
            continue
        with tempfile.TemporaryDirectory() as g:
            yol = pathlib.Path(g) / "video.mp4"
            try:
                urllib.request.urlretrieve((os.environ.get("YONETICI_VIDEO_TABAN") or f"https://raw.githubusercontent.com/{REPO}/{DAL}/") + d["video"], yol)
                nk, _ = dosya_oku("shorts/viral_noktalar.json")
                onceki = [n for v in (nk or {}).get("videolar", []) for n in v.get("noktalar", [])]
                bilgi = {"baslik": d.get("baslik"), "konu": d.get("konu"), "aciklama": d.get("aciklama"), "anlati": d.get("anlati") or "(anlatı metni kayıtlı değil)", "sahneler": [z.get("tip") for z in d.get("zamanlama") or []], "noktalar": []}
                inc = VI.incele(yol, bilgi, yonerge, bilgi_tabani, onceki)
            except Exception as e:
                print(f"UYARI: taslak incelenemedi ({type(e).__name__}: {str(e)[:100]})")
                continue
        ozet_inc = {k: inc.get(k) for k in ("karar", "puan", "sorunlar", "gerekce", "model", "iddialar")}
        t["inceleme"] = {"karar": inc["karar"], "puan": inc["puan"], "sorunlar": inc["sorunlar"][:3], "gerekce": inc["gerekce"]}
        print(f"Bekleyen taslak incelendi: {t['id']} → {inc['karar']} (puan {inc['puan']})")
        if kademe >= 2:
            json_guncelle(f"shorts/{t['id']}.json", lambda v: v.update(admin_inceleme=ozet_inc, admin_oneri=("reddet" if inc["karar"] != "yayinla" else v.get("admin_oneri")), admin_notu=(inc["gerekce"][:160] if inc["karar"] != "yayinla" else v.get("admin_notu"))), {}, "Yönetici: taslak incelemesi")


def calis(a):
    ayar, _ = dosya_oku(AYAR)
    ayar = {**VARSAYILAN_AYAR, **(ayar or {})}
    if not ayar["aktif"] and not a.elle:
        print("Yönetici ajan kapalı (panelden açılır); atlandı.")
        return 0
    kademe = int(ayar.get("kademe") or 2)
    kademe = kademe if kademe in (1, 2, 3) else 2
    ozet, _ = durum_ozeti()
    bd = pathlib.Path(__file__).resolve().parent.parent / "yonetici" / "bilgi.md"
    try:
        bekleyen_video_incele(ozet, kademe, ayar.get("yonerge", ""), bd.read_text(encoding="utf-8") if bd.exists() else "")
    except Exception as e:
        print(f"UYARI: video incelemesi atlandı ({type(e).__name__}: {str(e)[:100]})")
    rapor_d, _ = dosya_oku(RAPOR)
    rapor_d = rapor_d or {}
    bugun = simdi_tr().strftime("%Y-%m-%d")
    kalan = GUNLUK_ISLEM - sum(1 for d in rapor_d.get("defter", []) if str(d.get("zaman", ""))[:10] == bugun and d.get("durum") == "yapildi")
    hafiza = [f"{d.get('zaman', '')[:10]} {d.get('eylem')} → {d.get('durum')}: {str(d.get('ayrinti'))[:60]}" for d in rapor_d.get("defter", [])[-14:] if "onayla önerisi" not in str(d.get("ayrinti"))][-8:]   # eski hatalı "onayla" kayıtları anomali alarmı üretmesin
    eylemler = EYLEM_2 + ("\n" + EYLEM_3 if kademe >= 3 else "")
    bilgi_dosyasi = pathlib.Path(__file__).resolve().parent.parent / "yonetici" / "bilgi.md"
    sistem = SISTEM.format(kademe=kademe, kademe_aciklama=KADEME_ACIKLAMA[kademe], eylemler=eylemler, bilgi=(bilgi_dosyasi.read_text(encoding="utf-8")[:4500] if bilgi_dosyasi.exists() else "(yok)"))
    kullanici = ("SAHİBİNİN YÖNERGESİ:\n" + (ayar.get("yonerge") or "(yönerge yok)")[:4000] + "\n\nSİSTEM DURUMU (JSON):\n" + json.dumps(ozet, ensure_ascii=False)[:9000] +
                 "\n\nSON KARARLARIN:\n" + ("\n".join(hafiza) or "(henüz yok)") + f"\n\nBugün kalan işlem hakkı: {kalan}. Şimdi: {simdi_tr().strftime('%d.%m.%Y %H:%M')} (TR).")
    try:
        j, kaynak = llm(sistem, kullanici)
    except Exception as e:
        print(f"HATA: yönetici modeli çalışmadı: {type(e).__name__}: {str(e)[:160]}")
        H.bildir("Yönetici ajan çalışamadı", f"{type(e).__name__}", adres="/#yonetici", etiket="yonetici")
        return 1
    defter = []
    for e in (j.get("kararlar") or [])[:8]:
        if not isinstance(e, dict):
            continue
        if kalan <= 0:
            durum, ayr = "reddedildi", "günlük işlem sınırı doldu"
        else:
            durum, ayr = eylem_yurut(e, kademe, ozet)
            if durum == "yapildi":
                kalan -= 1
        defter.append({"zaman": simdi_tr().strftime("%Y-%m-%d %H:%M"), "kademe": kademe, "eylem": str(e.get("eylem"))[:30], "params": e.get("params") if isinstance(e.get("params"), dict) else {}, "neden": str(e.get("neden") or "")[:200], "durum": durum, "ayrinti": ayr})
        print(f"  {e.get('eylem')}: {durum} — {ayr}")
    kayit = {"zaman": simdi_tr().strftime("%Y-%m-%d %H:%M"), "kademe": kademe, "model": kaynak, "rapor": [str(x)[:260] for x in (j.get("rapor") or [])][:8], "oneriler": [str(x)[:260] for x in (j.get("oneriler") or [])][:6],
             "uyarilar": [str(x)[:260] for x in (j.get("uyarilar") or [])][:5], "eylem_sayisi": sum(1 for d in defter if d["durum"] == "yapildi")}

    def yaz(v):
        v.setdefault("raporlar", []).append(kayit)
        v["raporlar"] = v["raporlar"][-30:]
        v.setdefault("defter", []).extend(defter)
        v["defter"] = v["defter"][-200:]
    json_guncelle(RAPOR, yaz, {"raporlar": [], "defter": []}, "Yönetici: rapor")
    ilk = (kayit["rapor"] or ["Rapor hazır."])[0]
    H.bildir("Yönetici raporu", ilk[:120], adres="/#yonetici", etiket="yonetici")
    print("Rapor yazıldı:", ilk[:100])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elle", action="store_true", help="ajan kapalı olsa da bir kez çalış")
    return calis(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
