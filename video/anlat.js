/* "Anlat" biçimi — sahne motoru.
 * plan: { sure, sahneler:[{tip,t0,t1,params,etiketler,gecis}], bolumler:[{no,ad,t0,t1}], basliklar:[{t,metin}], altyazi:[{t0,t1,kelimeler:[{k,t0,t1,v}]}] }
 * Her sahne tipi anlat_sahneler.js içinde (window.ANLAT.sahneler[tip]) bir çizim işlevidir; motor sahneleri sırayla çizer, aralarında geçiş efekti uygular,
 * üstüne bölüm etiketi + renk vurgulu altyazı + başlık kartı + marka katar. render.js: window.hazirla(plan, olcek) ve window.kare(t, kalite). */
(function () {
  const W = 1080, H = 1920;
  const A = window.ANLAT = window.ANLAT || { sahneler: {} };
  const cl = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const sm = v => { v = cl(v); return v * v * (3 - 2 * v); };
  const eo = v => 1 - Math.pow(1 - cl(v), 3);
  const back = v => { v = cl(v); const c = 1.70158; return 1 + (c + 1) * Math.pow(v - 1, 3) + c * Math.pow(v - 1, 2); };
  const lerp = (a, b, t) => a + (b - a) * t;
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const mix = (c1, c2, t) => { const a = hex(c1), b = hex(c2); return 'rgb(' + a.map((v, i) => Math.round(lerp(v, b[i], cl(t)))).join(',') + ')'; };
  A.u = { W, H, cl, sm, eo, back, lerp, mix };
  let cv, x, olcek = 1, plan = {}, ca, cb, xa, xb;
  function rr(c, a, b, w, h, r) { c.beginPath(); c.moveTo(a + r, b); c.arcTo(a + w, b, a + w, b + h, r); c.arcTo(a + w, b + h, a, b + h, r); c.arcTo(a, b + h, a, b, r); c.arcTo(a, b, a + w, b, r); c.closePath(); }
  A.u.rr = rr;

  const VURGU = ['#ffffff', '#ff9a3c', '#4fc3ff'];
  const TEMALAR = { mavi: ['#0e2747', '#14506f', '#0a1f33'], mor: ['#1d1442', '#3b2a86', '#120c2c'], yesil: ['#0b2b2a', '#16645a', '#08201f'], turuncu: ['#2b1408', '#7a3a14', '#1a0c05'], gri: ['#14202e', '#2e4560', '#0c141f'] };

  /* ---------- sahne bağlamı: kamera, arka plan, etiket ---------- */
  function baglam(c, t, s, i) {
    const lt = Math.max(0, t - s.t0), d = Math.max(0.1, s.t1 - s.t0), p = s.params || {};
    const o = { x: c, W, H, t, lt, d, p, i, etiketler: s.etiketler || [], cam: { cx: 540, cy: 760, z: 1 } };
    o.arka = function (tema) {
      const th = TEMALAR[tema || p.tema || 'mavi'] || TEMALAR.mavi;
      const g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, th[0]); g.addColorStop(0.55, th[1]); g.addColorStop(1, th[2]); c.fillStyle = g; c.fillRect(0, 0, W, H);
      c.fillStyle = 'rgba(160,210,255,0.12)'; const ox = -(o.cam.cx * 0.3) % 90 - lt * 6, oy = -(o.cam.cy * 0.3) % 90;
      for (let gx = -90; gx < W + 90; gx += 90) for (let gy = -90; gy < H + 90; gy += 90) { c.beginPath(); c.arc(gx + ox, gy + oy, 3, 0, 6.3); c.fill(); }
      for (let k = 0; k < 24; k++) { const px = (k * 173 + t * (6 + k % 5)) % W, py = (k * 311 - t * (14 + k % 7) + 4000) % H; c.fillStyle = 'rgba(190,230,255,' + (0.1 + 0.1 * Math.sin(t * 1.3 + k)) + ')'; c.beginPath(); c.arc(px, py, 2 + k % 4, 0, 6.3); c.fill(); }
      const v = c.createRadialGradient(W / 2, H * 0.45, 300, W / 2, H * 0.45, 1200); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,10,25,0.55)'); c.fillStyle = v; c.fillRect(0, 0, W, H);
    };
    // dünya: kamera a→b (merkezX, merkezY, yakınlaştırma) sahne boyunca yumuşak gider; hafif el kamerası
    o.dunya = function (a, b, fn) {
      const q = sm(lt / d), cx = lerp(a[0], b[0], q) + Math.sin(t * 0.9) * 5, cy = lerp(a[1], b[1], q) + Math.cos(t * 0.7) * 4, z = lerp(a[2], b[2], q);
      o.cam = { cx, cy, z }; c.save(); c.translate(W / 2, H * 0.43); c.scale(z, z); c.translate(-cx, -cy); fn(); c.restore();
    };
    o.nokta = (wx, wy) => [(wx - o.cam.cx) * o.cam.z + W / 2, (wy - o.cam.cy) * o.cam.z + H * 0.43];
    // bilgi etiketi: metin sırası k (0,1), ekran konumu, giriş zamanı (sahne başından sn)
    o.etiket = function (k, sx, sy, tIn, yon) {
      const metin = o.etiketler[k]; if (!metin || lt < tIn) return;
      const s2 = Math.min(back((lt - tIn) / 0.45), 1.06), sol = (yon || 1) < 0;
      c.save(); c.font = '800 40px IB, Inter, sans-serif'; const w = c.measureText(metin).width + 50, h = 70;
      let bx = sol ? sx - 90 - w : sx + 90; if (bx + w > W - 24) bx = sx - 90 - w; if (bx < 24) bx = sx + 90; const by = sy - 60, tersMi = bx < sx;
      c.strokeStyle = '#ffd36b'; c.lineWidth = 5; c.beginPath(); c.moveTo(sx, sy); c.lineTo(tersMi ? bx + w - 20 : bx + 20, by + h / 2); c.stroke(); c.fillStyle = '#ffd36b'; c.beginPath(); c.arc(sx, sy, 10, 0, 6.3); c.fill();
      c.translate(bx + w / 2, by + h / 2); c.scale(s2, s2); c.fillStyle = '#ffffff'; c.shadowColor = 'rgba(0,0,0,0.35)'; c.shadowBlur = 16; rr(c, -w / 2, -h / 2, w, h, 20); c.fill(); c.shadowBlur = 0;
      c.fillStyle = '#12304f'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(metin, 0, 3); c.restore();
    };
    return o;
  }
  function sahneCiz(c, t, s, i) {
    const f = A.sahneler[s.tip] || A.sahneler.kanca;
    c.save(); try { f(baglam(c, t, s, i)); } finally { c.restore(); }
  }

  /* ---------- geçişler ---------- */
  const GEC_YARI = 0.3;
  function efektif(i) { const s = plan.sahneler[i]; return i === 0 ? s : Object.assign({}, s, { t0: s.t0 - GEC_YARI }); }   // sahne geçiş başlarken zaten hareket etmeye başlar (sıçrama olmasın)
  function gecisCiz(t, i) {   // sahne i → i+1 sınırında
    const S = plan.sahneler, A1 = S[i], B1 = S[i + 1], tb = A1.t1, q = cl((t - (tb - GEC_YARI)) / (2 * GEC_YARI)), e = sm(q), tip = B1.gecis || 'kay';
    xa.setTransform(olcek, 0, 0, olcek, 0, 0); xb.setTransform(olcek, 0, 0, olcek, 0, 0);
    sahneCiz(xa, t, efektif(i), i); sahneCiz(xb, t, efektif(i + 1), i + 1);
    x.save(); x.setTransform(1, 0, 0, 1, 0, 0);
    const pw = cv.width, ph = cv.height;
    if (tip === 'kay') {
      x.drawImage(ca, -e * pw, 0, pw, ph); x.drawImage(cb, (1 - e) * pw, 0, pw, ph);
      x.fillStyle = 'rgba(255,255,255,' + (0.18 * Math.sin(e * Math.PI)) + ')'; for (let k = 0; k < 7; k++) x.fillRect(0, (k * 0.15 + 0.03) * ph, pw, ph * 0.012);
    } else if (tip === 'cevir') {
      x.drawImage(ca, 0, -e * ph, pw, ph); x.drawImage(cb, 0, (1 - e) * ph, pw, ph);
    } else if (tip === 'yakin') {
      x.globalAlpha = 1 - e; const z = 1 + e * 0.7; x.drawImage(ca, pw / 2 - pw * z / 2, ph / 2 - ph * z / 2, pw * z, ph * z);
      x.globalAlpha = e; const z2 = 0.75 + e * 0.25; x.drawImage(cb, pw / 2 - pw * z2 / 2, ph / 2 - ph * z2 / 2, pw * z2, ph * z2); x.globalAlpha = 1;
    } else if (tip === 'daire') {
      x.drawImage(ca, 0, 0, pw, ph); const R = Math.hypot(pw, ph) / 2 * e; x.save(); x.beginPath(); x.arc(pw / 2, ph * 0.45, R, 0, 6.3); x.clip(); x.drawImage(cb, 0, 0, pw, ph); x.restore();
      x.strokeStyle = 'rgba(255,255,255,0.8)'; x.lineWidth = 10 * olcek; x.beginPath(); x.arc(pw / 2, ph * 0.45, R, 0, 6.3); x.stroke();
    } else {   // parlama
      x.drawImage(ca, 0, 0, pw, ph); x.globalAlpha = e; x.drawImage(cb, 0, 0, pw, ph); x.globalAlpha = 0.75 * Math.sin(e * Math.PI); x.fillStyle = '#fff6e0'; x.fillRect(0, 0, pw, ph); x.globalAlpha = 1;
    }
    x.restore();
  }

  /* ---------- ekran katmanı ---------- */
  function bolumEtiketi(t) {
    (plan.bolumler || []).forEach(function (s) {
      const g = back((t - s.t0 - 0.08) / 0.5), c = cl((s.t1 - 0.12 - t) / 0.3); if (t < s.t0 || t > s.t1 || c <= 0) return;
      x.save(); x.font = '800 44px IB, Inter, sans-serif'; const w = x.measureText(s.ad).width + 150, h = 92, y0 = lerp(-140, 140, Math.min(g, 1.05));
      x.globalAlpha = c; x.shadowColor = 'rgba(0,0,0,0.35)'; x.shadowBlur = 20; x.fillStyle = '#ffffff'; rr(x, W / 2 - w / 2, y0, w, h, 46); x.fill(); x.shadowBlur = 0;
      x.fillStyle = '#ff7a1a'; x.beginPath(); x.arc(W / 2 - w / 2 + 48, y0 + h / 2, 32, 0, 6.3); x.fill();
      x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(String(s.no), W / 2 - w / 2 + 48, y0 + h / 2 + 2);
      x.fillStyle = '#12304f'; x.textAlign = 'left'; x.fillText(s.ad, W / 2 - w / 2 + 100, y0 + h / 2 + 3); x.restore();
    });
  }
  function altyazi(t) {
    (plan.altyazi || []).forEach(function (blok) {
      if (t < blok.t0 || t > blok.t1) return;   // bir sonraki satırla üst üste binmesin
      const sol = cl((blok.t1 - t) / 0.12); x.save(); x.globalAlpha = sol; x.font = '800 78px IB, Inter, sans-serif'; x.textBaseline = 'middle';
      const bosluk = x.measureText(' ').width + 18, ks = blok.kelimeler.map(k => ({ t: k.t0, m: k.k, v: k.v || 0, w: x.measureText(k.k).width }));
      const toplam = ks.reduce((a, k) => a + k.w + bosluk, -bosluk); let satirlar = [ks];
      if (toplam > 900) { const yarim = Math.ceil(ks.length / 2); satirlar = [ks.slice(0, yarim), ks.slice(yarim)]; }
      satirlar.forEach(function (st, si) {
        const gw = st.reduce((a, k) => a + k.w + bosluk, -bosluk); let px = W / 2 - gw / 2; const py = 1560 + si * 100 - (satirlar.length - 1) * 50;
        st.forEach(function (k) {
          const p = t - k.t; if (p >= 0) { const sc = Math.min(back(p / 0.22), 1.08); x.save(); x.translate(px + k.w / 2, py); x.scale(sc, sc); x.lineJoin = 'round'; x.lineWidth = 14; x.strokeStyle = 'rgba(8,18,34,0.92)'; x.textAlign = 'center'; x.strokeText(k.m, 0, 0); x.fillStyle = VURGU[k.v] || VURGU[0]; x.fillText(k.m, 0, 0); x.restore(); }
          px += k.w + bosluk;
        });
      });
      x.restore();
    });
  }
  function baslikKarti(t) {
    (plan.basliklar || []).forEach(function (b) {
      const a = b.t, e = b.t + (b.sure || 1.1); if (t < a || t > e) return;
      const g = back((t - a) / 0.35), c = cl((e - t) / 0.25), jit = t - a < 0.5 ? Math.sin((t - a) * 60) * 4 * (1 - (t - a) / 0.5) : 0, m = String(b.metin).toUpperCase();
      x.save(); x.globalAlpha = c; x.translate(W / 2 + jit, 560); x.rotate(-0.07); const k = Math.min(g, 1.1); x.scale(k, k);
      let fs = 250; x.font = '800 ' + fs + 'px IB, Inter, sans-serif'; while (x.measureText(m).width > 940 && fs > 90) { fs -= 10; x.font = '800 ' + fs + 'px IB, Inter, sans-serif'; }
      x.textAlign = 'center'; x.textBaseline = 'middle'; x.lineJoin = 'round'; x.lineWidth = 34; x.strokeStyle = '#ff5a14'; x.strokeText(m, 0, 0); x.lineWidth = 14; x.strokeStyle = '#12304f'; x.strokeText(m, 0, 0);
      x.fillStyle = '#fff3d6'; x.fillText(m, 0, 0); x.restore();
    });
  }
  function marka(t) {
    const son = plan.sure; if (t < son - 2.2) return; const g = sm((t - (son - 2.2)) / 0.5);
    x.save(); x.globalAlpha = g; x.font = '800 40px IB, Inter, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; const m = '@gurtechs3d · Takip et', w = x.measureText(m).width + 70;
    x.fillStyle = 'rgba(8,18,34,0.78)'; rr(x, W / 2 - w / 2, 1745, w, 80, 40); x.fill(); x.fillStyle = '#ffffff'; x.fillText(m, W / 2, 1788); x.restore();
  }

  /* ---------- kare ---------- */
  function ciz(t) {
    x.setTransform(olcek, 0, 0, olcek, 0, 0);
    const S = plan.sahneler; let i = S.length - 1; for (let k = 0; k < S.length; k++) if (t < S[k].t1) { i = k; break; }
    if (i < S.length - 1 && t > S[i].t1 - GEC_YARI) gecisCiz(t, i);
    else sahneCiz(x, t, efektif(i), i);
    x.setTransform(olcek, 0, 0, olcek, 0, 0);
    bolumEtiketi(t); baslikKarti(t); altyazi(t); marka(t);
  }
  window.hazirla = async function (p, o) {
    plan = p; olcek = o || 1; cv = document.getElementById('c2'); cv.width = Math.round(W * olcek); cv.height = Math.round(H * olcek); x = cv.getContext('2d');
    ca = document.createElement('canvas'); cb = document.createElement('canvas'); ca.width = cb.width = cv.width; ca.height = cb.height = cv.height; xa = ca.getContext('2d'); xb = cb.getContext('2d');
    try { await Promise.all([document.fonts.load('800 40px IB'), document.fonts.load('600 40px IS')]); } catch (e) { /* yazı tipi yoksa Inter/sans-serif */ }
    ciz(0);
  };
  window.kare = function (t, q) { ciz(t); return cv.toDataURL('image/jpeg', q || 0.9).split(',')[1]; };
})();
