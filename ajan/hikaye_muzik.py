#!/usr/bin/env python3
"""Hikaye görselini müzikli videoya çevirir (yavaş yakınlaşma + sentezlenmiş, telifsiz ambiyans müziği).

Müzik (tempolu vuruş, bas, akor ve arpej) tamamen FFmpeg ile üretilir (üçüncü kişi müziği yok, telif sorunu yok). Instagram'ın kendi müzik kütüphanesi API ile eklenemediği için müzik videonun içine gömülür.

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
# Notaların frekansları (Hz)
N = {"C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31, "G2": 98.00, "A2": 110.00, "Bb2": 116.54, "B2": 123.47,
     "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00, "A3": 220.00, "Bb3": 233.08, "B3": 246.94,
     "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "Bb4": 466.16}

# Stil sırası: enerji dönüşümlü (hareketli, sakin, hareketli, ambiyans...). Her yeni hikaye sıradakini alır; böylece art arda aynı müzik çıkmaz.
# profil: "hareketli" (vuruş, el çırpma, hi-hat, bas, arpej), "yavas" (lo-fi: yumuşak vuruş, uzun bas, sıcak 7'li akorlar), "ambiyans" (davulsuz, geniş pad)
# akor: 4 akorluk döngü; (bas notası, (4 akor sesi))
STILLER = [
    {"ad": "Pop enerjik", "profil": "hareketli", "bpm": 112,
     "akor": [("A2", ("A3", "C4", "E4", "G4")), ("F2", ("F3", "A3", "C4", "E4")), ("C3", ("C4", "E4", "G4", "B3")), ("G2", ("G3", "B3", "D4", "F4"))]},
    {"ad": "Lo-fi sakin", "profil": "yavas", "bpm": 78,
     "akor": [("C3", ("C4", "E4", "G4", "B3")), ("A2", ("A3", "C4", "E4", "G4")), ("D3", ("D4", "F4", "A3", "C4")), ("G2", ("G3", "B3", "D4", "F4"))]},
    {"ad": "Parlak neşeli", "profil": "hareketli", "bpm": 118,
     "akor": [("C3", ("C4", "E4", "G4", "B3")), ("G2", ("G3", "B3", "D4", "F4")), ("A2", ("A3", "C4", "E4", "G4")), ("F2", ("F3", "A3", "C4", "E4"))]},
    {"ad": "Ambiyans", "profil": "ambiyans", "bpm": 64,
     "akor": [("F2", ("F3", "A3", "C4", "E4")), ("G2", ("G3", "B3", "D4", "E4")), ("E2", ("E3", "G3", "B3", "D4")), ("A2", ("A3", "C4", "E4", "G4"))]},
    {"ad": "Dans ritmi", "profil": "hareketli", "bpm": 108,
     "akor": [("D3", ("D4", "F4", "A4", "C4")), ("Bb2", ("Bb3", "D4", "F4", "A3")), ("F2", ("F3", "A3", "C4", "E4")), ("C3", ("C4", "E4", "G4", "B3"))]},
    {"ad": "Chill gece", "profil": "yavas", "bpm": 84,
     "akor": [("A2", ("A3", "C4", "E4", "G4")), ("F2", ("F3", "A3", "C4", "E4")), ("C3", ("C4", "E4", "G4", "B3")), ("G2", ("G3", "B3", "D4", "F4"))]},
]
# Her tam turdan sonra tüm müzik farklı bir tona kayar (yarım ton sayısı); aynı stil tekrar gelse bile farklı duyulur
TON_KAYMALARI = (0, 2, -2, 3, -3, 5)


def _sec(k, degerler):
    """k (0..3 ölçü numarası ifadesi) değerine göre if zinciri."""
    return f"if(lt({k},1),{degerler[0]},if(lt({k},2),{degerler[1]},if(lt({k},3),{degerler[2]},{degerler[3]})))"


def muzik_ifadesi(stil=0, ton=0):
    """aevalsrc ifadesi (profil ve ton kaymasına göre). Her ses kendi fazından başlar (tık sesi olmaz). Tamamen sentezlenir: telifsiz."""
    st = STILLER[stil % len(STILLER)]
    m = 2 ** (ton / 12.0)
    hz = lambda ad: round(N[ad] * m, 3)
    b = round(60.0 / st["bpm"], 5)
    k = f"mod(floor(t/({4 * b})),4)"
    bas_hz = _sec(k, [hz(a[0]) for a in st["akor"]])
    ses = [_sec(k, [hz(a[1][i]) for a in st["akor"]]) for i in range(4)]
    tb = f"mod(t,{b})"
    profil = st["profil"]
    if profil == "hareketli":
        kick = f"0.55*sin(2*PI*(45*{tb}+3.6*(1-exp(-25*{tb}))))*exp(-9*{tb})"
        clap = f"0.30*(2*random(0)-1)*exp(-20*mod(t+{b},{2 * b}))"
        hat = f"0.10*(2*random(1)-1)*exp(-45*mod(t+{b / 2},{b}))"
        hat16 = f"0.04*(2*random(2)-1)*exp(-60*mod(t,{b / 2}))"
        sek = f"mod(t,{b / 2})"
        bas = f"0.30*sin(2*PI*{bas_hz}*{sek})*exp(-3.2*{sek})"
        nefes = f"(0.55+0.45*(1-exp(-7*{tb})))"
        pad = f"{nefes}*(" + "+".join(f"0.04*sin(2*PI*{x}*t)" for x in ses[:3]) + ")"
        adim = f"mod(t,{b / 4})"
        ind = f"mod(floor(t/{b / 4}),4)"
        nota = f"if(lt({ind},1),{ses[0]},if(lt({ind},2),{ses[1]},if(lt({ind},3),{ses[2]},{ses[1]})))"
        lead = f"(0.085*sin(2*PI*2*{nota}*{adim})+0.03*sin(4*PI*2*{nota}*{adim}))*exp(-11*{adim})"
        parcalar = [kick, clap, hat, hat16, bas, pad, lead]
    elif profil == "yavas":
        iki = f"mod(t,{2 * b})"
        kick = f"0.34*sin(2*PI*(42*{iki}+2.6*(1-exp(-22*{iki}))))*exp(-7*{iki})"
        firca = f"0.07*(2*random(0)-1)*exp(-14*mod(t+{b},{2 * b}))"
        hat = f"0.035*(2*random(1)-1)*exp(-50*mod(t+{b / 2},{b}))"
        bas = f"0.30*sin(2*PI*{bas_hz}*{iki})*exp(-1.1*{iki})"
        tremolo = "(0.7+0.3*sin(2*PI*0.18*t))"
        pad = f"{tremolo}*(" + "+".join(f"0.042*sin(2*PI*{x}*t)" for x in ses) + ")"
        adim = f"mod(t,{b})"
        ind = f"mod(floor(t/{b}),4)"
        nota = f"if(lt({ind},1),{ses[0]},if(lt({ind},2),{ses[2]},if(lt({ind},3),{ses[1]},{ses[3]})))"
        lead = f"(0.075*sin(2*PI*2*{nota}*{adim})+0.02*sin(4*PI*2*{nota}*{adim}))*exp(-4.5*{adim})"
        parcalar = [kick, firca, hat, bas, pad, lead]
    else:   # ambiyans: davulsuz, geniş ve yavaş
        zarf = f"(0.65+0.35*sin(2*PI*t/{8 * b}))"
        pad = f"{zarf}*(" + "+".join(f"{0.05 - i * 0.004}*sin(2*PI*{x}*t)" for i, x in enumerate(ses)) + ")"
        bas = f"0.12*sin(2*PI*{bas_hz}*t)*(0.7+0.3*sin(2*PI*t/{4 * b}))"
        ik = f"mod(t,{2 * b})"
        ind = f"mod(floor(t/{2 * b}),4)"
        nota = f"if(lt({ind},1),{ses[3]},if(lt({ind},2),{ses[1]},if(lt({ind},3),{ses[2]},{ses[0]})))"
        parilti = f"(0.07*sin(2*PI*4*{nota}*{ik})+0.03*sin(2*PI*2*{nota}*{ik}))*exp(-2.2*{ik})"
        parcalar = [pad, bas, parilti]
    return "+".join(parcalar)


def muzik_uret(yol, sure, stil=0, ton=0):
    ifade = muzik_ifadesi(stil, ton)
    filtre = (f"highpass=f=30,lowpass=f=9500,aecho=0.8:0.5:180:0.18,loudnorm=I=-14:TP=-1.5:LRA=9,"
              f"afade=t=in:d=0.15,afade=t=out:st={max(0.1, sure - 1.5)}:d=1.5,alimiter=limit=0.93")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{ifade}':s=44100:d={sure}", "-af", filtre,
                        "-ac", "2", str(yol)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("müzik üretilemedi: " + (r.stderr or "")[-200:])


def muzikli_video(foto, cikti, sure=12, stil=0, ton=0):
    with tempfile.TemporaryDirectory() as g:
        wav = pathlib.Path(g) / "m.wav"
        muzik_uret(wav, sure, stil, ton)
        kare = int(sure * 30)
        filtre = (f"[0:v]scale=2160:-1,zoompan=z='min(1+0.0007*on,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={kare}:s=1080x1920:fps=30,"
                  f"format=yuv420p[v]")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(foto), "-i", str(wav), "-filter_complex", filtre,
                            "-map", "[v]", "-map", "1:a", "-t", str(sure), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(cikti)], capture_output=True, text=True)
        if r.returncode != 0 or not pathlib.Path(cikti).exists():
            raise RuntimeError("video hazırlanamadı: " + (r.stderr or "")[-300:])


def siradaki_stil():
    """Kuyruktaki ve yayınlanmış tüm hikayelerin en büyük müzik sırasından devam eder: art arda aynı müzik çıkmaz, enerji dönüşümlü olur."""
    en_buyuk = -1
    for f in H.KUYRUK.glob("h*.json"):
        try:
            en_buyuk = max(en_buyuk, int(json.loads(f.read_text(encoding="utf-8")).get("muzik_sira", -1)))
        except Exception:
            pass
    sira = en_buyuk + 1
    return sira, sira % len(STILLER), TON_KAYMALARI[(sira // len(STILLER)) % len(TON_KAYMALARI)]


def _kaydet(yol, o, sira, stil, ton):
    o["muzik"] = f"Sentezlenmiş müzik: {STILLER[stil]['ad']} (telifsiz, FFmpeg ile üretildi)"
    o["muzik_sira"] = sira
    o["muzik_stil"] = STILLER[stil]["ad"]
    o["muzik_ton"] = ton
    yol.write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")


def kayit_donustur(kimlik, sure=12):
    yol = H.KUYRUK / f"{kimlik}.json"
    o = json.loads(yol.read_text(encoding="utf-8"))
    if o.get("durum") not in ("planli", "onay_bekliyor"):
        raise SystemExit(f"{kimlik} dönüştürülemez (durum: {o.get('durum')})")
    if o.get("tur") == "video":
        raise SystemExit(f"{kimlik} zaten video")
    foto = KOK / o["gorsel"]
    mp4_yolu = f"hikaye/gorseller/{kimlik}.mp4"
    sira, stil, ton = siradaki_stil()
    muzikli_video(foto, KOK / mp4_yolu, sure, stil=stil, ton=ton)
    b = H.video_bilgi(KOK / mp4_yolu)
    print(f"Video: {b}; Instagram için uygun (olduğu gibi): {H.video_uygun_mu(b)}; müzik: {STILLER[stil]['ad']} ({ton:+d} ton)")
    o["tur"] = "video"
    o["gorsel"] = mp4_yolu
    _kaydet(yol, o, sira, stil, ton)
    foto.unlink(missing_ok=True)
    return o


def muzigi_yenile(kimlik, sure=12):
    """Zaten müzikli video olan (yayınlanmamış) hikayenin yalnızca sesini sıradaki stille değiştirir (görüntüye dokunmaz)."""
    yol = H.KUYRUK / f"{kimlik}.json"
    o = json.loads(yol.read_text(encoding="utf-8"))
    if o.get("durum") not in ("planli", "onay_bekliyor") or o.get("tur") != "video":
        raise SystemExit(f"{kimlik}: yenilenemez (durum/tür uygun değil)")
    mp4 = KOK / o["gorsel"]
    sira, stil, ton = siradaki_stil()
    with tempfile.TemporaryDirectory() as g:
        g = pathlib.Path(g)
        muzik_uret(g / "m.wav", sure, stil, ton)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-i", str(g / "m.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", str(sure), "-movflags", "+faststart", str(g / "o.mp4")], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ses değiştirilemedi: " + (r.stderr or "")[-200:])
        (g / "o.mp4").replace(mp4)
    _kaydet(yol, o, sira, stil, ton)
    print(f"{kimlik}: müzik -> {STILLER[stil]['ad']} ({ton:+d} ton)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hikaye", required=True)
    ap.add_argument("--yenile", action="store_true", help="zaten video olan hikayenin yalnızca müziğini sıradaki stille değiştir")
    ap.add_argument("--sure", type=int, default=12)
    a = ap.parse_args()
    (muzigi_yenile if a.yenile else kayit_donustur)(a.hikaye, max(5, min(a.sure, 20)))


if __name__ == "__main__":
    main()
