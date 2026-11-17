#!/usr/bin/env python3
"""Printables veri servisinin searchPrints2 sorgusunun lisans/sıralama filtrelerini hata mesajlarından keşfeder. Ücretsiz, yapay zekâsız, yazmaz."""
import json
import sys
import pathlib
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye_uret as U  # noqa: E402


def ham(sorgu):
    govde = json.dumps({"query": sorgu, "variables": {}}).encode()
    r = urllib.request.Request(U.PRINTABLES_API, data=govde, method="POST",
                               headers={"Content-Type": "application/json", "User-Agent": U.BOT_ADI, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as y:
            return y.status, json.load(y)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"errors": [{"message": f"{type(e).__name__}"}]}


def dene(ad, sorgu):
    kod, v = ham(sorgu)
    hatalar = "; ".join(str(h.get("message"))[:260] for h in (v.get("errors") or [])[:3])
    veri = v.get("data")
    if veri and not v.get("errors"):
        s = json.dumps(veri, ensure_ascii=False)
        print(f"[{ad}] TAMAM ({kod}): {s[:900]}")
    else:
        print(f"[{ad}] HATA ({kod}): {hatalar or 'yanıt boş'}")


ALAN = "items { id name slug likesCount downloadCount license { abbreviation } user { publicUsername } image { filePath } }"


def main():
    print("== Printables searchPrints2 teşhisi ==")
    dene("temel", '{ searchPrints2(query: "box", limit: 3) { items { id name license { abbreviation } } } }')
    dene("alan-genis", '{ searchPrints2(query: "box", limit: 3) { ' + ALAN + ' } }')
    dene("alan-resim", '{ searchPrints2(query: "box", limit: 3) { items { id name images { filePath } } } }')
    for isim in ("licenses", "license", "licenseIds", "licenseId", "licenses_ids"):
        dene(f"filtre {isim}", '{ searchPrints2(query: "box", limit: 3, %s: [1, 7]) { items { id name license { abbreviation } } } }' % isim)
    dene("filtre license tek", '{ searchPrints2(query: "box", limit: 3, license: 1) { items { id name license { abbreviation } } } }')
    for sira in ("best_match", "popular", "likes_count_today", "likes_count_7_days", "download_count_7_days", "download_count_today",
                 "makes_count_30_days", "newest", "date_published", "popularity", "trending"):
        dene(f"sıralama {sira}", '{ searchPrints2(query: "box", limit: 3, ordering: %s) { items { id name } } }' % sira)
    dene("sıralama tırnaklı", '{ searchPrints2(query: "box", limit: 3, ordering: "-likes_count_7_days") { items { id name } } }')
    dene("bos-sorgu", '{ searchPrints2(query: "", limit: 3) { items { id name } } }')
    dene("sayfalama", '{ searchPrints2(query: "box", limit: 3, offset: 3) { items { id name } } }')


if __name__ == "__main__":
    main()
