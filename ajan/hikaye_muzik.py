#!/usr/bin/env python3
"""Hikaye görselini müzikli videoya çevirir (yavaş yakınlaşma + sentezlenmiş, telifsiz ambiyans müziği).

Müzik (dinlendirici: 12 farklı tını, akor dizileri, tonlar, doğa dokuları) tamamen numpy ile sentezlenir (üçüncü kişi müziği yok, telif sorunu yok). Instagram'ın kendi müzik kütüphanesi API ile eklenemediği için müzik videonun içine gömülür.

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

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hikaye as H  # noqa: E402

KOK = H.KOK
# ---------------------------------------------------------------------------------------------
# Dinlendirici müzik kütüphanesi: tamamen numpy ile sentezlenir (örnek/ses dosyası yok → telif sorunu yok).
# Her stil: bir tını (enstrüman), eşlik, bas, isteğe bağlı doku (yağmur, okyanus, plak cızırtısı...) ve hafif ritim.
# Çeşitlilik: stil × akor dizisi × ton × tempo × melodi tohumu → art arda aynı müzik pratikte çıkmaz.
# ---------------------------------------------------------------------------------------------
SR = 44100

STILLER = [
    {"ad": "Keçe piyano", "lead": "piyano", "esl": "pad", "bpm": 72, "doku": "plak", "davul": "yok", "mod": "major", "desen": "melodi"},
    {"ad": "Kalimba sabahı", "lead": "kalimba", "esl": "yayli", "bpm": 84, "doku": "kus", "davul": "yok", "mod": "pentatonik", "desen": "arpej"},
    {"ad": "Rhodes lo-fi", "lead": "rhodes", "esl": "rhodes_akor", "bpm": 76, "doku": "plak", "davul": "lofi", "mod": "dorian", "desen": "melodi"},
    {"ad": "Müzik kutusu", "lead": "kutu", "esl": "pad", "bpm": 66, "doku": "yok", "mod": "major", "desen": "arpej"},
    {"ad": "Naylon gitar", "lead": "gitar", "esl": "gitar_akor", "bpm": 80, "doku": "yagmur", "davul": "yok", "mod": "major", "desen": "arpej"},
    {"ad": "Marimba bahçe", "lead": "marimba", "esl": "pad", "bpm": 90, "doku": "kus", "davul": "hafif", "mod": "pentatonik", "desen": "melodi"},
    {"ad": "Okyanus pad", "lead": "celesta", "esl": "pad", "bpm": 60, "doku": "okyanus", "davul": "yok", "mod": "lidya", "desen": "seyrek"},
    {"ad": "Vibrafon gece", "lead": "vibrafon", "esl": "rhodes_akor", "bpm": 70, "doku": "plak", "davul": "firca", "mod": "dorian", "desen": "melodi"},
    {"ad": "Flüt meditasyon", "lead": "flut", "esl": "pad", "bpm": 62, "doku": "ruzgar", "davul": "yok", "mod": "pentatonik", "desen": "uzun"},
    {"ad": "Arp yağmuru", "lead": "arp", "esl": "yayli", "bpm": 74, "doku": "yagmur", "davul": "yok", "mod": "lidya", "desen": "arpej"},
    {"ad": "Yaylı ve celesta", "lead": "celesta", "esl": "yayli", "bpm": 68, "doku": "yok", "mod": "major", "desen": "melodi"},
    {"ad": "Sıcak lo-fi gitar", "lead": "gitar", "esl": "rhodes_akor", "bpm": 82, "doku": "plak", "davul": "lofi", "mod": "mikso", "desen": "melodi"},
]
TON_KAYMALARI = (0, 5, -3, 2, -5, 7, -2, 4, -4, 1, 3, -1)
# akor dizileri (dereceler, akor türü): sakin ve sıcak diziler
DIZILER = [
    [(0, "maj7"), (5, "maj7"), (9, "min7"), (7, "add9")],      # I – IV – vi – V
    [(9, "min7"), (5, "maj7"), (0, "add9"), (7, "sus2")],      # vi – IV – I – V
    [(2, "min7"), (7, "dom9"), (0, "maj7"), (9, "min7")],      # ii – V – I – vi (caz)
    [(0, "maj7"), (4, "min7"), (9, "min7"), (5, "maj7")],      # I – iii – vi – IV
    [(5, "maj7"), (7, "add9"), (4, "min7"), (9, "min7")],      # IV – V – iii – vi
    [(0, "add9"), (5, "add9"), (0, "add9"), (7, "sus2")],      # I – IV – I – V (folk)
    [(0, "maj7"), (2, "add9"), (5, "maj7"), (0, "maj7")],      # lidya hissi
]
AKOR = {"maj7": (0, 4, 7, 11), "min7": (0, 3, 7, 10), "add9": (0, 4, 7, 14), "sus2": (0, 2, 7, 12), "dom9": (0, 4, 10, 14)}
OLCEK = {"major": (0, 2, 4, 5, 7, 9, 11), "pentatonik": (0, 2, 4, 7, 9), "lidya": (0, 2, 4, 6, 7, 9, 11), "dorian": (0, 2, 3, 5, 7, 9, 10), "mikso": (0, 2, 4, 5, 7, 9, 10)}


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(n):
    return np.arange(n) / SR


def _zarf(n, atak=.005, tau=1.0, birak=None):
    t = _t(n)
    z = np.minimum(1, t / atak) * np.exp(-t / tau)
    if birak:
        z *= np.minimum(1, np.maximum(0, (n / SR - t) / birak))
    return z


def _bant(rng, n, alt, ust):
    x = np.fft.rfft(rng.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR)
    w = np.clip((f - alt) / (.3 * alt + 1), 0, 1) * np.clip((ust - f) / (.3 * ust + 1), 0, 1)
    y = np.fft.irfft(x * w, n); return y / (np.sqrt(np.mean(y * y)) or 1)


# ---------- tınılar (mono parça döndürür) ----------
def e_piyano(f, d):   # keçe piyano: yumuşak tokmak, üst armonikler hızla söner
    n = int((d + 2.5) * SR); t = _t(n); y = np.zeros(n)
    for h in range(1, 9):
        y += np.sin(2 * np.pi * f * h * (1 + .0004 * h * h) * t) / h ** 1.7 * np.exp(-t * (.6 + .55 * h))
    return y * np.minimum(1, t / .008) * .55


def e_rhodes(f, d):   # elektrikli piyano (FM): parlak atak, çan gibi kuyruk, hafif tremolo
    n = int((d + 2.2) * SR); t = _t(n); I = 1.6 * np.exp(-t * 3.2)
    y = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * t)) * np.exp(-t / 1.6) + .18 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / .12)
    return y * np.minimum(1, t / .004) * (1 + .12 * np.sin(2 * np.pi * 4.5 * t)) * .45


def e_kalimba(f, d):   # kalimba: yumuşak ana ton + uyumsuz kısa parıltı
    n = int(2.2 * SR); t = _t(n)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / .9) + .3 * np.sin(2 * np.pi * f * 5.43 * t) * np.exp(-t / .07) + .15 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t / .25)
    return y * np.minimum(1, t / .002) * .5


def e_kutu(f, d):   # müzik kutusu: tiz çan dili
    n = int(2.6 * SR); t = _t(n); y = np.zeros(n)
    for o, a, tau in ((1, 1, 2.0), (2.0, .3, .7), (3.01, .12, .35), (4.17, .07, .18)):
        y += a * np.sin(2 * np.pi * f * o * t) * np.exp(-t / tau)
    return y * np.minimum(1, t / .0015) * .38


def e_gitar(f, d):   # naylon gitar: koparma konumuna göre armonikler, yüksekler önce söner
    n = int((d + 1.8) * SR); t = _t(n); y = np.zeros(n); p = .2
    for h in range(1, 13):
        y += abs(np.sin(np.pi * h * p)) / h ** 1.15 * np.sin(2 * np.pi * f * h * t) * np.exp(-t * (1.1 + .45 * h))
    return y * np.minimum(1, t / .003) * .6


def e_marimba(f, d):   # marimba: tahta tını
    n = int(1.6 * SR); t = _t(n)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / .55) + .45 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t / .09) + .15 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t / .03)
    return y * np.minimum(1, t / .002) * .5


def e_vibrafon(f, d):   # vibrafon: motorlu tremolo, uzun kuyruk
    n = int((d + 2.8) * SR); t = _t(n)
    y = (np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / .5)) * np.exp(-t / 2.3)
    return y * np.minimum(1, t / .003) * (1 + .3 * np.sin(2 * np.pi * 5.2 * t)) * .42


def e_celesta(f, d):   # celesta: yumuşak çan
    n = int(2.4 * SR); t = _t(n)
    y = (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t / .4) + .1 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t / .2)) * np.exp(-t / 1.3)
    return y * np.minimum(1, t / .002) * .42


def e_arp(f, d):   # arp: parlak koparma, uzun sönüm
    n = int(3.0 * SR); t = _t(n); y = np.zeros(n)
    for h in range(1, 11):
        y += np.sin(2 * np.pi * f * h * t) / h ** 1.35 * np.exp(-t * (.45 + .3 * h))
    return y * np.minimum(1, t / .002) * .5


def e_flut(f, d, rng=None):   # flüt: vibrato, nefes gürültüsü, yumuşak atak ve bırakış
    n = int((d + .4) * SR); t = _t(n); vib = 1 + .006 * np.sin(2 * np.pi * 5.1 * t) * np.minimum(1, t / .4)
    faz = 2 * np.pi * f * np.cumsum(vib) / SR
    y = np.sin(faz) + .22 * np.sin(2 * faz) + .06 * np.sin(3 * faz)
    nefes = (rng or np.random.default_rng(1)).standard_normal(n) * .04
    z = np.minimum(1, t / .12) * np.minimum(1, np.maximum(0, (n / SR - t) / .35))
    return (y + nefes) * z * .4


def e_pad(f, d):   # sıcak pad: ayarsız üç ses, yavaş atak
    n = int((d + 1.5) * SR); t = _t(n); y = np.zeros(n)
    for det in (-.004, 0, .0045):
        for h in range(1, 6):
            y += np.sin(2 * np.pi * f * (1 + det) * h * t + h) / h ** 1.6
    return y * np.minimum(1, t / 1.0) * np.minimum(1, np.maximum(0, (n / SR - t) / 1.2)) * .12


def e_yayli(f, d):   # yaylı topluluk: hafif vibrato, yavaş atak
    n = int((d + 1.5) * SR); t = _t(n); y = np.zeros(n)
    for det, vf in ((-.003, 5.3), (.0035, 5.9)):
        faz = 2 * np.pi * f * (1 + det) * np.cumsum(1 + .004 * np.sin(2 * np.pi * vf * t)) / SR
        for h in range(1, 8):
            y += np.sin(h * faz) / h ** 1.25
    return y * np.minimum(1, t / .7) * np.minimum(1, np.maximum(0, (n / SR - t) / 1.0)) * .07


TINI = {"piyano": e_piyano, "rhodes": e_rhodes, "kalimba": e_kalimba, "kutu": e_kutu, "gitar": e_gitar, "marimba": e_marimba,
        "vibrafon": e_vibrafon, "celesta": e_celesta, "arp": e_arp, "flut": e_flut, "pad": e_pad, "yayli": e_yayli}


def _koy(hedef, parca, t0, kazanc=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= len(hedef):
        return
    m = min(len(parca), len(hedef) - i); a = (pan + 1) * np.pi / 4
    hedef[i:i + m, 0] += parca[:m] * kazanc * np.cos(a); hedef[i:i + m, 1] += parca[:m] * kazanc * np.sin(a)


def _doku(tur, n, rng):
    t = _t(n)
    if tur == "yagmur":   # yumuşak yağmur: geniş bant hışırtı + seyrek damla
        y = _bant(rng, n, 900, 7000) * .012
        for _ in range(int(n / SR * 25)):
            k = int(rng.uniform(0, n - 900)); y[k:k + 900] += np.sin(2 * np.pi * rng.uniform(2500, 5000) * _t(900)) * np.exp(-_t(900) / .006) * .025
        return y
    if tur == "okyanus":   # yavaş kabaran dalgalar
        return _bant(rng, n, 120, 1800) * (.35 + .65 * (.5 + .5 * np.sin(2 * np.pi * t / 7.5 - 1.5)) ** 2) * .02
    if tur == "ruzgar":
        return _bant(rng, n, 250, 1500) * (.6 + .4 * np.sin(2 * np.pi * t / 5.3)) * .012
    if tur == "plak":   # plak cızırtısı + hafif hışırtı
        y = _bant(rng, n, 2000, 9000) * .004
        for _ in range(int(n / SR * 14)):
            k = int(rng.uniform(0, n - 60)); y[k:k + 60] += rng.standard_normal(60) * np.exp(-_t(60) / .0008) * .04
        return y
    if tur == "kus":   # uzaktan seyrek kuş cıvıltısı
        y = np.zeros(n)
        for _ in range(int(n / SR / 3) + 1):
            k = int(rng.uniform(0, max(1, n - SR))); m = int(.12 * SR); tt = _t(m); f0 = rng.uniform(2800, 4200)
            for j in range(int(rng.integers(2, 5))):
                s = k + j * int(.15 * SR)
                if s + m < n:
                    y[s:s + m] += np.sin(2 * np.pi * np.cumsum(f0 + 900 * np.sin(2 * np.pi * 14 * tt)) / SR) * np.sin(np.pi * tt / .12) ** 2 * .012
        return y
    return np.zeros(n)


def muzik_dizisi(sure, stil=0, ton=0, tohum=0):
    """(n,2) stereo dizi: dinlendirici, sentezlenmiş müzik."""
    st = STILLER[stil % len(STILLER)]
    rng = np.random.default_rng(1000 + int(tohum))
    n = int((sure + .5) * SR)
    cikis = np.zeros((n, 2))
    bpm = st["bpm"] * float(rng.uniform(.94, 1.06))
    vurus = 60.0 / bpm
    olcu = 4 * vurus
    kok = 57 + ton   # A3 civarı merkez
    dizi = DIZILER[(int(tohum) + stil) % len(DIZILER)]
    olcek = OLCEK[st["mod"]]
    lead, esl = TINI[st["lead"]], st["esl"]
    k = 0
    while k * olcu < sure + .2:
        derece, tur = dizi[k % len(dizi)]
        r = kok + derece - 12 * (derece > 7)
        sesler = [r + x for x in AKOR[tur]]
        t0 = k * olcu
        # eşlik
        if esl in ("pad", "yayli"):
            for m in sesler:
                _koy(cikis, TINI[esl](_hz(m), olcu + .3), t0, 1.0, float(rng.uniform(-.5, .5)))
        elif esl == "rhodes_akor":
            for vv in (0, 2.5):
                for j, m in enumerate(sesler):
                    _koy(cikis, e_rhodes(_hz(m), vurus * 1.5) * .45, t0 + vv * vurus + j * .012, 1.0, -.3 + .2 * j)
        elif esl == "gitar_akor":
            for vv in (0, 2):
                for j, m in enumerate(sesler):
                    _koy(cikis, e_gitar(_hz(m - 12 * (j > 1)), vurus * 2) * .5, t0 + vv * vurus + j * .035, 1.0, -.4 + .25 * j)
        # bas: yumuşak sinüs, kök ve beşli
        for vv, ar in ((0, 0), (2, 7)):
            m = r - 24 + ar; nb = int(vurus * 2 * SR); tb = _t(nb)
            _koy(cikis, np.sin(2 * np.pi * _hz(m) * tb) * np.minimum(1, tb / .02) * np.exp(-tb / 1.2) * .16, t0 + vv * vurus, 1.0, 0)
        # ana tını
        desen = st["desen"]
        if desen == "arpej":
            sira = [0, 1, 2, 3, 2, 1, 3, 2]
            for j in range(8):
                m = sesler[sira[j]] + 12 * (j % 4 == 3)
                _koy(cikis, lead(_hz(m), vurus / 2), t0 + j * vurus / 2, .55, -.45 + .9 * (j % 2))
        elif desen == "seyrek":
            for j in range(3):
                if rng.random() < .8:
                    m = sesler[int(rng.integers(0, 4))] + 12
                    _koy(cikis, lead(_hz(m), vurus), t0 + j * vurus * 1.33 + float(rng.uniform(0, .1)), .5, float(rng.uniform(-.6, .6)))
        elif desen == "uzun":
            for j in range(2):
                m = kok + 12 + olcek[int(rng.integers(0, len(olcek)))] + (derece if rng.random() < .5 else 0)
                m = min(m, kok + 26)
                parca = e_flut(_hz(m), vurus * 1.8, rng) if st["lead"] == "flut" else lead(_hz(m), vurus * 1.8)
                _koy(cikis, parca, t0 + j * vurus * 2, .6, float(rng.uniform(-.3, .3)))
        else:   # melodi: akor tonları + ölçek geçişleri, dinlenmeli ritim
            ritim = [(0, 1), (1, .5), (1.5, .5), (2, 1.5), (3.5, .5)] if rng.random() < .5 else [(0, 1.5), (1.5, .5), (2, 1), (3, 1)]
            onceki = sesler[2] + 12
            for bas_v, uz in ritim:
                if rng.random() < .18:
                    continue   # nefes boşluğu
                if rng.random() < .6:
                    aday = [x + 12 for x in sesler]
                else:
                    aday = [kok + 12 + o for o in olcek] + [kok + 24 + o for o in olcek[:3]]
                m = min(aday, key=lambda x: abs(x - onceki) + rng.uniform(0, 4))
                onceki = m
                _koy(cikis, lead(_hz(m), uz * vurus), t0 + bas_v * vurus, .6, float(rng.uniform(-.25, .25)))
        # hafif ritim
        dv = st.get("davul", "yok")
        if dv in ("lofi", "hafif", "firca"):
            for v in range(4):
                tv = t0 + v * vurus
                if dv == "lofi" and v in (0, 2) or dv == "hafif" and v == 0:
                    nk = int(.35 * SR); tk = _t(nk)
                    _koy(cikis, np.sin(2 * np.pi * np.cumsum(48 + 70 * np.exp(-tk / .03)) / SR) * np.exp(-tk / .13) * .28, tv, 1.0, 0)
                if dv in ("lofi", "firca") and v in (1, 3):
                    nf = int(.25 * SR)
                    _koy(cikis, _bant(rng, nf, 1500, 8000) * np.exp(-_t(nf) / .06) * .05, tv, 1.0, .1)
                if dv == "lofi":
                    nh = int(.06 * SR)
                    _koy(cikis, _bant(rng, nh, 6000, 14000) * np.exp(-_t(nh) / .012) * .025, tv + vurus / 2, 1.0, .3)
        k += 1
    # doku
    if st["doku"] != "yok":
        d = _doku(st["doku"], n, rng)
        cikis[:, 0] += d; cikis[:, 1] += np.roll(d, int(.011 * SR))
    # yankı: sentetik oda/salon (konvolüsyon), stereo genişlik
    ni = int(2.4 * SR); ti = _t(ni)
    ir = np.stack([rng.standard_normal(ni) * np.exp(-ti / .75) for _ in range(2)], axis=1) * np.minimum(1, ti / .03)[:, None]
    ir /= np.sqrt(np.sum(ir ** 2)) / 3.0
    N2 = 1 << (n + ni - 1).bit_length()
    yank = np.stack([np.fft.irfft(np.fft.rfft(cikis[:, c], N2) * np.fft.rfft(ir[:, c], N2), N2)[:n] for c in range(2)], axis=1)
    cikis = cikis * .72 + yank * .38
    t = _t(n)
    cikis *= (np.minimum(1, t / .6) * np.minimum(1, np.maximum(0, (sure - t) / 1.8)))[:, None]
    return cikis[:int(sure * SR)]


def muzik_uret(yol, sure, stil=0, ton=0, tohum=None):
    """Dinlendirici müziği wav olarak yazar ve −16 LUFS'a normalize eder."""
    tohum = (stil * 7 + ton) if tohum is None else tohum
    x = muzik_dizisi(sure, stil, ton, tohum)
    x /= max(1e-6, np.abs(x).max() / .8)
    with tempfile.TemporaryDirectory() as g:
        ham = pathlib.Path(g) / "ham.wav"
        import wave
        with wave.open(str(ham), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
        filtre = f"highpass=f=35,loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.2,afade=t=out:st={max(0.1, sure - 1.2)}:d=1.2,alimiter=limit=0.93"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ham), "-af", filtre, "-ar", str(SR), "-ac", "2", str(yol)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("müzik üretilemedi: " + (r.stderr or "")[-200:])


def muzikli_video(foto, cikti, sure=12, stil=0, ton=0, tohum=None):
    with tempfile.TemporaryDirectory() as g:
        wav = pathlib.Path(g) / "m.wav"
        muzik_uret(wav, sure, stil, ton, tohum)
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
    o["muzik"] = f"Sentezlenmiş müzik: {STILLER[stil]['ad']} (telifsiz, kodla üretildi)"
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
    muzikli_video(foto, KOK / mp4_yolu, sure, stil=stil, ton=ton, tohum=sira)
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
        muzik_uret(g / "m.wav", sure, stil, ton, sira)
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
