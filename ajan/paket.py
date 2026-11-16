#!/usr/bin/env python3
"""Video paketi ajanı: senaryoyu, yapay zekâ video aracına (Flow vb.) yapıştırmaya hazır pakete çevirir ve kontrol eder.

Girdi : zincir/<kimlik>.json ve zincir/<kimlik>_taslak.json (içerik ajanının senaryosu)
Çıktı : kayda "paket" alanı + zincir/<kimlik>_paket.md (okunur hali)

Kontroller (uyarı verir, engellemez):
- Klip süresi 8 saniyeyi aşıyor mu (video araçlarının klipleri genelde 8 sn'dir)
- Konuşma, sürenin izin verdiğinden hızlı mı (Türkçe için ~2,5 kelime/sn)
- Sahne promptu boş ya da karakter tarifi eksik mi

Hiçbir şey yayınlamaz, video üretmez.
Kullanım:
    python3 ajan/paket.py --son          # paketi henüz hazırlanmamış en yeni kayıt
    python3 ajan/paket.py --kimlik c20261116-215101
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import uret  # noqa: E402

KOK = uret.KOK
MAKS_KLIP_SN = 8
MAKS_KELIME_SN = 2.6
HEDEF_KELIME_SN = 2.3   # süreyi uzatırken kullanılan rahat konuşma hızı
import re  # noqa: E402
PARCA = re.compile(r"hinge|latch|lid|clasp|mechanism|gear|spring|joint|flap", re.I)
HAREKET = re.compile(r"flex\w*|snapp\w*|open(?:ing|s)\b|clos(?:ing|es)\b|shut|slid\w*|rotat\w*|fold\w*|swing\w*|press\w*|moving|unlock\w*", re.I)


def reels_paketi(t, persona):
    sahneler, uyarilar, notlar, mekanik = [], [], [], []
    for i, sh in enumerate(t.get("sahneler") or [], 1):
        sure = int(sh.get("sure_sn") or 0)
        konusma = (sh.get("seslendirme") or "").strip()
        kelime = len(konusma.split())
        prompt = uret.video_promptu(sh, persona)
        if not (sh.get("sahne_promptu") or "").strip():
            uyarilar.append(f"Sahne {i}: sahne promptu boş.")
        # Konuşma süreye sığmıyorsa süreyi (8 sn'yi aşmadan) uzat; imza cümleleri sabit olduğu için kısaltmak yerine bu yapılır
        if sure and kelime / sure > MAKS_KELIME_SN:
            gereken = -(-int(kelime / HEDEF_KELIME_SN * 10) // 10)
            gereken = max(sure + 1, int(kelime / HEDEF_KELIME_SN + 0.999))
            if gereken <= MAKS_KLIP_SN:
                notlar.append(f"Sahne {i}: konuşma ({kelime} kelime) {sure} sn'ye sığmıyordu, süre {gereken} sn'ye çıkarıldı.")
                sure = gereken
            else:
                uyarilar.append(f"Sahne {i}: {kelime} kelime {MAKS_KLIP_SN} sn'ye bile sığmaz. Konuşmayı kısalt ya da sahneyi ikiye böl.")
        if sure > MAKS_KLIP_SN:
            uyarilar.append(f"Sahne {i}: {sure} sn. Video araçları klipleri genelde {MAKS_KLIP_SN} sn üretir; bu sahneyi ikiye böl.")
        sp = sh.get("sahne_promptu") or ""
        if PARCA.search(sp) and HAREKET.search(sp):
            mekanik.append(i)
        sahneler.append({"no": i, "sure_sn": sure, "gorsel": sh.get("gorsel", ""), "ekran_yazisi": sh.get("ekran_yazisi", ""),
                         "seslendirme": konusma, "prompt": prompt, "karakter": bool(sh.get("karakter_gorunur"))})
    if mekanik:
        uyarilar.append("Sahne " + ", ".join(map(str, mekanik)) + ": mekanik hareket (menteşe, kilit, kapak). Video modelleri bunu çoğu zaman fiziksel olarak "
                        "mümkün olmayacak biçimde çizer. Kısa, tek hareketli, yakın plan iste; sonuç gerçekçi değilse sahneyi çıkar ya da gerçek bir baskıyı çek.")
    toplam = sum(s["sure_sn"] for s in sahneler)
    return {"tur": "reels", "toplam_sn": toplam, "sahneler": sahneler, "uyarilar": uyarilar, "notlar": notlar}


def carousel_paketi(t, persona):
    slaytlar = []
    for i, sl in enumerate(t.get("slaytlar") or [], 1):
        slaytlar.append({"no": i, "baslik": sl.get("baslik", ""), "metin": uret.numara_temizle(sl.get("metin", "")),
                         "prompt": uret.gorsel_promptu(sl, persona), "karakter": bool(sl.get("karakter_gorunur"))})
    return {"tur": "carousel", "slaytlar": slaytlar, "uyarilar": uret.carousel_uyarilari(t, t.get("slaytlar") or [])}


def okunur(kayit, p):
    s = [f"# Video paketi: {kayit['konu']}", "", f"- Kimlik: {kayit['kimlik']}", f"- Tür: {p['tur']}"]
    if p["tur"] == "reels":
        s.append(f"- Toplam süre: {p['toplam_sn']} sn")
        for sh in p["sahneler"]:
            s += ["", f"## Sahne {sh['no']} ({sh['sure_sn']} sn)", f"- Ekran yazısı: {sh['ekran_yazisi']}",
                  f"- Konuşma: {sh['seslendirme']}", "", "Prompt:", sh["prompt"]]
    else:
        for sl in p["slaytlar"]:
            s += ["", f"## Slayt {sl['no']}: {sl['baslik']}", f"- Yazı: {sl['metin']}", "", "Prompt:", sl["prompt"]]
    if p.get("notlar"):
        s += ["", "## Notlar"] + [f"- {n}" for n in p["notlar"]]
    if p["uyarilar"]:
        s += ["", "## Uyarılar"] + [f"- {u}" for u in p["uyarilar"]]
    return "\n".join(s) + "\n"


def isle(kimlik):
    dizin = KOK / "zincir"
    kayit_yolu = dizin / f"{kimlik}.json"
    kayit = json.loads(kayit_yolu.read_text(encoding="utf-8"))
    t = json.loads((KOK / kayit["taslak_json"]).read_text(encoding="utf-8"))
    persona = uret.persona_tarifi()
    p = reels_paketi(t, persona) if t.get("format") == "reels" else carousel_paketi(t, persona)
    kayit["paket"] = p
    if t.get("model_notu"):
        kayit["model_notu"] = t["model_notu"]
    kayit_yolu.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    (dizin / f"{kimlik}_paket.md").write_text(okunur(kayit, p), encoding="utf-8")
    n = len(p.get("sahneler") or p.get("slaytlar") or [])
    print(f"Video paketi hazır: {kimlik} ({p['tur']}, {n} parça, {len(p['uyarilar'])} uyarı)")
    for u in p["uyarilar"]:
        print(f"UYARI: {u}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--son", action="store_true")
    g.add_argument("--kimlik")
    a = ap.parse_args()
    if a.kimlik:
        return isle(a.kimlik)
    adaylar = []
    for y in sorted((KOK / "zincir").glob("c*.json"), reverse=True):
        if y.stem.endswith("_taslak") or y.stem.endswith("_paket"):
            continue
        if "paket" not in json.loads(y.read_text(encoding="utf-8")):
            adaylar.append(y.stem)
    if not adaylar:
        print("Paketi hazırlanacak kayıt yok.")
        return
    isle(adaylar[0])


if __name__ == "__main__":
    main()
