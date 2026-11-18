#!/usr/bin/env python3
"""Hikaye görselini müzikli videoya çevirir (yavaş yakınlaşma + sentezlenmiş, telifsiz ambiyans müziği).

Müzik tamamen FFmpeg ile üretilir (üçüncü kişi müziği yok, telif sorunu yok). Instagram'ın kendi müzik kütüphanesi API ile eklenemediği için müzik videonun içine gömülür.

Kullanım:
    python3 ajan/hikaye_muzik.py --hikaye h20261118-033530-c7l [--sure 12]
Kuyruk kaydı yerinde güncellenir (tur=video, gorsel=mp4); foto silinir.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402

KOK = H.KOK
SENTEZ_SAYILARI = {0: (0, 3, 7, 10, 12, 10, 7, 3), 1: (0, 5, 7, 12, 7, 5, 3, 0)}


def muzik_ifadesi(desen=0):
    """aevalsrc ifadesi: sakin pad (Am7) + hafif arpej + yumuşak vuruş. Her nota kendi fazından başlar (tık sesi olmaz)."""
    s = SENTEZ_SAYILARI.get(desen, SENTEZ_SAYILARI[0])
    def adim(i):
        return f"lt(mod(floor(t*2),8),{i + 1})"
    ofs = str(s[7])
    for i in range(6, -1, -1):
        ofs = f"if({adim(i)},{s[i]},{ofs})"
    arp_f = f"(440*pow(2,({ofs})/12))"
    pad = ("0.060*sin(2*PI*110*t)+0.045*sin(2*PI*164.81*t)+0.040*sin(2*PI*220*t)"
           "+0.035*sin(2*PI*261.63*t)*(0.6+0.4*sin(2*PI*0.20*t))+0.028*sin(2*PI*329.63*t)*(0.6+0.4*sin(2*PI*0.30*t+1))")
    arp = f"(0.10*sin(2*PI*{arp_f}*mod(t,0.5))+0.035*sin(4*PI*{arp_f}*mod(t,0.5)))*exp(-6*mod(t,0.5))"
    vurus = "0.16*sin(2*PI*(48+70*exp(-22*mod(t,1)))*mod(t,1))*exp(-9*mod(t,1))"
    return f"{pad}+{arp}+{vurus}"


def muzik_uret(yol, sure, desen=0):
    ifade = muzik_ifadesi(desen)
    filtre = f"lowpass=f=5200,aecho=0.8:0.55:320:0.22,afade=t=in:d=0.8,afade=t=out:st={max(0.1, sure - 2.0)}:d=2.0,volume=5.0,alimiter=limit=0.9"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{ifade}':s=44100:d={sure}", "-af", filtre,
                        "-ac", "2", str(yol)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("müzik üretilemedi: " + (r.stderr or "")[-200:])


def muzikli_video(foto, cikti, sure=12, desen=0):
    with tempfile.TemporaryDirectory() as g:
        wav = pathlib.Path(g) / "m.wav"
        muzik_uret(wav, sure, desen)
        kare = int(sure * 30)
        filtre = (f"[0:v]scale=2160:-1,zoompan=z='min(1+0.0007*on,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s=1080x1920:fps=30,"
                  f"format=yuv420p[v]")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(foto), "-i", str(wav), "-filter_complex", filtre,
                            "-map", "[v]", "-map", "1:a", "-t", str(sure), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(cikti)], capture_output=True, text=True)
        if r.returncode != 0 or not pathlib.Path(cikti).exists():
            raise RuntimeError("video hazırlanamadı: " + (r.stderr or "")[-300:])


def kayit_donustur(kimlik, sure=12):
    yol = H.KUYRUK / f"{kimlik}.json"
    o = json.loads(yol.read_text(encoding="utf-8"))
    if o.get("durum") not in ("planli", "onay_bekliyor"):
        raise SystemExit(f"{kimlik} dönüştürülemez (durum: {o.get('durum')})")
    if o.get("tur") == "video":
        raise SystemExit(f"{kimlik} zaten video")
    foto = KOK / o["gorsel"]
    mp4_yolu = f"hikaye/gorseller/{kimlik}.mp4"
    muzikli_video(foto, KOK / mp4_yolu, sure, desen=len(kimlik) % 2)
    b = H.video_bilgi(KOK / mp4_yolu)
    print(f"Video: {b}; Instagram için uygun (olduğu gibi): {H.video_uygun_mu(b)}")
    o["tur"] = "video"
    o["gorsel"] = mp4_yolu
    o["muzik"] = "Sentezlenmiş ambiyans (telifsiz, FFmpeg ile üretildi)"
    yol.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    foto.unlink(missing_ok=True)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hikaye", required=True)
    ap.add_argument("--sure", type=int, default=12)
    a = ap.parse_args()
    kayit_donustur(a.hikaye, max(5, min(a.sure, 20)))


if __name__ == "__main__":
    main()
