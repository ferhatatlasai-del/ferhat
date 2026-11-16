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


def reels_paketi(t, persona):
    sahneler, uyarilar = [], []
    for i, sh in enumerate(t.get("sahneler") or [], 1):
        sure = int(sh.get("sure_sn") or 0)
        konusma = (sh.get("seslendirme") or "").strip()
        kelime = len(konusma.split())
        prompt = uret.video_promptu(sh, persona)
        if not (sh.get("sahne_promptu") or "").strip():
            uyarilar.append(f"Sahne {i}: sahne promptu boş.")
        if sure > MAKS_KLIP_SN:
            uyarilar.append(f"Sahne {i}: {sure} sn. Video araçları klipleri genelde {MAKS_KLIP_SN} sn üretir; bu sahneyi ikiye böl.")
        if sure and kelime / sure > MAKS_KELIME_SN:
            uyarilar.append(f"Sahne {i}: {kelime} kelime {sure} sn'ye sığmaz (en fazla ~{int(sure * MAKS_KELIME_SN)} kelime). Konuşmayı kısalt.")
        sahneler.append({"no": i, "sure_sn": sure, "gorsel": sh.get("gorsel", ""), "ekran_yazisi": sh.get("ekran_yazisi", ""),
                         "seslendirme": konusma, "prompt": prompt, "karakter": bool(sh.get("karakter_gorunur"))})
    toplam = sum(s["sure_sn"] for s in sahneler)
    return {"tur": "reels", "toplam_sn": toplam, "sahneler": sahneler, "uyarilar": uyarilar}


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
