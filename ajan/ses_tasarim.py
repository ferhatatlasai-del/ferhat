#!/usr/bin/env python3
"""Ses tasarımı: videonun tüm müziğini, geçiş/vurgu seslerini ve ortam atmosferini kodla SENTEZLER (numpy; örnek/ses kütüphanesi yok).

Katmanlar
  - müzik: Am-F-C-G ilerlemeli pad (toplamsal sentez), alt bas + vuruş, hi-hat, arpej + eko, hafif yankı (konvolüsyon)
  - atmosfer: 3D yazıcı ortamı (step motor çıtırtısı, fan uğultusu)
  - efektler: geçiş "whoosh" + darbe + yükseliş, vurgu "pop", çan "ding", uyarı, tık, fan sönmesi, sprey, silme, parıltı
  - miksaj: konuşma varsa müzik yan zincirle (sidechain) kısılır; efektler kısılmaz; sonunda ffmpeg ile −14 LUFS'a normalize edilir

Her şey tohumludur (deterministik): aynı plan aynı sesi üretir.
"""
import json
import pathlib
import subprocess
import sys
import wave

import numpy as np

SR = 44100
BPM = 96.0
BEAT = 60.0 / BPM


# ---------- temel yapı taşları ----------

def _zaman(n):
    return np.arange(n, dtype=np.float64) / SR


def _ilmek(rng, n):
    return rng.standard_normal(n)


def bant_gurultu(rng, n, alt, ust):
    """FFT ile bant sınırlı beyaz gürültü (birim RMS)."""
    x = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    w = np.clip((f - alt) / (0.25 * alt + 1), 0, 1) * np.clip((ust - f) / (0.25 * ust + 1), 0, 1)
    y = np.fft.irfft(x * w, n)
    r = np.sqrt(np.mean(y * y)) or 1.0
    return y / r


def _zarf_ustel(n, tau, atak=0.003):
    t = _zaman(n)
    return np.exp(-t / tau) * (1 - np.exp(-t / atak))


