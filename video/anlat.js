/* "Anlat" biçimi: konuya özel, sürekli hareketli kesit animasyonu (kamera akıcı biçimde gezer) + bölüm etiketi + renk vurgulu altyazı
 * + büyük başlık kartı + dünyaya bağlı bilgi etiketleri. render.js: window.hazirla(plan, olcek) ve window.kare(t, kalite).
 * Şimdilik tek sahne takımı var ("nozul": filament dişliden nozula, katman katman); sahneler VERİ olarak tanımlıdır (SAHNE, KAMERA, ALTYAZI, ETIKET). */
(function () {
  const W = 1080, H = 1920;
  let cv, x, olcek = 1, plan = {};
  const cl = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const sm = v => { v = cl(v); return v * v * (3 - 2 * v); };
  const eo = v => 1 - Math.pow(1 - cl(v), 3);
  const back = v => { v = cl(v); const c = 1.70158; return 1 + (c + 1) * Math.pow(v - 1, 3) + c * Math.pow(v - 1, 2); };
  const lerp = (a, b, t) => a + (b - a) * t;
  const mix = (c1, c2, t) => { const p = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); const a = p(c1), b = p(c2); return 'rgb(' + a.map((v, i) => Math.round(lerp(v, b[i], cl(t)))).join(',') + ')'; };
  function rr(a, b, w, h, r) { x.beginPath(); x.moveTo(a + r, b); x.arcTo(a + w, b, a + w, b + h, r); x.arcTo(a + w, b + h, a, b + h, r); x.arcTo(a, b + h, a, b, r); x.arcTo(a, b, a + w, b, r); x.closePath(); }

  /* ---------- veri: sahneler, kamera, altyazı, etiketler ---------- */
  const SAHNE = [
    { t0: 0.0, t1: 3.3, no: 1, ad: 'Dişli filamenti iter' },
    { t0: 3.3, t1: 6.7, no: 2, ad: 'Isıtıcı blok eritir' },
    { t0: 6.7, t1: 10.0, no: 3, ad: 'Nozul katman çizer' }
  ];
  // kamera anahtarları: [zaman, merkezX, merkezY, yakınlaştırma]; aralar yumuşak geçişle (kesme yok) birleşir
  const KAMERA = [[0, 540, 300, 1.0], [2.9, 540, 380, 1.12], [4.1, 540, 880, 1.18], [6.3, 540, 930, 1.22], [7.6, 540, 1235, 1.36], [10, 540, 1245, 1.5]];
  const ALTYAZI = [
    { t0: 0.0, t1: 3.2, kelimeler: [[0.15, 'Dişli'], [0.75, 'filamenti'], [1.4, 'iter.', 1]] },
    { t0: 3.4, t1: 6.6, kelimeler: [[3.55, 'Isıtıcı'], [4.1, 'blok'], [4.55, 'onu'], [4.95, 'eritir.', 1]] },
    { t0: 6.8, t1: 10.0, kelimeler: [[6.95, 'Nozul'], [7.5, 'katman', 2], [8.05, 'katman', 2], [8.6, 'çizer.']] }
  ];
  const VURGU = ['#ffffff', '#ff9a3c', '#4fc3ff'];
  // dünyaya bağlı etiketler: [başlangıç, bitiş, dünyaX, dünyaY, metin, yön(+1 sağ,-1 sol)]; konumları taşıyıcıyla (dx,dy) birlikte hareket eder
  const ETIKET = [
    [0.7, 3.2, 560, 40, '1,75 mm filament', 1, 0],
    [1.3, 3.2, 640, 330, 'Dişliler ters döner', 1, 0],
    [4.6, 6.6, 690, 905, '210 °C', 1, 1],
    [7.1, 9.9, 556, 1240, '0,4 mm nozul', 1, 1],
    [8.5, 9.9, 770, 1384, 'Katman: 0,2 mm', 1, 0]
  ];

  /* ---------- zaman çizelgeleri ---------- */
  const ısı = t => sm((t - 3.5) / 2.0);                       // 0..1
  const FIL_HIZ = t => (t < 6.7 ? 130 : 30);                  // filament ilerleme hızı (px/sn)
  const KAT_Y = 26, YATAK_Y = 1330;
  const GEC = [[7.4, 8.25, 1], [8.45, 9.3, -1], [9.5, 10.4, 1]];   // katman geçişleri [başlangıç, bitiş, yön]
  const KAFA = [[6.7, 0, 0], [7.4, -240, 38], [8.25, 240, 38], [8.45, 240, 12], [9.3, -240, 12], [9.5, -240, -14], [10.4, 240, -14]];   // [zaman, dx, dy]
  function tasiyici(t) {   // tüm ekstrüder+sıcak uç grubunun ötelenmesi (yazıcı kafası): yatağa iner, katman katman gidip gelir, her katmanda biraz yükselir
    if (t <= KAFA[0][0]) return { dx: 0, dy: 0 };
    for (let i = 0; i < KAFA.length - 1; i++) {
      const a = KAFA[i], b = KAFA[i + 1];
      if (t <= b[0]) { const p = sm((t - a[0]) / (b[0] - a[0])); return { dx: lerp(a[1], b[1], p), dy: lerp(a[2], b[2], p) }; }
    }
    const z = KAFA[KAFA.length - 1]; return { dx: z[1], dy: z[2] };
  }
  function kamera(t) {
    let i = 0; while (i < KAMERA.length - 2 && t > KAMERA[i + 1][0]) i++;
    const a = KAMERA[i], b = KAMERA[i + 1], p = sm((t - a[0]) / (b[0] - a[0]));
    const c = { x: lerp(a[1], b[1], p), y: lerp(a[2], b[2], p), z: lerp(a[3], b[3], p) };
    const tk = tasiyici(t);
    if (t > 6.7) c.x += tk.dx * 0.45 * sm((t - 6.7) / 0.8);
    c.x += Math.sin(t * 0.9) * 6; c.y += Math.cos(t * 0.7) * 5;       // hafif el kamerası
    return c;
  }

  /* ---------- arka plan ---------- */
  function arkaPlan(t, cam) {
    const g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0e2747'); g.addColorStop(0.55, '#14506f'); g.addColorStop(1, '#0a1f33');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    // paralaks nokta ızgarası + yavaş süzülen toz
    x.fillStyle = 'rgba(160,210,255,0.13)';
    const par = 0.35, ox = -(cam.x * par * cam.z) % 90, oy = -(cam.y * par * cam.z) % 90;
    for (let gx = -90; gx < W + 90; gx += 90) for (let gy = -90; gy < H + 90; gy += 90) { x.beginPath(); x.arc(gx + ox, gy + oy, 3, 0, 6.3); x.fill(); }
    for (let i = 0; i < 26; i++) {
      const px = (i * 173 + t * (6 + i % 5)) % W, py = (i * 311 - t * (14 + i % 7) + 4000) % H, r = 2 + (i % 4);
      x.fillStyle = 'rgba(190,230,255,' + (0.12 + 0.1 * Math.sin(t * 1.3 + i)) + ')'; x.beginPath(); x.arc(px, py, r, 0, 6.3); x.fill();
    }
    const v = x.createRadialGradient(W / 2, H * 0.45, 300, W / 2, H * 0.45, 1200); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,10,25,0.55)');
    x.fillStyle = v; x.fillRect(0, 0, W, H);
  }

  /* ---------- dünya çizimleri ---------- */
  function disli(cx, cy, dir, t, rOut, rIn, n) {
    x.save(); x.translate(cx, cy); x.rotate(dir * t * 1.9);
    x.fillStyle = '#8fa6c4'; x.strokeStyle = '#d6e4f7'; x.lineWidth = 4; x.beginPath();
    for (let i = 0; i < n * 2; i++) { const a0 = i / (n * 2) * Math.PI * 2, a1 = (i + 1) / (n * 2) * Math.PI * 2, r = i % 2 ? rIn : rOut; x.lineTo(Math.cos(a0) * r, Math.sin(a0) * r); x.lineTo(Math.cos(a1 - 0.02) * r, Math.sin(a1 - 0.02) * r); }
    x.closePath(); x.fill(); x.stroke();
    x.fillStyle = '#40536f'; x.beginPath(); x.arc(0, 0, rIn * 0.5, 0, 6.3); x.fill();
    x.strokeStyle = '#6f86a6'; x.lineWidth = 7; for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; x.beginPath(); x.moveTo(Math.cos(a) * rIn * 0.5, Math.sin(a) * rIn * 0.5); x.lineTo(Math.cos(a) * rIn * 0.92, Math.sin(a) * rIn * 0.92); x.stroke(); }
    x.fillStyle = '#d6e4f7'; x.beginPath(); x.arc(0, 0, 11, 0, 6.3); x.fill();
    x.restore();
  }
  function tasiyiciCiz(t) {
    const isi = ısı(t);
    // filament yönü: akan oklar
    if (t < 6.7) { x.strokeStyle = 'rgba(255,211,107,0.9)'; x.lineWidth = 8; x.lineCap = 'round'; x.lineJoin = 'round'; for (let k = 0; k < 4; k++) { const yy = -260 + ((t * 150 + k * 90) % 360); x.globalAlpha = Math.min(1, yy / 40 + 1) * (yy < 80 ? 1 : 0.0) + 0; if (yy > -260 && yy < 100) { x.globalAlpha = 1 - Math.abs(yy + 80) / 200; x.beginPath(); x.moveTo(478, yy); x.lineTo(490, yy + 16); x.lineTo(502, yy); x.stroke(); } } x.globalAlpha = 1; }
    // --- ekstrüder gövdesi (kesit) ---
    x.fillStyle = 'rgba(36,52,79,0.92)'; rr(300, 120, 480, 440, 46); x.fill(); x.strokeStyle = '#9fb6d6'; x.lineWidth = 6; x.stroke();
    x.fillStyle = 'rgba(14,26,44,0.9)'; rr(350, 175, 380, 330, 30); x.fill();
    disli(458, 340, 1, t, 74, 60, 12); disli(622, 340, -1, t, 74, 60, 12);
    // --- soğutma kanatları + ısı bariyeri ---
    for (let i = 0; i < 7; i++) { x.fillStyle = '#b9c9de'; rr(470, 575 + i * 30, 140, 12, 6); x.fill(); }
    x.fillStyle = 'rgba(60,80,110,0.9)'; x.fillRect(516, 560, 48, 240);
    // fan (sol) ve hava akışı çizgileri
    x.save(); x.translate(250, 690); x.fillStyle = '#2c3d5a'; rr(-80, -80, 160, 160, 26); x.fill(); x.strokeStyle = '#9fb6d6'; x.lineWidth = 4; x.stroke();
    x.rotate(t * 11); x.fillStyle = '#8fd0ff'; for (let i = 0; i < 4; i++) { x.rotate(Math.PI / 2); x.beginPath(); x.ellipse(28, 0, 30, 12, 0, 0, 6.3); x.fill(); } x.restore();
    x.strokeStyle = 'rgba(140,210,255,0.8)'; x.lineWidth = 6; x.lineCap = 'round';
    for (let r = 0; r < 4; r++) { const yy = 620 + r * 50, off = (t * 160 + r * 40) % 120; x.setLineDash([36, 84]); x.lineDashOffset = -off; x.beginPath(); x.moveTo(340, yy); x.lineTo(470, yy); x.stroke(); }
    x.setLineDash([]);
    // --- ısıtıcı blok ---
    const blokG = x.createLinearGradient(0, 800, 0, 1010); blokG.addColorStop(0, mix('#6b3a1e', '#ff7a1a', isi)); blokG.addColorStop(1, mix('#4a2a18', '#ff4d12', isi));
    if (isi > 0.02) { const gl = x.createRadialGradient(540, 905, 40, 540, 905, 380); gl.addColorStop(0, 'rgba(255,140,40,' + (0.55 * isi) + ')'); gl.addColorStop(1, 'rgba(255,120,30,0)'); x.fillStyle = gl; x.fillRect(100, 600, 880, 620); }
    x.fillStyle = blokG; rr(400, 800, 280, 210, 34); x.fill(); x.strokeStyle = '#ffd2a3'; x.lineWidth = 5; x.globalAlpha = 0.35 + 0.65 * isi; x.stroke(); x.globalAlpha = 1;
    x.fillStyle = '#2a1a12'; x.beginPath(); x.arc(440, 840, 11, 0, 6.3); x.fill();   // termistör
    // ısı dalgaları
    if (isi > 0.05) { x.strokeStyle = 'rgba(255,200,140,' + (0.5 * isi) + ')'; x.lineWidth = 5; for (let k = 0; k < 3; k++) { x.beginPath(); for (let u = 0; u <= 1; u += 0.05) { const px = 410 + u * 260, py = 770 - k * 26 - ((t * 40 + k * 20) % 30) + Math.sin(u * 12 + t * 6 + k) * 8; u === 0 ? x.moveTo(px, py) : x.lineTo(px, py); } x.stroke(); } }
    // --- nozul gövdesi ---
    x.fillStyle = mix('#7a8aa3', '#c88a56', isi); x.beginPath(); x.moveTo(440, 1010); x.lineTo(640, 1010); x.lineTo(572, 1232); x.lineTo(508, 1232); x.closePath(); x.fill();
    x.strokeStyle = '#d6e4f7'; x.lineWidth = 5; x.stroke();
    x.fillStyle = mix('#7a8aa3', '#c88a56', isi); rr(520, 1226, 40, 40, 8); x.fill(); x.stroke();
    // --- filament (katı → erimiş) ---
    const on = FIL_HIZ(t);
    x.save(); x.beginPath(); x.rect(0, -700, W, 700 + 1010); x.clip();
    x.fillStyle = '#eaf3ff'; rr(522, -700, 36, 1710, 8); x.fill();
    x.strokeStyle = 'rgba(70,110,170,0.55)'; x.lineWidth = 4; const faz = (t * on) % 70; for (let yy = -700 + faz; yy < 1010; yy += 70) { x.beginPath(); x.moveTo(522, yy); x.lineTo(558, yy); x.stroke(); }
    x.restore();
    // erime cephesi
    const cephe = lerp(1225, 835, isi);
    x.save(); x.beginPath(); x.moveTo(440, 800); x.lineTo(640, 800); x.lineTo(640, 1010); x.lineTo(572, 1232); x.lineTo(508, 1232); x.lineTo(440, 1010); x.closePath(); x.clip();
    const eg = x.createLinearGradient(0, cephe - 24, 0, cephe + 40); eg.addColorStop(0, 'rgba(255,170,60,0)'); eg.addColorStop(1, 'rgba(255,128,24,1)');
    x.fillStyle = eg; x.fillRect(420, cephe - 24, 240, 1300 - cephe);
    // kabarcıklar
    x.fillStyle = 'rgba(255,220,150,0.55)'; for (let i = 0; i < 9; i++) { const by = lerp(cephe + 20, 1220, ((t * 0.5 + i * 0.37) % 1)), bx = 540 + Math.sin(i * 2.3 + t * 3) * 34 * (1 - (by - 800) / 600); if (isi > 0.3 && by > cephe) { x.beginPath(); x.arc(bx, by, 4 + i % 3, 0, 6.3); x.fill(); } }
    x.restore();
    // erimiş damla/akış ucu
    if (isi > 0.6) { x.fillStyle = '#ff8a2b'; x.beginPath(); x.ellipse(540, 1272 + Math.sin(t * 8) * 2, 8, 12, 0, 0, 6.3); x.fill(); }
  }
  function yatakVeKatmanlar(t, tk) {
    x.fillStyle = '#3a4c68'; rr(-420, YATAK_Y, 1920, 46, 10); x.fill(); x.fillStyle = '#6d86a8'; x.fillRect(-420, YATAK_Y, 1920, 6);
    x.fillStyle = '#1c2a40'; x.fillRect(-420, YATAK_Y + 46, 1920, 200);
    x.strokeStyle = 'rgba(160,200,255,0.18)'; x.lineWidth = 3; for (let gx = -400; gx < 1500; gx += 90) { x.beginPath(); x.moveTo(gx, YATAK_Y + 46); x.lineTo(gx, YATAK_Y + 246); x.stroke(); }
    // katmanlar: her geçiş nozulun arkasında uzar
    for (let i = 0; i < GEC.length; i++) {
      const [a, b, yon] = GEC[i]; if (t < a) continue;
      const p = sm(cl((t - a) / (b - a))), x0 = yon > 0 ? 300 : 780, x1 = yon > 0 ? 300 + 480 * p : 780 - 480 * p;
      const yy = YATAK_Y - KAT_Y * (i + 1), l = Math.min(x0, x1), w = Math.abs(x1 - x0);
      x.fillStyle = i % 2 ? '#e8782a' : '#f08a3a'; rr(l, yy, w, KAT_Y - 2, 7); x.fill();
      x.fillStyle = 'rgba(255,255,255,0.22)'; x.fillRect(l + 5, yy + 4, Math.max(0, w - 10), 4); x.fillStyle = 'rgba(120,50,10,0.25)'; x.fillRect(l + 5, yy + KAT_Y - 8, Math.max(0, w - 10), 3);
      if (t < b && t >= a) { const hx = x1, gl = x.createRadialGradient(hx, yy + 6, 2, hx, yy + 6, 70); gl.addColorStop(0, 'rgba(255,190,90,0.95)'); gl.addColorStop(1, 'rgba(255,140,40,0)'); x.fillStyle = gl; x.fillRect(hx - 70, yy - 64, 140, 140); }
    }
  }

  /* ---------- ekran katmanı ---------- */
  function dunyaEkran(wx, wy, cam) { return [(wx - cam.x) * cam.z + W / 2, (wy - cam.y) * cam.z + H * 0.43]; }
  function etiketCiz(t, cam, tk) {
    ETIKET.forEach(function (e) {
      const [a, b, wx, wy, metin, yon, tasi] = e; if (t < a || t > b) return;
      const gir = back((t - a) / 0.45), cik = cl((b - t) / 0.3), s = Math.min(gir, 1.06) * cik;
      const [sx, sy] = dunyaEkran(wx + (tasi ? tk.dx : 0), wy + (tasi ? tk.dy : 0), cam);
      x.save(); x.globalAlpha = cl(cik * 1.2); x.font = '800 40px IB, Inter, sans-serif'; const w = x.measureText(metin).width + 50, h = 70;
      if (sx < 40 || sx > W - 40) { x.restore(); return; }
      const sola = sx + 90 + w > W - 24, bx = sola ? sx - 90 - w : sx + 90, by = sy - 60;
      x.strokeStyle = '#ffd36b'; x.lineWidth = 5; x.beginPath(); x.moveTo(sx, sy); x.lineTo(sola ? bx + w - 20 : bx + 20, by + h / 2); x.stroke(); x.fillStyle = '#ffd36b'; x.beginPath(); x.arc(sx, sy, 10, 0, 6.3); x.fill();
      x.translate(bx + w / 2, by + h / 2); x.scale(s, s); x.fillStyle = '#ffffff'; x.shadowColor = 'rgba(0,0,0,0.35)'; x.shadowBlur = 16; rr(-w / 2, -h / 2, w, h, 20); x.fill(); x.shadowBlur = 0;
      x.fillStyle = '#12304f'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(metin, 0, 3); x.restore();
    });
  }
  function bolumEtiketi(t) {
    SAHNE.forEach(function (s) {
      const g = back((t - s.t0 - 0.08) / 0.5), c = cl((s.t1 - 0.12 - t) / 0.3); if (t < s.t0 || t > s.t1 || c <= 0) return;
      x.save(); x.font = '800 44px IB, Inter, sans-serif'; const w = x.measureText(s.ad).width + 150, h = 92, y0 = lerp(-140, 140, Math.min(g, 1.05));
      x.globalAlpha = c; x.shadowColor = 'rgba(0,0,0,0.35)'; x.shadowBlur = 20; x.fillStyle = '#ffffff'; rr(W / 2 - w / 2, y0, w, h, 46); x.fill(); x.shadowBlur = 0;
      x.fillStyle = '#ff7a1a'; x.beginPath(); x.arc(W / 2 - w / 2 + 48, y0 + h / 2, 32, 0, 6.3); x.fill();
      x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(String(s.no), W / 2 - w / 2 + 48, y0 + h / 2 + 2);
      x.fillStyle = '#12304f'; x.textAlign = 'left'; x.fillText(s.ad, W / 2 - w / 2 + 100, y0 + h / 2 + 3); x.restore();
    });
  }
  function altyazi(t) {
    ALTYAZI.forEach(function (blok) {
      if (t < blok.t0 || t > blok.t1) return;
      const sol = cl((blok.t1 - t) / 0.25); x.save(); x.globalAlpha = sol; x.font = '800 78px IB, Inter, sans-serif'; x.textBaseline = 'middle';
      const bosluk = x.measureText(' ').width + 18, ks = blok.kelimeler.map(k => ({ t: k[0], m: k[1], v: k[2] || 0, w: x.measureText(k[1]).width }));
      const toplam = ks.reduce((a, k) => a + k.w + bosluk, -bosluk), iki = toplam > 900;
      let satirlar = [ks]; if (iki) { const yarim = Math.ceil(ks.length / 2); satirlar = [ks.slice(0, yarim), ks.slice(yarim)]; }
      satirlar.forEach(function (st, si) {
        const gw = st.reduce((a, k) => a + k.w + bosluk, -bosluk); let px = W / 2 - gw / 2; const py = 1540 + si * 100 - (satirlar.length - 1) * 50;
        st.forEach(function (k) {
          const p = t - k.t; if (p >= 0) { const s = back(p / 0.22); x.save(); x.translate(px + k.w / 2, py); x.scale(Math.min(s, 1.08), Math.min(s, 1.08)); x.lineJoin = 'round'; x.lineWidth = 14; x.strokeStyle = 'rgba(8,18,34,0.92)'; x.textAlign = 'center'; x.strokeText(k.m, 0, 0); x.fillStyle = VURGU[k.v]; x.fillText(k.m, 0, 0); x.restore(); }
          px += k.w + bosluk;
        });
      });
      x.restore();
    });
  }
  function baslikKarti(t) {   // "ERİR!" — büyük, eğik, zıplayarak gelen vurgu kartı
    const a = 4.85, b = 5.95; if (t < a || t > b) return;
    const g = back((t - a) / 0.35), c = cl((b - t) / 0.25), jit = t - a < 0.5 ? Math.sin((t - a) * 60) * 4 * (1 - (t - a) / 0.5) : 0;
    x.save(); x.globalAlpha = c; x.translate(W / 2 + jit, 560); x.rotate(-0.07); x.scale(Math.min(g, 1.1), Math.min(g, 1.1));
    x.font = '800 250px IB, Inter, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.lineJoin = 'round';
    x.lineWidth = 34; x.strokeStyle = '#ff5a14'; x.strokeText('ERİR!', 0, 0); x.lineWidth = 14; x.strokeStyle = '#12304f'; x.strokeText('ERİR!', 0, 0);
    x.fillStyle = '#fff3d6'; x.fillText('ERİR!', 0, 0); x.restore();
  }
  function sicaklikGostergesi(t) {   // sağ üst: sayaç kartı (ikinci örnekteki 1:07 sayacı gibi)
    const a = 3.55, b = 6.6; if (t < a || t > b) return;
    const g = back((t - a) / 0.5), c = cl((b - t) / 0.25), p = sm((t - 3.6) / 1.9), deg = Math.round(lerp(25, 210, p));
    x.save(); x.globalAlpha = c; x.translate(870, 330); x.scale(Math.min(g, 1.05), Math.min(g, 1.05)); x.shadowColor = 'rgba(0,0,0,0.4)'; x.shadowBlur = 20;
    x.fillStyle = '#ffffff'; rr(-150, -64, 300, 128, 34); x.fill(); x.shadowBlur = 0;
    x.fillStyle = '#e9edf3'; rr(-122, 30, 244, 14, 7); x.fill(); x.fillStyle = mix('#4fc3ff', '#ff5a14', p); rr(-122, 30, 244 * p, 14, 7); x.fill();
    x.fillStyle = '#12304f'; x.font = '800 62px IB, Inter, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(deg + ' °C', 0, -14); x.restore();
  }
  function katmanSayaci(t) {
    const a = 7.3, b = 10; if (t < a) return;
    const g = back((t - a) / 0.5), say = Math.min(3, GEC.filter(e => t >= e[0]).length);
    x.save(); x.translate(870, 330); x.scale(Math.min(g, 1.05), Math.min(g, 1.05)); x.shadowColor = 'rgba(0,0,0,0.4)'; x.shadowBlur = 20;
    x.fillStyle = '#ffffff'; rr(-170, -64, 340, 128, 34); x.fill(); x.shadowBlur = 0;
    x.fillStyle = '#ff7a1a'; x.font = '800 30px IB, Inter, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('KATMAN', 0, -34);
    x.fillStyle = '#12304f'; x.font = '800 70px IB, Inter, sans-serif'; x.fillText(say + ' / 3', 0, 18); x.restore();
  }
  function marka(t) {
    if (t < 9.2) return; const g = sm((t - 9.2) / 0.5);
    x.save(); x.globalAlpha = g; x.font = '800 40px IB, Inter, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; const m = '@gurtechs3d · Takip et', w = x.measureText(m).width + 70;
    x.fillStyle = 'rgba(8,18,34,0.78)'; rr(W / 2 - w / 2, 1745, w, 80, 40); x.fill(); x.fillStyle = '#ffffff'; x.fillText(m, W / 2, 1788); x.restore();
  }

  /* ---------- kare ---------- */
  function ciz(t) {
    x.setTransform(olcek, 0, 0, olcek, 0, 0);
    const cam = kamera(t), tk = tasiyici(t);
    arkaPlan(t, cam);
    x.save(); x.translate(W / 2, H * 0.43); x.scale(cam.z, cam.z); x.translate(-cam.x, -cam.y);
    yatakVeKatmanlar(t, tk);
    x.save(); x.translate(tk.dx, tk.dy); tasiyiciCiz(t); x.restore();
    x.restore();
    etiketCiz(t, cam, tk); sicaklikGostergesi(t); katmanSayaci(t); bolumEtiketi(t); baslikKarti(t); altyazi(t); marka(t);
  }
  window.hazirla = async function (p, o) {
    plan = p; olcek = o || 1; cv = document.getElementById('c2'); cv.width = Math.round(W * olcek); cv.height = Math.round(H * olcek); x = cv.getContext('2d');
    try { await Promise.all([document.fonts.load('800 40px IB'), document.fonts.load('600 40px IS')]); } catch (e) { /* yazı tipi yoksa Inter/sans-serif */ }
    ciz(0);
  };
  window.kare = function (t, q) { ciz(t); return cv.toDataURL('image/jpeg', q || 0.9).split(',')[1]; };
})();
