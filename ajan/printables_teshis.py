#!/usr/bin/env python3
"""Printables veri servisinin yapısını (alan ve sorgu adları) günlüğe yazar. Yapay zekâ kullanmaz, ücretsizdir, hiçbir şey yazmaz.

Amaç: lisansa göre süzülmüş popüler tasarım listesini çekebilecek sorguyu bulmak.
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye_uret as U  # noqa: E402


def sor(ad, sorgu, degiskenler=None):
    try:
        v = U.graphql(sorgu, degiskenler)
    except Exception as e:
        print(f"[{ad}] istek hatası: {type(e).__name__}: {e}")
        return None
    if v.get("errors"):
        print(f"[{ad}] HATA: " + "; ".join(str(h.get("message"))[:160] for h in v["errors"][:3]))
    return v.get("data")


def tur_alanlari(ad):
    d = sor(f"tür {ad}", '{ __type(name: "%s") { fields { name type { name kind ofType { name kind } } args { name } } inputFields { name } enumValues { name } } }' % ad)
    t = (d or {}).get("__type")
    if not t:
        print(f"[tür {ad}] bulunamadı")
        return
    if t.get("fields"):
        print(f"[tür {ad}] alanlar: " + ", ".join(f["name"] + ("(" + ",".join(a["name"] for a in f["args"]) + ")" if f.get("args") else "") for f in t["fields"]))
    if t.get("inputFields"):
        print(f"[tür {ad}] giriş alanları: " + ", ".join(f["name"] for f in t["inputFields"]))
    if t.get("enumValues"):
        print(f"[tür {ad}] değerler: " + ", ".join(f["name"] for f in t["enumValues"]))


def main():
    print("== Printables servis teşhisi ==")
    d = sor("Query", '{ __schema { queryType { fields { name args { name } } } } }')
    if d:
        alanlar = d["__schema"]["queryType"]["fields"]
        print("[Query] sorgular: " + ", ".join(f["name"] + "(" + ",".join(a["name"] for a in f["args"]) + ")" for f in alanlar if any(k in f["name"].lower() for k in ("print", "model", "license", "search", "popular", "trend", "explore"))))
        print(f"[Query] toplam {len(alanlar)} sorgu")
    for ad in ("PrintType", "LicenseType", "PrintFilterInput", "SearchPrintsType", "PrintOrderingEnum", "OrderingEnum"):
        tur_alanlari(ad)
    # lisans listesi
    for sorgu in ("{ licenses { id name abbreviation disallowRemixing } }", "{ licenses { id name } }"):
        d = sor("licenses", sorgu)
        if d and d.get("licenses"):
            print("[licenses] " + json.dumps(d["licenses"], ensure_ascii=False)[:1500])
            break
    # olası liste sorguları (alan adları teşhis çıktısına göre ayarlanacak)
    denemeler = {
        "morePrints": '{ morePrints(limit: 5, ordering: "-likes_count_7_days") { id name license { name abbreviation } } }',
        "prints": '{ prints(limit: 5, ordering: "-likes_count_7_days") { id name license { name abbreviation } } }',
        "searchPrints": '{ searchPrints2(query: "box", limit: 5) { items { id name license { name abbreviation } } } }',
    }
    for ad, q in denemeler.items():
        d = sor(f"deneme {ad}", q)
        if d:
            print(f"[deneme {ad}] BAŞARILI: " + json.dumps(d, ensure_ascii=False)[:700])


if __name__ == "__main__":
    main()
