"""Geçici yetim dal: Instagram'ın indirebilmesi için dosyaları depo geçmişini şişirmeden raw adreste yayınlar.

Tek commit'lik yetim dal olarak zorla yazılır; iş bitince silinir. Kullanım (hikaye.py uzun video parçaları):
    g = yukle({"p1.mp4": yerel1, "p2.mp4": yerel2}, "hikaye-gecici")
    adres = raw_adres("p1.mp4", "hikaye-gecici")  ...  sil(g, "hikaye-gecici")
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("GH_REPO") or ""


def sh(komut, **k):
    return subprocess.run(komut, capture_output=True, text=True, **k)


def uzak_adres():
    return os.environ.get("GIT_UZAK_ADRES") or f"https://x-access-token:{os.environ.get('GITHUB_TOKEN', '')}@github.com/{REPO}.git"


def raw_adres(yol, dal):
    taban = os.environ.get("YAYIN_RAW_TABAN") or f"https://raw.githubusercontent.com/{REPO}/{dal}"
    return f"{taban.rstrip('/')}/{yol}"


def yukle(dosyalar, dal):
    """dosyalar: {depo_yolu: yerel_yol}. Dönen: çalışma dizini (sil() için)."""
    g = pathlib.Path(tempfile.mkdtemp())
    sh(["git", "-C", str(g), "init", "-q"])
    sh(["git", "-C", str(g), "config", "user.name", "hikaye-ajani"])
    sh(["git", "-C", str(g), "config", "user.email", "hikaye-ajani@users.noreply.github.com"])
    for yol, yerel in dosyalar.items():
        hedef = g / yol
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yerel, hedef)
    sh(["git", "-C", str(g), "add", "-A"])
    sh(["git", "-C", str(g), "commit", "-q", "-m", "geçici hikaye parçaları"])
    p = sh(["git", "-C", str(g), "push", "-q", "-f", uzak_adres(), f"HEAD:refs/heads/{dal}"])
    if p.returncode != 0:
        raise RuntimeError("geçici dala yazılamadı: " + (p.stderr or "")[-160:].replace(os.environ.get("GITHUB_TOKEN", "x"), "***"))
    return g


def sil(g, dal):
    try:
        sh(["git", "-C", str(g), "push", "-q", uzak_adres(), "--delete", dal])
    except Exception:
        pass


def hazir_mi(adres, sn=90):
    son = time.time() + sn
    while time.time() < son:
        try:
            with urllib.request.urlopen(urllib.request.Request(adres, headers={"Range": "bytes=0-0"}), timeout=20) as y:
                if y.status in (200, 206):
                    return True
        except Exception:
            pass
        time.sleep(4)
    return False
