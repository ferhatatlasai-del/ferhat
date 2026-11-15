#!/usr/bin/env python3
"""Instagram hesabının güncel durumunu okuyup ajan/hesap_durumu.md dosyasına yazar.

Yalnızca OKUR, hesapta hiçbir şey paylaşmaz ya da değiştirmez.
Gerekli ortam değişkeni: IG_ACCESS_TOKEN  (Instagram API with Instagram Login erişim anahtarı)
Anahtar yoksa sessizce çıkar; ajan eski dosyayla ya da dosyasız çalışmaya devam eder.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
CIKTI = KOK / "ajan" / "hesap_durumu.md"
IG_USER_ID = os.environ.get("IG_USER_ID", "me")
# Anahtar türüne göre iki olası adres denenir (Instagram girişi / Facebook işletme girişi).
ADAYLAR = [
    ("https://graph.instagram.com/v21.0", "me"),
    ("https://graph.facebook.com/v21.0", IG_USER_ID),
]


def al(taban, yol, **parametre):
    parametre["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    url = f"{taban}/{yol}?{urllib.parse.urlencode(parametre)}"
    with urllib.request.urlopen(url, timeout=60) as yanit:
        return json.load(yanit)


def hata_ozeti(e):
    """Meta'nın hata mesajını (anahtarı değil) kısa yazdırır."""
    try:
        h = json.loads(e.read().decode("utf-8")).get("error", {})
        return f"HTTP {e.code} kod={h.get('code')} tür={h.get('type')}: {str(h.get('message'))[:180]}"
    except Exception:
        return f"HTTP {e.code}"


def medya_metrikleri(taban, medya_id):
    """Erişim/kaydetme/paylaşım gibi metrikler. Desteklenmeyen medyada boş döner."""
    for metrikler in ("views,reach,saved,shares", "reach,saved"):
        try:
            veri = al(taban, f"{medya_id}/insights", metric=metrikler)
            return {m["name"]: m["values"][0]["value"] for m in veri.get("data", [])}
        except (urllib.error.HTTPError, KeyError, IndexError):
            continue
    return {}


def olustur(taban, profil, medyalar):
    satirlar = [
        "# Güncel Hesap Durumu",
        "",
        f"(Otomatik çekildi: {datetime.date.today().isoformat()}. Elle düzenleme, üzerine yazılır.)",
        "",
        f"- **Hesap:** @{profil.get('username', '?')}",
        f"- **Takipçi:** {profil.get('followers_count', '?')}",
        f"- **Takip edilen:** {profil.get('follows_count', '?')}",
        f"- **Gönderi sayısı:** {profil.get('media_count', '?')}",
        "",
        "## Son gönderiler (yeniden eskiye)",
    ]
    for m in medyalar:
        metrik = medya_metrikleri(taban, m["id"])
        parcalar = [f"beğeni {m.get('like_count', 0)}", f"yorum {m.get('comments_count', 0)}"]
        ad = {"views": "izlenme", "reach": "erişim", "saved": "kaydetme", "shares": "paylaşım"}
        parcalar += [f"{ad[k]} {v}" for k, v in metrik.items() if k in ad]
        baslik = (m.get("caption") or "").split("\n")[0][:70]
        satirlar.append(f"- {m.get('timestamp', '')[:10]} | {m.get('media_type', '')} | {' · '.join(parcalar)} | \"{baslik}\"")
    return "\n".join(satirlar) + "\n"


def main():
    if not os.environ.get("IG_ACCESS_TOKEN"):
        print("IG_ACCESS_TOKEN tanımlı değil, hesap durumu atlandı.")
        return
    for taban, kimlik in ADAYLAR:
        ad = taban.split("//")[1].split("/")[0]
        try:
            profil = al(taban, kimlik, fields="username,followers_count,follows_count,media_count")
            medya = al(taban, f"{kimlik}/media", fields="id,caption,media_type,like_count,comments_count,timestamp", limit=12)
            CIKTI.write_text(olustur(taban, profil, medya.get("data", [])), encoding="utf-8")
            print(f"Hesap durumu yazıldı ({ad}): {CIKTI.relative_to(KOK)}")
            return
        except urllib.error.HTTPError as e:
            print(f"{ad}: {hata_ozeti(e)}")
        except Exception as e:  # ağ vb.
            print(f"{ad}: alınamadı ({type(e).__name__})")
    print("Hiçbir adres çalışmadı; hesap durumu atlandı.")


if __name__ == "__main__":
    sys.exit(main())