def _pan(x, p):
    """mono → stereo; p: -1 sol … +1 sağ (sabit güç)."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def _yerlestir(hedef, parca, t0):
    i = int(round(t0 * SR))
    if i >= hedef.shape[0] or i + parca.shape[0] <= 0:
        return
    a = max(0, -i)
    b = min(parca.shape[0], hedef.shape[0] - i)
    hedef[i + a:i + b] += parca[a:b]


def _nota(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------- efektler (stereo parça döndürür; sıfır an = olayın tepe noktasından "ONCE" kadar önce DEĞİL, parçanın başı) ----------

def fx_whoosh(rng, sure=0.9, tepe=0.5, yon=1):
    n = int(sure * SR)
    t = _zaman(n) / sure
    K = 12
    merkezler = np.geomspace(220, 7000, K)
    y = np.zeros(n)
    for k in range(K):
        gur = bant_gurultu(rng, n, merkezler[k] / 1.35, merkezler[k] * 1.35)
        c_yuk = 0.12 + (tepe - 0.12) * k / (K - 1)       # yükselen süpürme (tepeye doğru)
        c_in = tepe + (1 - tepe) * (K - 1 - k) / (K - 1) * 0.9 + 0.04   # sonra alçalan kuyruk
        sg = 0.075 + 0.02 * k / K
        zarf = np.exp(-0.5 * ((t - c_yuk) / sg) ** 2) + 0.55 * np.exp(-0.5 * ((t - c_in) / (sg * 1.5)) ** 2)
        y += gur * zarf
    y *= 0.17 * np.minimum(1, t / 0.04) * np.minimum(1, (1 - t) / 0.2)
    p = np.linspace(-0.85 * yon, 0.85 * yon, n)
    a = (p + 1) * np.pi / 4
    return np.stack([y * np.cos(a), y * np.sin(a)], axis=1)


def fx_darbe(rng, sure=1.6, guc=1.0):
    n = int(sure * SR)
    t = _zaman(n)
    f = 36 + 80 * np.exp(-t / 0.10)
    faz = 2 * np.pi * np.cumsum(f) / SR
    alt = np.sin(faz) * np.exp(-t / 0.55) * (1 - np.exp(-t / 0.004))
    gur = bant_gurultu(rng, n, 80, 3500) * np.exp(-t / 0.16) * 0.55
    catlak = bant_gurultu(rng, n, 3000, 14000) * np.exp(-t / 0.035) * 0.3
    y = (alt * 0.95 + gur + catlak) * guc * 0.7
    return _pan(y, 0)


def fx_yukselis(rng, sure=0.9):
    n = int(sure * SR)
    t = _zaman(n) / sure
    y = bant_gurultu(rng, n, 1800, 11000) * (t ** 2.2) * 0.2
    ton = np.sin(2 * np.pi * np.cumsum(220 + 900 * t ** 2) / SR) * (t ** 2) * 0.06
    s = (y + ton) * np.minimum(1, (1 - t) / 0.03 + 0.0)
    return _pan(s, 0)


def fx_pop(rng, f0=760, guc=1.0):
    n = int(0.22 * SR)
    t = _zaman(n)
    f = f0 + 780 * (1 - np.exp(-t / 0.03))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.055) * (1 - np.exp(-t / 0.002))
    s += 0.35 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR) * np.exp(-t / 0.03)
    s += 0.25 * bant_gurultu(rng, n, 2500, 9000) * np.exp(-t / 0.008)
    return _pan(s * 0.33 * guc, 0)


def fx_ding(rng, f=1318.5, guc=1.0, pan=0.0):
    n = int(1.4 * SR)
    t = _zaman(n)
    y = np.zeros(n)
    for oran, a, tau in ((1, 1, 0.9), (2.76, .45, .5), (5.4, .22, .28), (8.9, .1, .15)):
        y += a * np.sin(2 * np.pi * f * oran * t) * np.exp(-t / tau)
    y *= (1 - np.exp(-t / 0.002)) * 0.28 * guc
    return _pan(y, pan)


def fx_uyari(rng, guc=1.0):
    n = int(0.62 * SR)
    t = _zaman(n)
    y = np.zeros(n)
    for k, f in enumerate((349.0, 262.0)):
        b = int((0.0 + k * 0.28) * SR)
        m = int(0.2 * SR)
        tt = _zaman(m)
        s = sum(np.sin(2 * np.pi * f * h * tt) / h for h in (1, 3, 5, 7)) * np.exp(-tt / 0.2)
        s *= np.minimum(1, tt / 0.004) * np.minimum(1, (0.2 - tt) / 0.03)
        y[b:b + m] += s * 0.2
    return _pan(y * guc, 0)


def fx_tik(rng, guc=1.0, f=2100):
    n = int(0.06 * SR)
    t = _zaman(n)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.006) + 0.5 * bant_gurultu(rng, n, 3000, 9000) * np.exp(-t / 0.004)
    return _pan(y * 0.16 * guc, 0.1)


def fx_fan_son(rng, sure=1.9):
    n = int(sure * SR)
    t = _zaman(n)
    d = t / sure
    frot = 46 * (1 - d) ** 1.6
    faz = 2 * np.pi * np.cumsum(frot) / SR
    gur = bant_gurultu(rng, n, 350, 3200)
    y = gur * (0.55 + 0.45 * np.sin(faz)) * (1 - d) ** 1.2 * np.minimum(1, t / 0.05) * 0.2
    ton = np.sin(2 * np.pi * np.cumsum(260 * (1 - d) ** 1.4 + 40) / SR) * (1 - d) * 0.05
    return _pan(y + ton, 0.2)


def fx_sprey(rng, sure=0.9):
    n = int(sure * SR)
    t = _zaman(n) / sure
    g = bant_gurultu(rng, n, 3500, 13000)
    z = np.zeros(n)
    for c in (0.18, 0.5, 0.78):
        z += np.exp(-0.5 * ((t - c) / 0.1) ** 2)
    return _pan(g * np.minimum(1, z) * 0.17 * np.minimum(1, t / 0.03) * np.minimum(1, (1 - t) / 0.1), -0.4)


def fx_silme(rng, yon=1, sure=0.45):
    n = int(sure * SR)
    t = _zaman(n) / sure
    g = bant_gurultu(rng, n, 1200, 6500) * np.sin(np.pi * t) ** 2
    p = np.linspace(-0.6 * yon, 0.6 * yon, n)
    a = (p + 1) * np.pi / 4
    y = g * 0.16
    return np.stack([y * np.cos(a), y * np.sin(a)], axis=1)


def fx_parilti(rng, guc=1.0):
    n = int(2.0 * SR)
    y = np.zeros((n, 2))
    for k, m in enumerate((81, 84, 88, 91, 96)):
        _yerlestir(y, fx_ding(rng, _nota(m), 0.55 * guc, pan=-0.6 + 0.3 * k), 0.085 * k)
    return y


def fx_yukselen_ton(rng, sure=1.4, guc=1.0):
    n = int(sure * SR)
    t = _zaman(n) / sure
    f = 330 * 2 ** (1.7 * t)
    y = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR)) * (t ** 1.3) * 0.11 * guc
    y *= np.minimum(1, (1 - t) / 0.05)
    return _pan(y, 0)


FX = {
    'gecis': lambda r: fx_whoosh(r, 0.9, 0.5),
    'darbe': lambda r: fx_darbe(r),
    'yukselis': lambda r: fx_yukselis(r),
    'pop': lambda r: fx_pop(r),
    'ding': lambda r: fx_ding(r),
    'ding_alt': lambda r: fx_ding(r, 987.8, 0.9),
    'uyari': lambda r: fx_uyari(r),
    'tik': lambda r: fx_tik(r),
    'fan_son': lambda r: fx_fan_son(r),
    'sprey': lambda r: fx_sprey(r),
    'silme': lambda r: fx_silme(r, 1),
    'silme2': lambda r: fx_silme(r, -1),
    'parilti': lambda r: fx_parilti(r),
    'yukselen_ton': lambda r: fx_yukselen_ton(r),
}
# bir efektin "tepe noktası" parçanın başından kaç saniye sonra? (olay zamanı tepe noktasına hizalanır)
TEPE = {'gecis': 0.5 * 0.9, 'yukselis': 0.9}   # yükseliş süresi olaydan gelir (3. eleman)


# ---------- müzik ----------

AKORLAR = [  # (bas MIDI, pad sesleri)
    (45, [57, 60, 64, 67]),   # Am7
    (41, [53, 57, 60, 64]),   # Fmaj7
    (48, [55, 60, 64, 67]),   # C
    (43, [55, 59, 62, 66]),   # G
]
AKOR_SURESI = 8 * BEAT   # 2 ölçü
# Her videoda farklı müzik: konuya göre seçilen akor dizisi, ton ve tempo (bkz. muzik_ayarla)
DIZI_SECENEKLERI = [
    [(45, [57, 60, 64, 67]), (41, [53, 57, 60, 64]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 66])],   # Am7 F C G
    [(48, [55, 60, 64, 71]), (45, [57, 60, 64, 67]), (41, [53, 57, 60, 65]), (43, [55, 59, 62, 67])],   # Cmaj7 Am7 F G
    [(50, [57, 62, 65, 69]), (46, [58, 62, 65, 69]), (41, [53, 57, 60, 65]), (48, [55, 60, 64, 67])],   # Dm Bb F C
    [(40, [55, 59, 64, 67]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 67]), (50, [57, 62, 66, 69])],   # Em C G D
    [(41, [57, 60, 64, 65]), (43, [55, 59, 62, 67]), (45, [57, 60, 64, 69]), (40, [55, 59, 64, 67])],   # Fmaj7 G Am Em
]


def muzik_ayarla(tohum):
    """Akor dizisini, tonu ve tempoyu tohuma göre seçer (aynı konu aynı müziği, farklı konular farklı müziği verir)."""
    global AKORLAR, BPM, BEAT, AKOR_SURESI
    r = np.random.default_rng(int(tohum))
    dizi = DIZI_SECENEKLERI[int(r.integers(0, len(DIZI_SECENEKLERI)))]
    kay = int(r.integers(-3, 4))
    AKORLAR = [(b + kay, [n + kay for n in ns]) for b, ns in dizi]
    BPM = float(r.uniform(88, 106))
    BEAT = 60.0 / BPM
    AKOR_SURESI = 8 * BEAT


def _pad(rng, sure):
    n = int((sure + 2) * SR)
    cikis = np.zeros((n, 2))
    k = 0
    while k * AKOR_SURESI < sure + 1:
        bas, notlar = AKORLAR[k % len(AKORLAR)]
        t0 = k * AKOR_SURESI - 0.9
        dur = AKOR_SURESI + 1.8
        a = int(max(0, t0) * SR)
        m = int(dur * SR)
        m = min(m, n - a)
        if m <= 0:
            break
        t = _zaman(m)
        yerel = t + max(0, t0) - t0
        zarf = np.minimum(1, yerel / 1.4) ** 2 * np.minimum(1, (dur - yerel) / 1.4) ** 2
        for nt in notlar:
            f = _nota(nt)
            for ch, det in ((0, 0.9985), (1, 1.0015)):
                y = np.zeros(m)
                for h in range(1, 7):
                    y += np.sin(2 * np.pi * f * det * h * t + h * 0.7 + nt) / (h ** 1.35)
                y *= 0.5 + 0.5 * (0.85 + 0.15 * np.sin(2 * np.pi * 0.17 * (t + a / SR) + nt))
                cikis[a:a + m, ch] += y * zarf * 0.055
        k += 1
    return cikis[:int(sure * SR)]


def _bas_vurus(rng, sure):
    n = int(sure * SR)
    y = np.zeros((n, 2))
    ol = int(BEAT * 8 * 0 + 0)
    # vuruş (kick): 1. ve 3. vuruş; bas notaları: 1. vuruş + 2'nin "ve"si
    kick_n = int(0.4 * SR)
    t = _zaman(kick_n)
    f = 46 + 90 * np.exp(-t / 0.045)
    kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16) * (1 - np.exp(-t / 0.002))
    kick += 0.25 * bant_gurultu(rng, kick_n, 1500, 6000) * np.exp(-t / 0.006)
    bar = 0
    while bar * 4 * BEAT < sure:
        bas, _ = AKORLAR[(bar // 2) % len(AKORLAR)]
        b0 = bar * 4 * BEAT
        for bt in (0, 2):
            ks = b0 + bt * BEAT
            if ks >= 1.0:   # ilk saniyede sade giriş
                _yerlestir(y, _pan(kick * 0.5, 0), ks)
        for ofs in (0, 2.5):
            bn = int(0.5 * SR)
            tt = _zaman(bn)
            f0 = _nota(bas - 12)
            yb = (np.sin(2 * np.pi * f0 * tt) + 0.3 * np.sin(2 * np.pi * f0 * 2 * tt)) * np.exp(-tt / 0.32) * np.minimum(1, tt / 0.01)
            _yerlestir(y, _pan(yb * 0.3, 0), b0 + ofs * BEAT)
        bar += 1
    return y


def _hihat(rng, sure):
    n = int(sure * SR)
    y = np.zeros((n, 2))
    kisa = bant_gurultu(rng, int(0.09 * SR), 7000, 16000) * _zarf_ustel(int(0.09 * SR), 0.018, 0.001)
    acik = bant_gurultu(rng, int(0.3 * SR), 6000, 15000) * _zarf_ustel(int(0.3 * SR), 0.09, 0.001)
    k = 0
    while k * BEAT / 2 < sure:
        t0 = k * BEAT / 2
        if k % 2 == 1 and t0 > 2.0:
            _yerlestir(y, _pan((acik if k % 8 == 7 else kisa) * 0.05, 0.3 if k % 4 == 1 else -0.3), t0)
        k += 1
    return y


def _arpej(rng, sure):
    n = int(sure * SR)
    ham = np.zeros((n, 2))
    desen = [0, 2, 1, 3, 2, 3, 1, 2]
    k = 0
    pn = int(0.7 * SR)
    t = _zaman(pn)
    while k * BEAT / 2 < sure:
        t0 = k * BEAT / 2
        _, notlar = AKORLAR[int(t0 // AKOR_SURESI) % len(AKORLAR)]
        if t0 >= 3.0 and (k % 8) not in (7,):
            m = notlar[desen[k % 8]] + 12
            f = _nota(m)
            s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t / 0.08) + 0.15 * np.sin(2 * np.pi * f * 3 * t)) * np.exp(-t / 0.2) * (1 - np.exp(-t / 0.003))
            _yerlestir(ham, _pan(s * 0.075, -0.5 if k % 2 else 0.5), t0)
        k += 1
    # nokta sekizlik eko (3 vuruş)
    y = ham.copy()
    for i, (gec, g) in enumerate(((0.75 * BEAT, 0.42), (1.5 * BEAT, 0.2))):
        d = int(gec * SR)
        y[d:] += ham[:n - d][:, ::-1] * g
    return y


def _yanki(x, rng, tau=0.55, sure=1.4, karisim=0.22):
    n = int(sure * SR)
    t = _zaman(n)
    ir = np.stack([rng.standard_normal(n) * np.exp(-t / tau) for _ in range(2)], axis=1)
    ir *= np.minimum(1, t / 0.02)[:, None]
    ir /= np.sqrt(np.sum(ir ** 2)) / 2.5
    boy = x.shape[0] + n
    N = 1 << (boy - 1).bit_length()
    sonuc = np.zeros_like(x)
    for c in range(2):
        s = np.fft.irfft(np.fft.rfft(x[:, c], N) * np.fft.rfft(ir[:, c], N), N)[:x.shape[0]]
        sonuc[:, c] = s
    return x * (1 - karisim) + sonuc * karisim


def _atmosfer(rng, sure):
    n = int(sure * SR)
    y = np.zeros((n, 2))
    # fan uğultusu (sürekli, çok hafif)
    g = bant_gurultu(rng, n, 180, 1100)
    y += _pan(g * 0.018, 0)
    # step motor çıtırtıları: kısa, rastgele, perde ve konum değişken
    t0 = 0.8
    while t0 < sure - 0.5:
        dur = float(rng.uniform(0.25, 1.1))
        m = int(dur * SR)
        t = _zaman(m)
        f0 = float(rng.uniform(170, 460))
        kayma = float(rng.uniform(-0.25, 0.25))
        f = f0 * (1 + kayma * t / dur)
        faz = 2 * np.pi * np.cumsum(f) / SR
        kare = sum(np.sin(h * faz) / h for h in (1, 3, 5))
        adim = float(rng.uniform(22, 46))
        am = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * adim * t))
        z = kare * am * np.sin(np.pi * np.linspace(0, 1, m)) ** 0.7
        _yerlestir(y, _pan(z * 0.016, float(rng.uniform(-0.8, 0.8))), t0)
        t0 += dur + float(rng.uniform(0.4, 2.4))
    return y


# ---------- olay listesi (plan → sesler) ----------

def _olaylar_ham(plan):
    """Renderer ile aynı zaman çizelgesinden efekt olayları: [(zaman, ad)]"""
    ol = [(0.06, 'darbe')]
    sahneler = plan['sahneler']
    for i, s in enumerate(sahneler):
        t0, t1 = s['t0'], s['t1']
        d = t1 - t0
        pr = s.get('params') or {}
        tip = s['tip']
        if i < len(sahneler) - 1:
            son = s.get('ses_son', t1 - 0.5)   # konuşmanın bittiği an: geçiş efektleri ondan SONRA başlar
            ol.append((t1, 'gecis'))
            ol.append((t1, 'yukselis', max(0.15, min(0.5, t1 - son - 0.06))))
        if s.get('ekran') and i > 0:
            ol.append((t0 + 0.34, 'pop'))
        if s.get('rozet'):
            ol.append((t0 + 0.28, 'ding'))
        if tip == 'baski' and pr.get('nesne') == 'warp':
            ol += [(t0 + d * 0.36, 'uyari'), (t0 + d * 0.36 + 0.9, 'uyari')]
        elif tip == 'temizlik':
            ol.append((t0 + d * 0.03, 'sprey'))
            for k in range(4):
                ol.append((t0 + d * (0.22 + 0.72 * k / 4) + 0.1, 'silme' if k % 2 == 0 else 'silme2'))
            ol.append((t0 + d * 0.92, 'parilti'))
        elif tip == 'ilk_katman':
            for k, ad in enumerate(('uyari', 'ding', 'uyari')):
                ol.append((t0 + d * (k * 0.24 + 0.07), ad))
        elif tip == 'sicaklik':
            n = int(d * 0.72 * 8)
            for k in range(n):
                ol.append((t0 + d * 0.08 + k * (d * 0.72 / n), 'tik'))
            ol.append((t0 + d * 0.82, 'ding'))
        elif tip == 'hiz':
            ol.append((t0 + d * 0.1, 'fan_son'))
            ol.append((t0 + d * 0.52, 'uyari'))
        elif tip == 'yapistirici':
            for k in range(3):
                ol.append((t0 + d * (0.06 + 0.15 * k), 'silme' if k % 2 == 0 else 'silme2'))
            ol.append((t0 + d * 0.62, 'yukselen_ton'))
            ol.append((t0 + d * 0.92, 'ding_alt'))
        elif tip == 'sayi':
            n = int(d * 0.5 * 10)
            for k in range(n):
                ol.append((t0 + d * 0.05 + k * (d * 0.5 / n), 'tik'))
            ol.append((t0 + d * 0.58, 'ding'))
        elif tip == 'karsilastir':
            ol += [(t0 + d * 0.15, 'yukselen_ton'), (t0 + d * 0.62, 'ding_alt'), (t0 + d * 0.74, 'ding')]
        elif tip == 'ozet':
            m = len(pr.get('maddeler') or [])
            for k in range(m):
                ol.append((t0 + d * (0.08 + k * 0.55 / max(m, 1)) + 0.1, 'ding' if k % 2 == 0 else 'ding_alt'))
        elif tip == 'liste_giris':
            ol.append((t0 + 0.45, 'pop'))
        elif tip == 'liste_madde':
            ol.append((t0 + 0.32, 'pop'))
            if pr.get('deger') is not None:
                for k in range(14):
                    ol.append((t0 + 0.58 + k * 0.09, 'tik'))
                ol.append((t0 + 1.92, 'ding'))
        elif tip == 'liste_kapanis':
            ol += [(t0 + 0.15, 'darbe'), (t0 + 0.15, 'parilti')]
        elif tip == 'cta':
            ol.append((t0 + d * 0.1, 'parilti'))
            ol.append((t0 + d * 0.1, 'darbe'))
    return sorted(ol)


def konusma_araliklari(plan, on_pay=0.04, son_pay=0.06):
    """Anlatının konuşulduğu zaman aralıkları [(baş, son)]: kelime zamanlarından, birleştirilmiş. Efektler bu aralıklara BAŞLAMAZ."""
    a = sorted((k['t0'] - on_pay, k['t1'] + son_pay) for p in plan.get('altyazi', []) for k in p.get('kelimeler', []))
    birlesik = []
    for b, e in a:
        if birlesik and b <= birlesik[-1][1] + 0.06:   # 60 ms'den kısa boşluklar nefes sayılmaz
            birlesik[-1][1] = max(birlesik[-1][1], e)
        else:
            birlesik.append([b, e])
    return birlesik


def olaylar_uret(plan):
    """Efekt olayları: konuşma varken (cümle sonu dahil) HİÇBİR efekt başlamaz.
    Konuşma aralığına düşen olay, ±0,7 sn içindeki en yakın sessiz boşluğa kaydırılır; yoksa sayaç tıkları (tik) düşürülür, diğerleri de atlanır."""
    ol = _olaylar_ham(plan)
    ar = konusma_araliklari(plan)
    if not ar:
        return ol
    sonuc = []
    for ev in ol:
        t, ad = ev[0], ev[1]
        # geçiş efektlerinin BAŞLANGICI da konuşmaya binmesin: gerekirse biraz geciktirilir (yükseliş kısalır)
        if ad in ('gecis', 'yukselis'):
            sure = ev[2] if (ad == 'yukselis' and len(ev) > 2) else TEPE.get(ad, 0.0)
            ic0 = next((a for a in ar if a[0] <= t - sure < a[1]), None)
            if ic0 is not None:
                if ad == 'gecis':
                    t = ic0[1] + 0.02 + sure
                    ev = (t, ad)
                else:
                    kalan = t - (ic0[1] + 0.02)
                    if kalan < 0.1:
                        continue
                    ev = (t, ad, kalan)
        ic = next((a for a in ar if a[0] <= t < a[1]), None)
        if ic is None:
            sonuc.append(ev)
            continue
        if ad == 'tik':
            continue   # sayaç yalnız görsel kalır; konuşmanın üstüne tık sesi binmez
        # en yakın boşluk: konuşma aralığının hemen öncesi ya da sonrası
        adaylar = []
        if ic[0] - 0.05 >= 0 and t - ic[0] <= 0.7:
            adaylar.append(ic[0] - 0.05)
        i = ar.index(ic)
        sonraki = ic[1] + 0.02
        if (i + 1 >= len(ar) or sonraki < ar[i + 1][0] - 0.1) and sonraki - t <= 0.7:
            adaylar.append(sonraki)
        if adaylar:
            yeni = min(adaylar, key=lambda x: abs(x - t))
            sonuc.append((yeni, ad) + tuple(ev[2:]))
    return sorted(sonuc)


# ---------- ana üretim ----------

def yaz_wav(yol, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype('<i2')
    with wave.open(str(yol), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def oku_wav(yol):
    with wave.open(str(yol), 'rb') as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        ham = w.readframes(n)
    if sw != 2:
        raise ValueError('yalnızca 16 bit wav')
    x = np.frombuffer(ham, dtype='<i2').astype(np.float64) / 32768
    x = x.reshape(-1, ch)
    mono = x.mean(axis=1)
    if sr != SR:
        t_yeni = np.arange(int(len(mono) * SR / sr)) / SR
        mono = np.interp(t_yeni, np.arange(len(mono)) / sr, mono)
    return mono


def yan_zincir(ses, sure, derinlik=0.5, atak=0.02, birak=0.75):   # müzik konuşma bitince YAVAŞÇA geri gelir (ani ses düşmesi/yükselmesi olmaz)
    """Konuşma zarfından müzik kazancı (1 = kısılmamış). 200 Hz ızgarada hesaplanır."""
    n = int(sure * SR)
    v = np.zeros(n)
    v[:min(n, len(ses))] = np.abs(ses[:n])
    hiz = 200
    blok = SR // hiz
    kadem = n // blok
    kisa = v[:kadem * blok].reshape(kadem, blok).max(axis=1)
    zarf = np.zeros(kadem)
    a_k = np.exp(-1 / (atak * hiz))
    r_k = np.exp(-1 / (birak * hiz))
    z = 0.0
    for i in range(kadem):
        z = a_k * z + (1 - a_k) * kisa[i] if kisa[i] > z else r_k * z + (1 - r_k) * kisa[i]
        zarf[i] = z
    ref = max(np.percentile(zarf[zarf > 0.01], 70), 0.05) if np.any(zarf > 0.01) else 1.0
    kazanc = 1 - derinlik * np.clip(zarf / ref, 0, 1)
    return np.interp(np.arange(n) / SR, (np.arange(kadem) + 0.5) / hiz, kazanc)


def uret(plan, cikti, ses_yolu=None, tohum=7):
    """plan: sahneler/sure. ses_yolu: konuşma (mono/stereo wav, SR'ye dönüştürülür) ya da None. cikti: stereo wav (limitlenmemiş; ffmpeg loudnorm sonrası)."""
    if plan.get('tohum') is not None:
        muzik_ayarla(plan['tohum'])
    rng = np.random.default_rng(tohum)
    sure = float(plan['sure'])
    n = int(sure * SR)
    muzik = _pad(rng, sure)[:n]
    muzik = muzik + _arpej(rng, sure)[:n]
    muzik = _yanki(muzik, rng)
    muzik = muzik + _bas_vurus(rng, sure)[:n] + _hihat(rng, sure)[:n]
    atm = _atmosfer(rng, sure)[:n]

    # efektler
    fx = np.zeros((n, 2))
    for ev in olaylar_uret(plan):
        zaman, ad = ev[0], ev[1]
        rr = np.random.default_rng(int(zaman * 1000) + len(ad))
        if ad == 'yukselis' and len(ev) > 2:
            parca, tepe = fx_yukselis(rr, ev[2]), ev[2]   # kısa yükseliş: konuşma bittikten sonra başlar, sahne sınırında zirve yapar
        else:
            parca, tepe = FX[ad](rr), TEPE.get(ad, 0.0)
        _yerlestir(fx, parca, zaman - tepe)
    fx = _yanki(fx, rng, 0.35, 0.8, 0.12)

    ses = oku_wav(ses_yolu)[:n] if ses_yolu else None
    muzik_g = np.ones(n)
    if ses is not None:
        muzik_g = yan_zincir(ses, sure)
    # düzey ayarı: müzik+atmosfer RMS'i konuşmanın 14 dB altında (konuşma yoksa -22 dBFS)
    kar = (muzik + atm)
    r_m = np.sqrt(np.mean(kar ** 2)) or 1.0
    hedef = 10 ** (-22 / 20)
    if ses is not None:
        r_s = np.sqrt(np.mean(ses[np.abs(ses) > 0.01] ** 2)) if np.any(np.abs(ses) > 0.01) else 0.1
        hedef = r_s * 10 ** (-13 / 20)
    kar *= hedef / r_m
    fx *= hedef / r_m * 1.9
    fx *= (0.5 + 0.5 * muzik_g)[:, None]   # konuşma sırasında efektler de (yarı derinlikte) kısılır
    karisim = kar * muzik_g[:, None] + fx
    # giriş / çıkış yumuşatma
    t = np.arange(n) / SR
    karisim *= np.minimum(1, t / 0.4)[:, None] * np.minimum(1, (sure - t) / 1.6)[:, None] ** 1.5
    if ses is not None:
        v = np.zeros(n)
        v[:len(ses)] = ses
        karisim += np.stack([v, v], axis=1) * 1.0
    karisim /= max(1.0, np.abs(karisim).max() / 0.95)
    yaz_wav(cikti, karisim)
    return cikti


def normalize(giris, cikti):
    """ffmpeg ile −14 LUFS / −1.5 dBTP (Shorts/Reels için)."""
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(giris), '-af', 'loudnorm=I=-14:TP=-1.5:LRA=9', '-ar', '44100', str(cikti)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ses normalize edilemedi: ' + (r.stderr or '')[-200:])
    return cikti


if __name__ == '__main__':
    plan = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
    uret(plan, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print('ses hazır:', sys.argv[2])
