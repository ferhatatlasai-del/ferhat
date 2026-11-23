/* "Anlat" sahne kütüphanesi: her tip (ANLAT.sahneler[tip]) tek bir animasyonlu sahneyi çizer. c: {x, W, H, t, lt, d, p, etiketler, arka(tema), dunya(a,b,fn), nokta(wx,wy), etiket(k,sx,sy,tGiris,yon)}.
 * Sahneler 3D baskı kavramlarını kesit/yan görünüşle anlatır; konuya özel parametreler (sayılar, adlar) plan'dan gelir. */
(function () {
  const A = window.ANLAT, S = A.sahneler, { W, H, cl, sm, eo, back, lerp, mix, rr } = A.u;
  const TURUNCU = '#ff7a1a', MAVI = '#4fc3ff', YESIL = '#3cc47a', KIRMIZI = '#ff5a4f', KOYU = '#12304f';

  /* ---------- ortak çizim parçaları ---------- */
  function disli(c, cx, cy, dir, t, rOut, rIn, n) {
    c.save(); c.translate(cx, cy); c.rotate(dir * t * 1.9);
    c.fillStyle = '#8fa6c4'; c.strokeStyle = '#d6e4f7'; c.lineWidth = 4; c.beginPath();
    for (let i = 0; i < n * 2; i++) { const a0 = i / (n * 2) * Math.PI * 2, a1 = (i + 1) / (n * 2) * Math.PI * 2, r = i % 2 ? rIn : rOut; c.lineTo(Math.cos(a0) * r, Math.sin(a0) * r); c.lineTo(Math.cos(a1 - 0.02) * r, Math.sin(a1 - 0.02) * r); }
    c.closePath(); c.fill(); c.stroke(); c.fillStyle = '#40536f'; c.beginPath(); c.arc(0, 0, rIn * 0.5, 0, 6.3); c.fill();
    c.strokeStyle = '#6f86a6'; c.lineWidth = 7; for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; c.beginPath(); c.moveTo(Math.cos(a) * rIn * 0.5, Math.sin(a) * rIn * 0.5); c.lineTo(Math.cos(a) * rIn * 0.92, Math.sin(a) * rIn * 0.92); c.stroke(); }
    c.fillStyle = '#d6e4f7'; c.beginPath(); c.arc(0, 0, 11, 0, 6.3); c.fill(); c.restore();
  }
  // yazıcı kafası (ekstrüder + soğutma + ısıtıcı blok + nozul), nozul ucu y=1266; isi 0..1, hiz: filament px/sn
  function kafa(c, t, isi, hiz) {
    c.save();
    if (hiz > 0) { c.strokeStyle = 'rgba(255,211,107,0.9)'; c.lineWidth = 8; c.lineCap = 'round'; c.lineJoin = 'round'; for (let k = 0; k < 4; k++) { const yy = -260 + ((t * 150 + k * 90) % 360); if (yy < 100) { c.globalAlpha = Math.max(0, 1 - Math.abs(yy + 80) / 200); c.beginPath(); c.moveTo(478, yy); c.lineTo(490, yy + 16); c.lineTo(502, yy); c.stroke(); } } c.globalAlpha = 1; }
    c.fillStyle = 'rgba(36,52,79,0.92)'; rr(c, 300, 120, 480, 440, 46); c.fill(); c.strokeStyle = '#9fb6d6'; c.lineWidth = 6; c.stroke();
    c.fillStyle = 'rgba(14,26,44,0.9)'; rr(c, 350, 175, 380, 330, 30); c.fill();
    disli(c, 458, 340, 1, t * (hiz > 0 ? 1 : 0.2), 74, 60, 12); disli(c, 622, 340, -1, t * (hiz > 0 ? 1 : 0.2), 74, 60, 12);
    for (let i = 0; i < 7; i++) { c.fillStyle = '#b9c9de'; rr(c, 470, 575 + i * 30, 140, 12, 6); c.fill(); }
    c.fillStyle = 'rgba(60,80,110,0.9)'; c.fillRect(516, 560, 48, 240);
    c.save(); c.translate(250, 690); c.fillStyle = '#2c3d5a'; rr(c, -80, -80, 160, 160, 26); c.fill(); c.strokeStyle = '#9fb6d6'; c.lineWidth = 4; c.stroke();
    c.rotate(t * 11); c.fillStyle = '#8fd0ff'; for (let i = 0; i < 4; i++) { c.rotate(Math.PI / 2); c.beginPath(); c.ellipse(28, 0, 30, 12, 0, 0, 6.3); c.fill(); } c.restore();
    c.strokeStyle = 'rgba(140,210,255,0.8)'; c.lineWidth = 6; c.lineCap = 'round';
    for (let r = 0; r < 4; r++) { const yy = 620 + r * 50, off = (t * 160 + r * 40) % 120; c.setLineDash([36, 84]); c.lineDashOffset = -off; c.beginPath(); c.moveTo(340, yy); c.lineTo(470, yy); c.stroke(); } c.setLineDash([]);
    const blokG = c.createLinearGradient(0, 800, 0, 1010); blokG.addColorStop(0, mix('#6b3a1e', '#ff7a1a', isi)); blokG.addColorStop(1, mix('#4a2a18', '#ff4d12', isi));
    if (isi > 0.02) { const gl = c.createRadialGradient(540, 905, 40, 540, 905, 380); gl.addColorStop(0, 'rgba(255,140,40,' + (0.55 * isi) + ')'); gl.addColorStop(1, 'rgba(255,120,30,0)'); c.fillStyle = gl; c.fillRect(100, 600, 880, 620); }
    c.fillStyle = blokG; rr(c, 400, 800, 280, 210, 34); c.fill(); c.strokeStyle = '#ffd2a3'; c.lineWidth = 5; c.globalAlpha = 0.35 + 0.65 * isi; c.stroke(); c.globalAlpha = 1;
    c.fillStyle = '#2a1a12'; c.beginPath(); c.arc(440, 840, 11, 0, 6.3); c.fill();
    if (isi > 0.05) { c.strokeStyle = 'rgba(255,200,140,' + (0.5 * isi) + ')'; c.lineWidth = 5; for (let k = 0; k < 3; k++) { c.beginPath(); for (let u = 0; u <= 1; u += 0.05) { const px = 410 + u * 260, py = 770 - k * 26 - ((t * 40 + k * 20) % 30) + Math.sin(u * 12 + t * 6 + k) * 8; u === 0 ? c.moveTo(px, py) : c.lineTo(px, py); } c.stroke(); } }
    c.fillStyle = mix('#7a8aa3', '#c88a56', isi); c.beginPath(); c.moveTo(440, 1010); c.lineTo(640, 1010); c.lineTo(572, 1232); c.lineTo(508, 1232); c.closePath(); c.fill(); c.strokeStyle = '#d6e4f7'; c.lineWidth = 5; c.stroke();
    c.fillStyle = mix('#7a8aa3', '#c88a56', isi); rr(c, 520, 1226, 40, 40, 8); c.fill(); c.stroke();
    c.save(); c.beginPath(); c.rect(0, -700, W, 700 + 1010); c.clip(); c.fillStyle = '#eaf3ff'; rr(c, 522, -700, 36, 1710, 8); c.fill();
    c.strokeStyle = 'rgba(70,110,170,0.55)'; c.lineWidth = 4; const faz = (t * hiz) % 70; for (let yy = -700 + faz; yy < 1010; yy += 70) { c.beginPath(); c.moveTo(522, yy); c.lineTo(558, yy); c.stroke(); } c.restore();
    const cephe = lerp(1225, 835, isi);
    c.save(); c.beginPath(); c.moveTo(440, 800); c.lineTo(640, 800); c.lineTo(640, 1010); c.lineTo(572, 1232); c.lineTo(508, 1232); c.lineTo(440, 1010); c.closePath(); c.clip();
    const eg = c.createLinearGradient(0, cephe - 24, 0, cephe + 40); eg.addColorStop(0, 'rgba(255,170,60,0)'); eg.addColorStop(1, 'rgba(255,128,24,1)'); c.fillStyle = eg; c.fillRect(420, cephe - 24, 240, 1300 - cephe);
    c.fillStyle = 'rgba(255,220,150,0.55)'; for (let i = 0; i < 9; i++) { const by = lerp(cephe + 20, 1220, ((t * 0.5 + i * 0.37) % 1)), bx = 540 + Math.sin(i * 2.3 + t * 3) * 34 * (1 - (by - 800) / 600); if (isi > 0.3 && by > cephe) { c.beginPath(); c.arc(bx, by, 4 + i % 3, 0, 6.3); c.fill(); } }
    c.restore(); c.restore();
  }
  // tek başına nozul (kesit): tipX,tipY ucun alt ortası; boyut ölçeği k
  function nozul(c, tipX, tipY, isi, t, k, hizFil, tikali) {
    k = k || 1; c.save(); c.translate(tipX, tipY); c.scale(k, k);
    const sicak = mix('#7a8aa3', '#c88a56', isi), blok = mix('#5a3a2a', '#ff7a1a', isi);
    c.fillStyle = '#eaf3ff'; rr(c, -14, -760, 28, 640, 6); c.fill();
    if (hizFil) { c.strokeStyle = 'rgba(70,110,170,0.55)'; c.lineWidth = 4; const f = (t * hizFil) % 60; for (let y = -760 + f; y < -120; y += 60) { c.beginPath(); c.moveTo(-14, y); c.lineTo(14, y); c.stroke(); } }
    c.fillStyle = blok; rr(c, -105, -270, 210, 140, 26); c.fill(); c.strokeStyle = '#ffd2a3'; c.lineWidth = 4; c.stroke();
    c.fillStyle = sicak; c.beginPath(); c.moveTo(-75, -130); c.lineTo(75, -130); c.lineTo(15, -20); c.lineTo(-15, -20); c.closePath(); c.fill(); c.strokeStyle = '#d6e4f7'; c.lineWidth = 4; c.stroke();
    c.fillStyle = sicak; rr(c, -14, -24, 28, 24, 5); c.fill(); c.stroke();
    if (isi > 0.3 && !tikali) { c.fillStyle = 'rgba(255,128,24,0.95)'; c.beginPath(); c.moveTo(-14, -130); c.lineTo(14, -130); c.lineTo(8, -4); c.lineTo(-8, -4); c.closePath(); c.fill(); }
    c.restore();
  }
  function yatak(c, y, x0, x1) {
    c.fillStyle = '#3a4c68'; rr(c, x0, y, x1 - x0, 46, 10); c.fill(); c.fillStyle = '#6d86a8'; c.fillRect(x0, y, x1 - x0, 6); c.fillStyle = '#1c2a40'; c.fillRect(x0, y + 46, x1 - x0, 1500);   // yatağın altı ekranın dibine kadar iner (boş boşluk kalmasın)
    c.strokeStyle = 'rgba(160,200,255,0.16)'; c.lineWidth = 3; for (let gx = Math.ceil(x0 / 90) * 90; gx < x1; gx += 90) { c.beginPath(); c.moveTo(gx, y + 46); c.lineTo(gx, y + 1500); c.stroke(); }
  }
  function yazi(c, m, px, py, boy, renk, hiza, kontur) {
    c.save(); c.font = '800 ' + boy + 'px IB, Inter, sans-serif'; c.textAlign = hiza || 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round';
    if (kontur !== false) { c.lineWidth = Math.max(8, boy * 0.16); c.strokeStyle = 'rgba(8,18,34,0.9)'; c.strokeText(m, px, py); } c.fillStyle = renk || '#fff'; c.fillText(m, px, py); c.restore();
  }
  function kart(c, px, py, w, h, g) { c.save(); c.translate(px, py); c.scale(g, g); c.shadowColor = 'rgba(0,0,0,0.4)'; c.shadowBlur = 20; c.fillStyle = '#fff'; rr(c, -w / 2, -h / 2, w, h, 32); c.fill(); c.restore(); }
  function rozet(c, m, px, py, renk, g, boy) {   // ✓ / ✗ etiketli hap
    c.save(); c.translate(px, py); c.scale(g, g); c.font = '800 ' + (boy || 44) + 'px IB, Inter, sans-serif'; const w = c.measureText(m).width + 70; c.fillStyle = renk; c.shadowColor = 'rgba(0,0,0,0.35)'; c.shadowBlur = 16; rr(c, -w / 2, -38, w, 76, 38); c.fill(); c.shadowBlur = 0;
    c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(m, 0, 3); c.restore();
  }
  function makara(c, cx, cy, r, t, renk, dir) {
    c.save(); c.translate(cx, cy); c.rotate((dir || 1) * t * 0.9);
    c.fillStyle = renk; c.beginPath(); c.arc(0, 0, r, 0, 6.3); c.fill(); c.strokeStyle = 'rgba(0,0,0,0.18)'; c.lineWidth = 5; for (let k = r * 0.35; k < r; k += 18) { c.beginPath(); c.arc(0, 0, k, 0, 6.3); c.stroke(); }
    c.fillStyle = '#e9eef6'; c.beginPath(); c.arc(0, 0, r * 0.34, 0, 6.3); c.fill(); c.strokeStyle = '#b7c3d4'; c.lineWidth = 8; for (let i = 0; i < 5; i++) { const a = i * 6.2832 / 5; c.beginPath(); c.moveTo(Math.cos(a) * r * 0.12, Math.sin(a) * r * 0.12); c.lineTo(Math.cos(a) * r * 0.32, Math.sin(a) * r * 0.32); c.stroke(); }
    c.fillStyle = '#27364d'; c.beginPath(); c.arc(0, 0, r * 0.1, 0, 6.3); c.fill(); c.restore();
  }
  const sayi = (v, d) => Number(v == null || isNaN(v) ? d : v);

  /* ---------- sahneler ---------- */
  S.kanca = function (c) {   // açılış: dönen makara, ışın demeti, süzülen soru işaretleri
    const { x, lt, t, d } = c; c.arka(c.p.tema || 'mor');
    c.dunya([540, 760, 0.85], [540, 760, 1.05], function () {
      x.save(); x.translate(540, 760); for (let k = 0; k < 16; k++) { x.rotate(Math.PI * 2 / 16); x.fillStyle = 'rgba(255,255,255,' + (k % 2 ? 0.05 : 0.02) + ')'; x.beginPath(); x.moveTo(0, 0); x.lineTo(900, -60 + Math.sin(t) * 10); x.lineTo(900, 60 + Math.sin(t) * 10); x.closePath(); x.fill(); } x.restore();
      if (c.p.ikon && IKONLAR[c.p.ikon]) { x.save(); x.translate(540, 760); x.scale(5, 5); IKONLAR[c.p.ikon](x, t, { renk: 'turuncu' }); x.restore(); } else makara(x, 540, 760, 280, t, mix('#ff7a1a', '#ffb347', 0.5 + 0.5 * Math.sin(t * 0.8)), 1);
      for (let k = 0; k < 5; k++) { const a = t * 0.6 + k * 1.2566, rx = 440, ry = 150, px = 540 + Math.cos(a) * rx, py = 760 + Math.sin(a) * ry; x.fillStyle = ['#4fc3ff', '#3cc47a', '#ff9a3c', '#ff5a8f', '#b49cff'][k]; x.globalAlpha = 0.9; x.beginPath(); if (k % 2) x.rect(px - 26, py - 26, 52, 52); else x.arc(px, py, 28, 0, 6.3); x.fill(); x.globalAlpha = 1; }
    });
    for (let k = 0; k < 4; k++) { const e = back((lt - 0.3 - k * 0.35) / 0.4); if (e <= 0) continue; const px = [210, 880, 330, 790][k], py = [420, 520, 1150, 1030][k] + Math.sin(t * 2 + k) * 14; x.save(); x.translate(px, py); x.rotate(Math.sin(t * 1.6 + k) * 0.18); x.scale(Math.min(e, 1.05), Math.min(e, 1.05)); yazi(x, '?', 0, 0, 170 - k * 14, ['#ffd36b', '#fff', '#ff9a3c', '#4fc3ff'][k]); x.restore(); }
    c.etiket(0, 540, 560, 1.3);
  };

  S.ekstruder = function (c) {
    const { x, t, lt } = c; c.arka(c.p.tema || 'mavi');
    c.dunya([540, 300, 1.0], [540, 400, 1.18], function () { kafa(x, t, 0, 130); });
    const a = c.nokta(560, 40), b = c.nokta(640, 330); c.etiket(0, a[0], a[1], 0.8); c.etiket(1, b[0], b[1], 1.6);
  };
  S.sicak_uc = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'mavi'); const isi = sm((lt - 0.2) / Math.max(1.2, d * 0.55)), der = Math.round(lerp(25, sayi(p.derece, 210), isi));
    c.dunya([540, 880, 1.12], [540, 960, 1.28], function () { kafa(x, t, isi, 50); });
    kart(x, 880, 330, 300, 128, back((lt - 0.2) / 0.5)); x.save(); x.fillStyle = '#e9edf3'; rr(x, 758, 394, 244, 14, 7); x.fill(); x.fillStyle = mix('#4fc3ff', '#ff5a14', isi); rr(x, 758, 394, 244 * isi, 14, 7); x.fill(); x.restore();
    yazi(x, der + ' °C', 880, 316, 62, KOYU, 'center', false);
    const a = c.nokta(690, 905), b = c.nokta(556, 1240); c.etiket(0, a[0], a[1], 1.0); c.etiket(1, b[0], b[1], 2.0);
  };
  S.katman = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'mavi'); const n = Math.max(2, Math.min(6, Math.round(sayi(p.sayi, 4)))), KY = 26, YY = 1330, iniş = 0.7, gez = Math.max(0.5, (d - iniş - 0.5) / n);
    let dx = 0, dy = 0, aktif = -1, ilerle = 0, katSay = 0;
    if (lt < iniş) { dy = 52 * sm(lt / iniş) - 26 * 0; } else {
      const q = lt - iniş; aktif = Math.min(n - 1, Math.floor(q / gez)); const u = cl((q - aktif * gez) / gez); katSay = aktif + 1; ilerle = u;
      const yon = aktif % 2 === 0 ? 1 : -1, ph = sm(Math.min(1, u * 1.15)); dx = yon > 0 ? lerp(-240, 240, ph) : lerp(240, -240, ph); dy = 38 - KY * aktif;
      if (u > 0.9 && aktif < n - 1) dy -= KY * sm((u - 0.9) / 0.1);
    }
    c.dunya([540, 1230, 1.34], [540, 1245, 1.46], function () {
      yatak(x, YY, -420, 1500);
      for (let i = 0; i < n; i++) {
        if (i > aktif && aktif >= 0 || (aktif < 0)) break; const yon = i % 2 === 0 ? 1 : -1, tam = i < aktif, pr = tam ? 1 : sm(Math.min(1, ilerle * 1.15)), x0 = yon > 0 ? 300 : 780, x1 = yon > 0 ? 300 + 480 * pr : 780 - 480 * pr, yy = YY - KY * (i + 1), l = Math.min(x0, x1), w = Math.abs(x1 - x0);
        x.fillStyle = i % 2 ? '#e8782a' : '#f08a3a'; rr(x, l, yy, w, KY - 2, 7); x.fill(); x.fillStyle = 'rgba(255,255,255,0.22)'; x.fillRect(l + 5, yy + 4, Math.max(0, w - 10), 4); x.fillStyle = 'rgba(120,50,10,0.25)'; x.fillRect(l + 5, yy + KY - 8, Math.max(0, w - 10), 3);
        if (!tam) { const gl = x.createRadialGradient(x1, yy + 6, 2, x1, yy + 6, 70); gl.addColorStop(0, 'rgba(255,190,90,0.95)'); gl.addColorStop(1, 'rgba(255,140,40,0)'); x.fillStyle = gl; x.fillRect(x1 - 70, yy - 64, 140, 140); }
      }
      x.save(); x.translate(dx, dy); kafa(x, t, 1, 30); x.restore();
    });
    kart(x, 870, 330, 340, 128, back((lt - 0.5) / 0.5)); yazi(x, 'KATMAN', 870, 296, 30, TURUNCU, 'center', false); yazi(x, Math.max(1, katSay) + ' / ' + n, 870, 348, 70, KOYU, 'center', false);
    const a = c.nokta(556 + dx, 1240 + dy), b = c.nokta(770, 1384); c.etiket(0, a[0], a[1], 0.9); c.etiket(1, b[0], b[1], 1.8);
  };

  S.tikanma = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'turuncu'); const ph = lt / d, tikali = ph < 0.52, igne = sm((ph - 0.4) / 0.2), akis = sm((ph - 0.7) / 0.1), TIP = 1040;
    c.dunya([540, 880, 1.15], [540, 900, 1.3], function () {
      yatak(x, TIP + 190, -300, 1400);
      nozul(x, 540, TIP, 1, t, 1.2, tikali ? 18 : 60, tikali);
      if (tikali) { x.fillStyle = '#2b1d14'; x.beginPath(); x.moveTo(520, TIP - 100); x.lineTo(560, TIP - 100); x.lineTo(555, TIP - 20); x.lineTo(525, TIP - 20); x.closePath(); x.fill(); x.fillStyle = '#3a2a1c'; for (let k = 0; k < 6; k++) { x.beginPath(); x.arc(525 + k * 6 + Math.sin(t * 9 + k) * 2, TIP - 80 + (k % 3) * 18, 8, 0, 6.3); x.fill(); } for (let k = 0; k < 6; k++) { const q = (t * 0.6 + k / 6) % 1; x.fillStyle = 'rgba(190,190,200,' + (0.5 * (1 - q)) + ')'; x.beginPath(); x.arc(540 + Math.sin(q * 9 + k) * 40, TIP + 20 - q * 160, 18 + q * 30, 0, 6.3); x.fill(); } }
      if (igne > 0 && igne < 1.01 && ph < 0.7) { const iy = lerp(TIP + 330, TIP - 70, eo(igne)); x.strokeStyle = '#d6e4f7'; x.lineWidth = 7; x.lineCap = 'round'; x.beginPath(); x.moveTo(540, TIP + 400); x.lineTo(540, iy); x.stroke(); x.fillStyle = '#d6e4f7'; x.beginPath(); x.arc(540, iy, 7, 0, 6.3); x.fill();
        if (igne > 0.6) for (let k = 0; k < 14; k++) { const q = cl((igne - 0.6) / 0.4 + (ph > 0.55 ? (ph - 0.55) * 3 : 0)), px = 540 + Math.sin(k * 2.1) * 45 * q, py = TIP + 10 + q * 260 + (k % 5) * 14; x.fillStyle = '#2b1d14'; x.beginPath(); x.arc(px, py, 6 + k % 4, 0, 6.3); x.fill(); } }
      if (akis > 0) { const g = x.createLinearGradient(0, TIP, 0, TIP + 190); g.addColorStop(0, '#ff9a3c'); g.addColorStop(1, '#ff7a1a'); x.fillStyle = g; rr(x, 531, TIP, 18, 190 * akis, 8); x.fill(); x.fillStyle = '#ff9a3c'; x.beginPath(); x.ellipse(540, TIP + 190 * akis, 22, 12, 0, 0, 6.3); x.fill(); }
    });
    const dur = tikali ? 'TIKALI' : (ph < 0.7 ? 'TEMİZLENİYOR' : 'AÇIK'); rozet(x, (tikali ? '✗ ' : ph < 0.7 ? '⟳ ' : '✓ ') + dur, 540, 360, tikali ? KIRMIZI : ph < 0.7 ? '#e0a31a' : YESIL, back((lt - 0.2) / 0.4), 52);
    const a = c.nokta(540, TIP - 60); c.etiket(0, a[0], a[1], 0.9); const b = c.nokta(540, TIP + 330); c.etiket(1, b[0], b[1], d * 0.45);
  };

  S.ilk_katman = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'gri'); const YB = 1040, g1 = back((lt - 0.3) / 0.5), g2 = back((lt - 0.9) / 0.5);
    c.dunya([540, 900, 0.98], [540, 940, 1.08], function () {
      yatak(x, YB, -300, 1400);
      [[300, 74, false], [780, 14, true]].forEach(function (pn, k) {
        const cx = pn[0], gap = pn[1], dogru = pn[2], hareket = Math.sin(t * 1.6 + k) * 70, tip = YB - gap;
        nozul(x, cx + hareket * 0.0, tip, 1, t, 0.75, 40, false);
        const bw = dogru ? 52 : 34, bh = dogru ? 13 : 34;
        for (let i = -3; i <= 3; i++) {
          const px = cx + i * (dogru ? 50 : 62), yy = dogru ? YB - bh : YB - bh * 0.5 - Math.abs(Math.sin(t * 3 + i)) * 6 - (Math.abs(i) > 1 ? (Math.abs(i) - 1) * 14 * sm((lt - 0.8) / 1.0) : 0);
          x.fillStyle = dogru ? '#f08a3a' : '#e8782a'; x.beginPath(); if (dogru) rr(x, px - bw / 2, yy, bw, bh, 6); else x.ellipse(px, yy + bh / 2 + 4, bw / 2, bh / 2, 0, 0, 6.3); x.fill();
        }
      });
    });
    rozet(x, '✗ ÇOK YÜKSEK', 300, 400, KIRMIZI, g1, 40); rozet(x, '✓ DOĞRU', 780, 400, YESIL, g2, 40);
    const a = c.nokta(300, YB - 200); c.etiket(0, a[0], a[1], 1.6, 1); const b = c.nokta(780, YB + 70); c.etiket(1, b[0], b[1], 2.2, -1);
  };

  S.sogutma = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'mavi'); const YB = 1120, ust = Math.round(sayi(p.bas, 230)), alt = Math.round(sayi(p.son, 60)), q = sm(lt / d);
    c.dunya([560, 900, 1.0], [560, 960, 1.14], function () {
      yatak(x, YB, -300, 1400);
      for (let i = 0; i < 12; i++) {   // taşan (overhang) kule: her katman biraz sağa kayar
        const yy = YB - 26 * (i + 1), l = 360 + (i > 4 ? (i - 4) * 36 : 0), w = 220 + (i > 4 ? (i - 4) * 36 : 0), yas = Math.max(0, 1 - (11 - i) * 0.14 - q * 0.0), sogu = cl((lt * 1.2 - (11 - i) * 0.06), 0, 1);
        x.fillStyle = mix(mix('#e8782a', '#9fb4cf', sogu), '#ff9a3c', Math.max(0, 1 - sogu * 1.5) * 0.9); rr(x, l, yy, w, 24, 6); x.fill();
      }
      // fan + hava akışı
      x.save(); x.translate(190, 930); x.fillStyle = '#2c3d5a'; rr(x, -90, -90, 180, 180, 30); x.fill(); x.strokeStyle = '#9fb6d6'; x.lineWidth = 5; x.stroke(); x.rotate(t * 13); x.fillStyle = '#8fd0ff'; for (let i = 0; i < 4; i++) { x.rotate(Math.PI / 2); x.beginPath(); x.ellipse(32, 0, 34, 14, 0, 0, 6.3); x.fill(); } x.restore();
      x.strokeStyle = 'rgba(160,220,255,0.85)'; x.lineWidth = 7; x.lineCap = 'round';
      for (let r = 0; r < 5; r++) { const yy = 860 + r * 46, off = (t * 220 + r * 50) % 150; x.setLineDash([46, 104]); x.lineDashOffset = -off; x.beginPath(); x.moveTo(300, yy); x.quadraticCurveTo(420, yy - 30 + r * 10, 560, yy + 20 - r * 12); x.stroke(); } x.setLineDash([]);
      const dx = lerp(-120, 120, sm((Math.sin(t * 1.4) + 1) / 2)); x.save(); x.translate(560 + dx + 180, YB - 26 * 12 - 4 + 160 - 160); nozul(x, 0, 0, 1, t, 0.55, 30, false); x.restore();
    });
    const der = Math.round(lerp(ust, alt, q)); kart(x, 870, 330, 330, 128, back((lt - 0.3) / 0.5)); yazi(x, der + ' °C', 870, 320, 64, mix('#ff5a14', '#2b7de9', q), 'center', false);
    const a = c.nokta(190, 930); c.etiket(0, a[0], a[1], 1.0); const b = c.nokta(900, YB - 26 * 12 + 40); c.etiket(1, b[0], b[1], 2.0);
  };

  S.nem = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'yesil'); const g = back((lt - 0.2) / 0.5);
    c.dunya([540, 820, 0.95], [540, 840, 1.06], function () {
      makara(x, 270, 820, 190, t * 0.3, '#3aa0e0', 1);
      for (let k = 0; k < 9; k++) { const q = (t * 0.55 + k / 9) % 1, ang = k * 0.9, px = 270 + Math.cos(ang) * (420 - q * 280), py = 820 + Math.sin(ang) * (300 - q * 200) - 80; x.fillStyle = 'rgba(120,200,255,' + (0.9 - q * 0.5) + ')'; x.beginPath(); x.moveTo(px, py - 18); x.quadraticCurveTo(px + 13, py + 2, px, py + 14); x.quadraticCurveTo(px - 13, py + 2, px, py - 18); x.fill(); }
      x.strokeStyle = '#ffd36b'; x.lineWidth = 8; x.lineCap = 'round'; x.beginPath(); x.moveTo(500, 820); x.lineTo(590, 820); x.moveTo(570, 795); x.lineTo(595, 820); x.lineTo(570, 845); x.stroke();
      nozul(x, 800, 1130, 1, t, 0.8, 70, false);
      for (let k = 0; k < 10; k++) { const q = (t * 0.9 + k / 10) % 1, bx = 800 + Math.sin(k * 3.1) * 30, by = 1010 - q * 300; x.fillStyle = 'rgba(255,255,255,' + (0.8 * (1 - q)) + ')'; x.beginPath(); x.arc(bx, by, 6 + (k % 3) * 3 + q * 8, 0, 6.3); x.fill(); }
      const pat = Math.floor(t * 5) % 4; x.fillStyle = '#ff9a3c'; for (let k = 0; k < 6; k++) { const q = ((t * 1.7 + k * 0.31) % 1), px = 800 + (k % 2 ? 1 : -1) * q * 90, py = 1135 + q * 40 - Math.sin(q * 3) * 50; x.beginPath(); x.arc(px, py, 5 - q * 3, 0, 6.3); x.fill(); } void pat;
      yatak(x, 1150, 560, 1100);
    });
    rozet(x, '💧 NEM ÇEKTİ', 270, 340, '#2b7de9', g, 42); rozet(x, 'ÇITIR ÇITIR', 800, 340, '#e0a31a', back((lt - 1.0) / 0.5), 42);
    const a = c.nokta(270, 960); c.etiket(0, a[0], a[1], 1.4, 1); const b = c.nokta(800, 900); c.etiket(1, b[0], b[1], 2.0, -1);
  };

  S.stringing = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'mor'); const YB = 1180, ph = lt / d, geriCek = ph > 0.5, uz = 420;
    c.dunya([540, 930, 0.98], [540, 960, 1.1], function () {
      yatak(x, YB, -300, 1400);
      [320, 760].forEach(function (cx) { x.fillStyle = '#f08a3a'; rr(x, cx - 60, YB - 300, 120, 300, 10); x.fill(); x.fillStyle = 'rgba(255,255,255,0.18)'; for (let k = 1; k < 12; k++) x.fillRect(cx - 54, YB - 26 * k, 108, 3); });
      const u = (lt * (geriCek ? 0.9 : 0.8)) % 1, gidis = u < 0.5 ? u * 2 : 2 - u * 2, nx = lerp(320, 760, sm(gidis)), ny = YB - 330 - Math.sin(gidis * Math.PI) * 60;
      if (!geriCek || (geriCek && ph < 0.55)) { const aci = geriCek ? 1 - (ph - 0.5) / 0.05 : 1; x.strokeStyle = 'rgba(255,214,150,' + (0.9 * aci) + ')'; x.lineWidth = 4; for (let k = 0; k < 7; k++) { const a = Math.min(1, lt * 0.9 + 0.0) , sag = 18 + k * 7; x.beginPath(); x.moveTo(370 + k * 3, YB - 300 + k * 7 * 0.3); x.quadraticCurveTo(540, YB - 300 + sag + 30, 710 - k * 3, YB - 300 + k * 7 * 0.3); x.stroke(); void a; } }
      nozul(x, nx, ny + 0, 1, t, 0.7, geriCek ? -20 : 50, false);
      if (geriCek) { x.strokeStyle = '#ffd36b'; x.lineWidth = 8; x.lineCap = 'round'; const ay = ny - 300 + Math.sin(t * 6) * 6; x.beginPath(); x.moveTo(nx + 90, ay + 30); x.lineTo(nx + 90, ay - 30); x.moveTo(nx + 72, ay - 12); x.lineTo(nx + 90, ay - 32); x.lineTo(nx + 108, ay - 12); x.stroke(); }
    });
    rozet(x, geriCek ? '✓ GERİ ÇEKME AÇIK' : '✗ GERİ ÇEKME KAPALI', 540, 360, geriCek ? YESIL : KIRMIZI, back((lt - 0.2) / 0.4), 46);
    const a = c.nokta(320, YB - 300); c.etiket(0, a[0], a[1], 0.9, 1); const b = c.nokta(760, YB - 130); c.etiket(1, b[0], b[1], d * 0.55, -1);
  };

  S.warping = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'turuncu'); const YB = 1120, ph = lt / d, kivrim = ph < 0.5 ? sm(ph / 0.35) : 1 - sm((ph - 0.5) / 0.3), isiBlok = sm((ph - 0.45) / 0.2);
    c.dunya([540, 940, 1.0], [540, 970, 1.1], function () {
      if (isiBlok > 0.01) { const gl = x.createLinearGradient(0, YB + 40, 0, YB - 160); gl.addColorStop(0, 'rgba(255,120,30,' + (0.7 * isiBlok) + ')'); gl.addColorStop(1, 'rgba(255,120,30,0)'); x.fillStyle = gl; x.fillRect(180, YB - 160, 720, 200); }
      yatak(x, YB, -300, 1400);
      x.fillStyle = '#f08a3a'; x.strokeStyle = '#ffb066'; x.lineWidth = 4; x.beginPath();
      const N = 24, ust = [], alt = [];
      for (let i = 0; i <= N; i++) { const u = i / N, px = 240 + u * 600, e = Math.pow(Math.abs(u - 0.5) * 2, 2.2) * 130 * kivrim; ust.push([px, YB - 44 - e]); alt.push([px, YB - e]); }
      x.moveTo(ust[0][0], ust[0][1]); ust.forEach(p => x.lineTo(p[0], p[1])); for (let i = N; i >= 0; i--) x.lineTo(alt[i][0], alt[i][1]); x.closePath(); x.fill(); x.stroke();
      if (kivrim > 0.4) { x.strokeStyle = 'rgba(255,90,79,0.95)'; x.lineWidth = 7; [alt[0], alt[N]].forEach(function (p, k) { const dir = k ? 1 : -1; x.beginPath(); x.moveTo(p[0] + dir * 40, p[1] - 80); x.lineTo(p[0] + dir * 40, p[1] - 20); x.moveTo(p[0] + dir * 22, p[1] - 38); x.lineTo(p[0] + dir * 40, p[1] - 18); x.lineTo(p[0] + dir * 58, p[1] - 38); x.stroke(); }); }
    });
    rozet(x, ph < 0.5 ? '✗ KÖŞELER KALKIYOR' : '✓ TABLA SICAK: YAPIŞTI', 540, 360, ph < 0.5 ? KIRMIZI : YESIL, back((lt - 0.2) / 0.4), 44);
    const a = c.nokta(240, YB - 90); c.etiket(0, a[0], a[1], 1.0, 1); const b = c.nokta(540, YB + 80); c.etiket(1, b[0], b[1], d * 0.55, 1);
  };

  S.karsilastir = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'mavi'); const a = p.a || { ad: 'A', deger: 60 }, b = p.b || { ad: 'B', deger: 40 }, mx = Math.max(sayi(a.deger, 1), sayi(b.deger, 1), 1e-9), q = eo((lt - 0.3) / 1.2), ond = mx < 10 ? 2 : 0, fmt = v => (ond ? v.toFixed(ond).replace('.', ',') : String(Math.round(v))), birim = p.birim || '';   // küçük değerlerde (0,02 mm) ondalık göster
    c.dunya([540, 800, 1.0], [540, 800, 1.06], function () {
      x.fillStyle = 'rgba(255,255,255,0.08)'; rr(x, 90, 380, 900, 780, 40); x.fill();
      [[a, 330, TURUNCU], [b, 750, MAVI]].forEach(function (pr) {
        const o = pr[0], cx = pr[1], renk = pr[2], h = 560 * (sayi(o.deger, 0) / mx) * q;
        const g = x.createLinearGradient(0, 1100 - h, 0, 1100); g.addColorStop(0, renk); g.addColorStop(1, mix(renk, '#000000', 0.35)); x.fillStyle = g; rr(x, cx - 110, 1100 - h, 220, Math.max(h, 8), 22); x.fill();
        x.fillStyle = 'rgba(255,255,255,0.22)'; rr(x, cx - 90, 1100 - h + 10, 40, Math.max(h - 20, 0), 14); x.fill();
        yazi(x, fmt(sayi(o.deger, 0) * q) + (birim ? ' ' + birim : ''), cx, 1100 - h - 52, 66, '#fff'); yazi(x, String(o.ad), cx, 1160, 52, '#fff');
      });
      x.fillStyle = '#fff'; x.beginPath(); x.arc(540, 800, 52, 0, 6.3); x.fill(); yazi(x, 'VS', 540, 804, 44, KOYU, 'center', false);
    });
    const e0 = c.nokta(540, 1230); c.etiket(0, e0[0], e0[1], 1.8, 1); const e1 = c.nokta(540, 1290); c.etiket(1, e1[0], e1[1], 2.6, 1);
  };

  S.sayi = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'yesil'); const deger = sayi(p.deger, 70), maks = Math.max(1, sayi(p.maks, 100)), q = eo((lt - 0.2) / 1.4), birim = p.birim || '%';
    c.dunya([540, 780, 0.95], [540, 780, 1.1], function () {
      x.lineWidth = 56; x.lineCap = 'round'; x.strokeStyle = 'rgba(255,255,255,0.14)'; x.beginPath(); x.arc(540, 780, 270, 0.75 * Math.PI, 2.25 * Math.PI); x.stroke();
      const bit = 0.75 * Math.PI + 1.5 * Math.PI * Math.min(1, deger / maks) * q, g = x.createLinearGradient(260, 500, 820, 1000); g.addColorStop(0, '#ffd36b'); g.addColorStop(1, '#ff5a14'); x.strokeStyle = g; x.beginPath(); x.arc(540, 780, 270, 0.75 * Math.PI, bit); x.stroke();
      x.fillStyle = '#fff'; x.beginPath(); x.arc(540 + Math.cos(bit) * 270, 780 + Math.sin(bit) * 270, 22, 0, 6.3); x.fill();
      yazi(x, Math.round(deger * q) + '', 540, 770, 210, '#fff'); yazi(x, birim, 540, 930, 70, '#ffd36b'); if (p.etiket) yazi(x, String(p.etiket), 540, 1130, 52, '#d6e4f7');
    });
    const a = c.nokta(540, 640); c.etiket(0, a[0], a[1], 1.2, 1);
  };

  S.kontrol_listesi = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'mor'); const m = (p.maddeler && p.maddeler.length ? p.maddeler : ['Birinci adım', 'İkinci adım', 'Üçüncü adım']).slice(0, 5), gap = Math.max(0.5, (d - 1.0) / m.length);
    c.dunya([540, 800, 1.0], [540, 800, 1.05], function () {
      m.forEach(function (s, i) {
        const t0 = 0.3 + i * gap * 0.9, g = back((lt - t0) / 0.5); if (g <= 0) return; const y = 560 + i * 170, kay = (1 - Math.min(g, 1)) * 600;
        x.save(); x.translate(kay, 0); x.shadowColor = 'rgba(0,0,0,0.35)'; x.shadowBlur = 18; x.fillStyle = '#fff'; rr(x, 110, y - 62, 860, 124, 34); x.fill(); x.shadowBlur = 0;
        const tik = sm((lt - t0 - 0.35) / 0.3); x.fillStyle = mix('#d9e1ec', YESIL, tik); x.beginPath(); x.arc(200, y, 42, 0, 6.3); x.fill();
        x.strokeStyle = '#fff'; x.lineWidth = 12; x.lineCap = 'round'; x.lineJoin = 'round'; if (tik > 0) { x.beginPath(); x.moveTo(180, y + 2); x.lineTo(196, y + 18); x.lineTo(224, y - 16); x.stroke(); }
        x.font = '800 48px IB, Inter, sans-serif'; x.textAlign = 'left'; x.textBaseline = 'middle'; x.fillStyle = KOYU; let txt = String(s); while (x.measureText(txt).width > 660 && txt.length > 6) txt = txt.slice(0, -2); x.fillText(txt, 272, y + 3); x.restore();
      });
    });
  };

  S.dolgu = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'gri'); const hedef = Math.round(sayi(p.yuzde, 25)), q = sm(lt / d), yuz = Math.round(lerp(5, hedef, q)), aralik = lerp(150, 32 + (100 - Math.min(100, hedef)) * 0.9, q);
    c.dunya([540, 800, 1.0], [540, 800, 1.06], function () {
      x.fillStyle = '#f08a3a'; rr(x, 220, 420, 640, 640, 30); x.fill(); x.fillStyle = '#1c2a40'; rr(x, 270, 470, 540, 540, 14); x.fill();
      x.strokeStyle = '#ffb066'; x.lineWidth = 8; x.lineCap = 'round'; x.save(); x.beginPath(); x.rect(270, 470, 540, 540); x.clip();
      for (let g = 270; g <= 810; g += aralik) { x.beginPath(); x.moveTo(g, 470); x.lineTo(g, 1010); x.stroke(); x.beginPath(); x.moveTo(270, g + 200); x.lineTo(810, g + 200); x.stroke(); }
      x.strokeStyle = 'rgba(255,176,102,0.5)'; x.lineWidth = 5; for (let g = -540; g < 540; g += aralik * 1.4) { x.beginPath(); x.moveTo(270 + g, 470); x.lineTo(810 + g, 1010); x.stroke(); } x.restore();
      x.fillStyle = 'rgba(255,255,255,0.14)'; rr(x, 220, 1130, 640, 28, 14); x.fill(); x.fillStyle = mix('#4fc3ff', '#ff5a14', q); rr(x, 220, 1130, 640 * (yuz / 100), 28, 14); x.fill(); x.fillStyle = '#fff'; x.beginPath(); x.arc(220 + 640 * (yuz / 100), 1144, 30, 0, 6.3); x.fill();
    });
    yazi(x, '%' + yuz, 540, 330, 130, '#fff'); yazi(x, 'DOLGU', 540, 250, 40, '#ffd36b');
    const a = c.nokta(540, 740); c.etiket(0, a[0], a[1], 1.4, 1);
  };

  S.hiz = function (c) {
    const { x, t, lt, d, p } = c; c.arka(c.p.tema || 'turuncu'); const q = sm(lt / d), v = Math.round(lerp(40, sayi(p.hiz, 220), q)), YB = 1150, sal = 3 + q * 17;
    c.dunya([540, 920, 1.0], [540, 940, 1.1], function () {
      yatak(x, YB, -300, 1400);
      x.fillStyle = '#f08a3a'; x.strokeStyle = '#ffb066'; x.lineWidth = 4; x.beginPath(); x.moveTo(740, YB);
      for (let y = 0; y <= 420; y += 6) x.lineTo(740 + Math.sin(y * 0.08 - t * 5) * sal * (y / 420), YB - y); for (let y = 420; y >= 0; y -= 6) x.lineTo(800 + Math.sin(y * 0.08 - t * 5) * sal * (y / 420), YB - y); x.closePath(); x.fill(); x.stroke();
      const nx = 300 + (Math.sin(t * (2 + q * 6)) * 0.5 + 0.5) * 440; x.save(); x.translate(nx, YB - 440); nozul(x, 0, 0, 1, t, 0.6, 30 + v, false); x.restore();
      x.strokeStyle = 'rgba(255,255,255,0.35)'; x.lineWidth = 6; for (let k = 0; k < 5; k++) { x.beginPath(); x.moveTo(nx - 120 - k * 30, YB - 520 + k * 26); x.lineTo(nx - 60 - k * 30 - q * 50, YB - 520 + k * 26); x.stroke(); }
    });
    kart(x, 540, 350, 440, 150, back((lt - 0.2) / 0.5)); yazi(x, v + ' mm/s', 540, 345, 76, mix('#3cc47a', '#ff3b30', q), 'center', false);
    const a = c.nokta(800, YB - 300); c.etiket(0, a[0], a[1], d * 0.55, -1);
  };

  S.destek = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'mavi'); const YB = 1160, ph = lt / d, destek = ph > 0.5, sark = destek ? 0 : sm(ph / 0.4) * 60;
    c.dunya([540, 950, 1.0], [540, 970, 1.1], function () {
      yatak(x, YB, -300, 1400);
      x.fillStyle = '#f08a3a'; rr(x, 260, YB - 420, 150, 420, 14); x.fill();
      x.beginPath(); x.moveTo(410, YB - 420); x.lineTo(410 + 520, YB - 420 + sark); x.lineTo(410 + 520, YB - 380 + sark); x.lineTo(410, YB - 380); x.closePath(); x.fill();
      if (!destek) { x.strokeStyle = 'rgba(255,214,150,0.9)'; x.lineWidth = 4; for (let k = 0; k < 6; k++) { x.beginPath(); x.moveTo(500 + k * 80, YB - 380 + sark * (0.2 + k * 0.16)); x.quadraticCurveTo(505 + k * 80, YB - 300 + sark * 0.3, 520 + k * 80, YB - 240 + k * 10); x.stroke(); } }
      else { const e = sm((ph - 0.5) / 0.25); x.fillStyle = 'rgba(100,200,255,0.55)'; x.strokeStyle = '#8fd0ff'; x.lineWidth = 3; [520, 640, 760, 880].forEach(function (px, k) { const h = 380 * e * cl(1.5 - k * 0.15); x.beginPath(); x.rect(px - 22, YB - h, 44, h - 0); x.fill(); x.stroke(); for (let y = YB - 20; y > YB - h; y -= 30) { x.beginPath(); x.moveTo(px - 22, y); x.lineTo(px + 22, y - 20); x.stroke(); } }); }
    });
    rozet(x, destek ? '✓ DESTEKLİ' : '✗ DESTEKSİZ SARKIYOR', 540, 360, destek ? YESIL : KIRMIZI, back((lt - 0.2) / 0.4), 46);
    const a = c.nokta(700, YB - 400); c.etiket(0, a[0], a[1], 1.0, 1); const b = c.nokta(760, YB - 120); c.etiket(1, b[0], b[1], d * 0.62, 1);
  };

  S.kapanis = function (c) {
    const { x, t, lt, d } = c; c.arka(c.p.tema || 'mor');
    c.dunya([540, 820, 0.9], [540, 820, 1.04], function () {
      x.save(); x.translate(540, 760); for (let k = 0; k < 14; k++) { x.rotate(Math.PI * 2 / 14); x.fillStyle = 'rgba(255,255,255,' + (k % 2 ? 0.05 : 0.02) + ')'; x.beginPath(); x.moveTo(0, 0); x.lineTo(900, -70); x.lineTo(900, 70); x.closePath(); x.fill(); } x.restore();
      const g = back((lt - 0.2) / 0.6), pulse = 1 + 0.04 * Math.sin(t * 4); x.save(); x.translate(540, 700); x.scale(Math.min(g, 1.05) * pulse, Math.min(g, 1.05) * pulse); x.shadowColor = 'rgba(0,0,0,0.45)'; x.shadowBlur = 40; x.fillStyle = '#ffffff'; x.beginPath(); x.arc(0, 0, 230, 0, 6.3); x.fill(); x.shadowBlur = 0;
      if (c.p.ikon && IKONLAR[c.p.ikon]) { x.scale(2.8, 2.8); IKONLAR[c.p.ikon](x, t, { renk: 'turuncu' }); } else { for (let k = 0; k < 5; k++) { x.fillStyle = ['#ff7a1a', '#ff9a3c', '#ffb347', '#4fc3ff', '#3cc47a'][k]; rr(x, -130 + k * 6, 100 - k * 44, 260 - k * 12, 34, 12); x.fill(); } } x.restore();
      for (let k = 0; k < 9; k++) { const q = (t * 0.45 + k / 9) % 1, px = 540 + Math.sin(k * 2.4) * 380, py = 1000 - q * 700; x.save(); x.translate(px, py); x.globalAlpha = Math.sin(q * Math.PI); x.fillStyle = k % 2 ? '#ff5a8f' : '#ffd36b'; x.beginPath(); x.moveTo(0, 12); x.bezierCurveTo(-34, -16, -12, -38, 0, -16); x.bezierCurveTo(12, -38, 34, -16, 0, 12); x.fill(); x.restore(); }
    });
    const b = back((lt - 0.7) / 0.5); x.save(); x.translate(540, 1100); x.scale(Math.min(b, 1.05) * (1 + 0.05 * Math.sin(t * 5)), Math.min(b, 1.05) * (1 + 0.05 * Math.sin(t * 5))); x.shadowColor = 'rgba(0,0,0,0.4)'; x.shadowBlur = 24; x.fillStyle = TURUNCU; rr(x, -230, -62, 460, 124, 62); x.fill(); x.shadowBlur = 0; x.restore();
    yazi(x, 'TAKİP ET', 540, 1100, 60, '#fff', 'center', false); yazi(x, '@gurtechs3d', 540, 1230, 60, '#ffd36b');
  };

  /* ---------- ÖZEL SAHNE: yapay zekâ tarifli (şekiller, oklar, yazılar, ikonlar, hareket) ---------- */
  const RENK = { turuncu: '#ff7a1a', mavi: '#4fc3ff', yesil: '#3cc47a', kirmizi: '#ff5a4f', sari: '#ffd36b', mor: '#b49cff', pembe: '#ff7fb0', beyaz: '#ffffff', koyu: '#12304f', gri: '#8fa6c4', kahve: '#6b3a1e', siyah: '#10161f' };
  const renk = v => RENK[v] || (/^#[0-9a-fA-F]{6}$/.test(v || '') ? v : '#ffffff');
  const EGRI = { yumusak: sm, lineer: v => cl(v), ziplama: back, cikis: eo };
  const IKONLAR = {
    nozul: (c, t, p) => nozul(c, 0, 60, 1, t, 0.3, 40, false), nozul_tikali: (c, t, p) => nozul(c, 0, 60, 1, t, 0.3, 14, true), makara: (c, t, p) => makara(c, 0, 0, 60, t, renk(p.renk || 'turuncu'), 1),
    disli: (c, t) => disli(c, 0, 0, 1, t, 62, 48, 10),
    fan: (c, t) => { c.fillStyle = '#2c3d5a'; rr(c, -60, -60, 120, 120, 22); c.fill(); c.strokeStyle = '#9fb6d6'; c.lineWidth = 4; c.stroke(); c.save(); c.rotate(t * 12); c.fillStyle = '#8fd0ff'; for (let i = 0; i < 4; i++) { c.rotate(Math.PI / 2); c.beginPath(); c.ellipse(22, 0, 24, 10, 0, 0, 6.3); c.fill(); } c.restore(); },
    termometre: (c, t, p) => { const d = cl(p.doluluk == null ? 0.7 : p.doluluk); c.fillStyle = '#e9edf3'; rr(c, -14, -70, 28, 120, 14); c.fill(); c.fillStyle = mix('#4fc3ff', '#ff3b30', d); rr(c, -9, 50 - 110 * d - 6, 18, 110 * d + 6, 9); c.fill(); c.beginPath(); c.arc(0, 56, 26, 0, 6.3); c.fillStyle = mix('#4fc3ff', '#ff3b30', d); c.fill(); },
    damla: (c) => { c.fillStyle = '#5ab8ff'; c.beginPath(); c.moveTo(0, -42); c.quadraticCurveTo(34, 6, 0, 38); c.quadraticCurveTo(-34, 6, 0, -42); c.fill(); c.fillStyle = 'rgba(255,255,255,0.5)'; c.beginPath(); c.ellipse(-9, 8, 5, 10, 0.4, 0, 6.3); c.fill(); },
    alev: (c, t) => { const w = Math.sin(t * 9) * 4; c.fillStyle = '#ff7a1a'; c.beginPath(); c.moveTo(0, -60 + w); c.quadraticCurveTo(46, -2, 22, 38); c.quadraticCurveTo(0, 56, -22, 38); c.quadraticCurveTo(-46, -2, 0, -60 + w); c.fill(); c.fillStyle = '#ffd36b'; c.beginPath(); c.moveTo(0, -20 + w); c.quadraticCurveTo(22, 12, 10, 38); c.quadraticCurveTo(0, 46, -10, 38); c.quadraticCurveTo(-22, 12, 0, -20 + w); c.fill(); },
    duman: (c, t) => { for (let k = 0; k < 4; k++) { const q = (t * 0.5 + k / 4) % 1; c.fillStyle = 'rgba(200,205,215,' + (0.6 * (1 - q)) + ')'; c.beginPath(); c.arc(Math.sin(q * 8 + k) * 22, 40 - q * 110, 14 + q * 26, 0, 6.3); c.fill(); } },
    tik: (c) => { c.fillStyle = '#3cc47a'; c.beginPath(); c.arc(0, 0, 46, 0, 6.3); c.fill(); c.strokeStyle = '#fff'; c.lineWidth = 12; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(-20, 2); c.lineTo(-6, 18); c.lineTo(22, -14); c.stroke(); },
    carpi: (c) => { c.fillStyle = '#ff5a4f'; c.beginPath(); c.arc(0, 0, 46, 0, 6.3); c.fill(); c.strokeStyle = '#fff'; c.lineWidth = 12; c.lineCap = 'round'; c.beginPath(); c.moveTo(-18, -18); c.lineTo(18, 18); c.moveTo(18, -18); c.lineTo(-18, 18); c.stroke(); },
    uyari: (c) => { c.fillStyle = '#ffc533'; c.beginPath(); c.moveTo(0, -48); c.lineTo(48, 38); c.lineTo(-48, 38); c.closePath(); c.fill(); c.fillStyle = '#12304f'; c.fillRect(-5, -16, 10, 30); c.beginPath(); c.arc(0, 26, 6, 0, 6.3); c.fill(); },
    saat: (c, t) => { c.fillStyle = '#fff'; c.beginPath(); c.arc(0, 0, 48, 0, 6.3); c.fill(); c.strokeStyle = '#12304f'; c.lineWidth = 6; c.stroke(); c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.sin(t * 3) * 30, -Math.cos(t * 3) * 30); c.stroke(); c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.sin(t * 0.25) * 20, -Math.cos(t * 0.25) * 20); c.stroke(); },
    lupa: (c) => { c.strokeStyle = '#fff'; c.lineWidth = 9; c.beginPath(); c.arc(-8, -8, 30, 0, 6.3); c.stroke(); c.lineCap = 'round'; c.beginPath(); c.moveTo(14, 14); c.lineTo(42, 42); c.stroke(); },
    yildiz: (c, t) => { c.fillStyle = '#ffd36b'; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 22 : 50; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fill(); },
    parca: (c, t, p) => { for (let i = 0; i < 5; i++) { c.fillStyle = mix('#ff7a1a', '#ffb347', i / 5); rr(c, -50 + i * 2, 38 - i * 20, 100 - i * 4, 18, 6); c.fill(); } },
    filament: (c, t) => { c.strokeStyle = '#eaf3ff'; c.lineWidth = 12; c.lineCap = 'round'; c.beginPath(); for (let u = -60; u <= 60; u += 4) { const y = Math.sin(u * 0.08 + t * 2) * 14; u === -60 ? c.moveTo(u, y) : c.lineTo(u, y); } c.stroke(); },
    yatak: (c) => { c.fillStyle = '#3a4c68'; rr(c, -80, -12, 160, 24, 8); c.fill(); c.fillStyle = '#6d86a8'; c.fillRect(-80, -12, 160, 4); },
    yumurta: (c) => { c.fillStyle = '#f6e6c8'; c.beginPath(); c.moveTo(0, -56); c.bezierCurveTo(38, -56, 46, 6, 40, 22); c.bezierCurveTo(32, 54, -32, 54, -40, 22); c.bezierCurveTo(-46, 6, -38, -56, 0, -56); c.fill(); c.fillStyle = 'rgba(255,255,255,0.65)'; c.beginPath(); c.ellipse(-16, -16, 7, 15, 0.3, 0, 6.3); c.fill(); },
    kalp: (c, t) => { const s = 1 + 0.06 * Math.sin(t * 5); c.scale(s, s); c.fillStyle = '#ff4f6b'; c.beginPath(); c.moveTo(0, 42); c.bezierCurveTo(-64, -4, -42, -52, 0, -22); c.bezierCurveTo(42, -52, 64, -4, 0, 42); c.fill(); },
    ampul: (c, t) => { c.fillStyle = '#ffd36b'; c.beginPath(); c.arc(0, -10, 32, 0, 6.3); c.fill(); c.fillStyle = '#c9d3e0'; rr(c, -16, 20, 32, 14, 4); c.fill(); rr(c, -12, 36, 24, 10, 4); c.fill(); c.strokeStyle = 'rgba(255,200,60,0.7)'; c.lineWidth = 5; c.lineCap = 'round'; for (let i = 0; i < 6; i++) { const a = -Math.PI + i * Math.PI / 5, q = 0.6 + 0.4 * Math.sin(t * 4 + i); c.beginPath(); c.moveTo(Math.cos(a) * 44, -10 + Math.sin(a) * 44); c.lineTo(Math.cos(a) * (44 + 12 * q), -10 + Math.sin(a) * (44 + 12 * q)); c.stroke(); } },
    dunya: (c, t) => { c.fillStyle = '#2f8fe0'; c.beginPath(); c.arc(0, 0, 46, 0, 6.3); c.fill(); c.save(); c.beginPath(); c.arc(0, 0, 46, 0, 6.3); c.clip(); c.fillStyle = '#3cc47a'; const o = (t * 14) % 120; for (let k = -1; k < 2; k++) { const dx = -60 + k * 120 + o; c.beginPath(); c.ellipse(dx, -10, 24, 18, 0.3, 0, 6.3); c.ellipse(dx + 40, 20, 18, 22, 0, 0, 6.3); c.fill(); } c.restore(); c.strokeStyle = 'rgba(255,255,255,0.5)'; c.lineWidth = 3; c.beginPath(); c.arc(0, 0, 46, 0, 6.3); c.stroke(); },
    kitap: (c) => { c.fillStyle = '#4f7cff'; rr(c, -48, -36, 96, 74, 8); c.fill(); c.fillStyle = '#f4f1e8'; rr(c, -42, -30, 40, 62, 4); c.fill(); rr(c, 2, -30, 40, 62, 4); c.fill(); c.strokeStyle = '#9aa7c0'; c.lineWidth = 3; for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(-36, -18 + i * 14); c.lineTo(-8, -18 + i * 14); c.moveTo(8, -18 + i * 14); c.lineTo(36, -18 + i * 14); c.stroke(); } },
    ev: (c) => { c.fillStyle = '#f2d9b0'; c.fillRect(-36, -4, 72, 46); c.fillStyle = '#d9534f'; c.beginPath(); c.moveTo(-50, -2); c.lineTo(0, -48); c.lineTo(50, -2); c.closePath(); c.fill(); c.fillStyle = '#6b3a1e'; c.fillRect(-9, 14, 18, 28); c.fillStyle = '#8fd0ff'; c.fillRect(14, 8, 14, 14); c.fillRect(-28, 8, 14, 14); },
    yaprak: (c, t) => { c.rotate(Math.sin(t * 2) * 0.1); c.fillStyle = '#3cc47a'; c.beginPath(); c.moveTo(-34, 40); c.bezierCurveTo(-58, -10, -10, -54, 44, -44); c.bezierCurveTo(52, 8, 14, 52, -34, 40); c.fill(); c.strokeStyle = '#1f7a48'; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(-34, 40); c.lineTo(22, -22); c.stroke(); },
    para: (c, t) => { c.save(); c.scale(Math.cos(t * 2.4) * 0.9 + 0.1 * Math.sign(Math.cos(t * 2.4) || 1), 1); c.fillStyle = '#ffc533'; c.beginPath(); c.arc(0, 0, 44, 0, 6.3); c.fill(); c.strokeStyle = '#e09b00'; c.lineWidth = 6; c.stroke(); c.fillStyle = '#b97a00'; c.font = 'bold 50px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('₺', 0, 3); c.restore(); },
    gunes: (c, t) => { c.fillStyle = '#ffd36b'; c.beginPath(); c.arc(0, 0, 26, 0, 6.3); c.fill(); c.strokeStyle = '#ffb347'; c.lineWidth = 7; c.lineCap = 'round'; c.save(); c.rotate(t * 0.8); for (let i = 0; i < 8; i++) { c.rotate(Math.PI / 4); c.beginPath(); c.moveTo(38, 0); c.lineTo(52, 0); c.stroke(); } c.restore(); },
    bulut: (c, t) => { c.fillStyle = '#dfe8f5'; c.beginPath(); c.arc(-24, 8, 22, 0, 6.3); c.arc(2, -10, 28, 0, 6.3); c.arc(28, 8, 22, 0, 6.3); c.fill(); rr(c, -42, 6, 86, 24, 12); c.fill(); },
    insan: (c, t) => { c.fillStyle = '#ffcf9f'; c.beginPath(); c.arc(0, -26, 17, 0, 6.3); c.fill(); c.fillStyle = '#4f7cff'; c.beginPath(); c.moveTo(-32, 46); c.quadraticCurveTo(-34, 0, 0, -4); c.quadraticCurveTo(34, 0, 32, 46); c.closePath(); c.fill(); },
    tavuk: (c, t) => { const z = Math.sin(t * 5) * 0.06; c.rotate(z); c.fillStyle = '#fff8e6'; c.beginPath(); c.ellipse(-4, 12, 40, 32, 0, 0, 6.3); c.fill(); c.beginPath(); c.arc(26, -22, 20, 0, 6.3); c.fill(); c.fillStyle = '#e8503a'; c.beginPath(); c.arc(20, -44, 7, 0, 6.3); c.arc(30, -44, 7, 0, 6.3); c.fill(); c.fillStyle = '#ffa31a'; c.beginPath(); c.moveTo(44, -24); c.lineTo(60, -18); c.lineTo(44, -14); c.closePath(); c.fill(); c.fillStyle = '#10161f'; c.beginPath(); c.arc(30, -26, 3.5, 0, 6.3); c.fill(); c.strokeStyle = '#ffa31a'; c.lineWidth = 5; c.lineCap = 'round'; c.beginPath(); c.moveTo(-8, 42); c.lineTo(-8, 56); c.moveTo(8, 42); c.lineTo(8, 56); c.stroke(); c.fillStyle = '#f1dcae'; c.beginPath(); c.ellipse(-16, 12, 18, 12, -0.4, 0, 6.3); c.fill(); },
    kilit: (c) => { c.strokeStyle = '#fff'; c.lineWidth = 9; c.beginPath(); c.arc(0, -14, 22, Math.PI, 0); c.stroke(); c.fillStyle = '#ffc533'; rr(c, -34, -14, 68, 56, 10); c.fill(); }
  };
  function ozelEleman(c, e, lt, t, id) {
    const g = (e.t && e.t[0]) || 0, cik = (e.t && e.t[1] != null) ? e.t[1] : 1e9;
    if (lt < g || lt > cik) return;
    const pr = { x: 0, y: 0, w: 100, h: 100, r: 0, olcek: 1, donus: 0, opaklik: 1, doluluk: null, cizim: 1, boyut: 48 };
    for (const k in e) if (typeof e[k] === 'number') pr[k] = e[k];
    (e.hareket || []).forEach(function (a) { const q = (EGRI[a.egri] || sm)((lt - (a.t0 || 0)) / Math.max(0.05, (a.t1 || 1) - (a.t0 || 0))); pr[a.o] = lerp(a.den, a.a, q); });
    const d = e.dongu || {};
    if (d.titre) pr.x += Math.sin(t * 22 + id) * d.titre; if (d.yuz) pr.y += Math.sin(t * 1.6 + id) * d.yuz; if (d.dondur) pr.donus += t * d.dondur; if (d.salin) pr.donus += Math.sin(t * 2 + id) * d.salin; if (d.nabiz) pr.olcek *= 1 + d.nabiz * Math.sin(t * 4 + id);
    const al = pr.opaklik * cl((lt - g) / 0.3) * (cik < 1e8 ? cl((cik - lt) / 0.3) : 1); if (al <= 0.01) return;
    const taban = c.globalAlpha; c.save(); c.globalAlpha = taban * al; c.translate(pr.x, pr.y); c.rotate(pr.donus); c.scale(pr.olcek, pr.olcek);
    if (e.golge) { c.shadowColor = 'rgba(0,0,0,0.38)'; c.shadowBlur = 22; c.shadowOffsetY = 10; }
    const rk = renk(e.renk);
    const dolgu = function (x0, y0, x1, y1) { if (!e.renk2) return rk; const r2 = renk(e.renk2), g = e.gradyan === 'yatay' ? c.createLinearGradient(x0, 0, x1, 0) : e.gradyan === 'radyal' ? c.createRadialGradient(0, 0, 0, 0, 0, Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / 2) : c.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, rk); g.addColorStop(1, r2); return g; };
    if (e.tur === 'dikdortgen') {
      const w = pr.w, h = pr.h; c.fillStyle = e.doluluk_zemin ? renk(e.doluluk_zemin) : dolgu(-w / 2, -h / 2, w / 2, h / 2); if (pr.doluluk == null) { rr(c, -w / 2, -h / 2, w, h, pr.r); c.fill(); } else {
        c.fillStyle = 'rgba(255,255,255,0.16)'; rr(c, -w / 2, -h / 2, w, h, pr.r); c.fill(); c.fillStyle = rk; const f = cl(pr.doluluk); if (e.yon === 'dikey') rr(c, -w / 2, h / 2 - h * f, w, Math.max(h * f, 1), pr.r); else rr(c, -w / 2, -h / 2, Math.max(w * f, 1), h, pr.r); c.fill(); }
      if (e.kenar) { c.strokeStyle = renk(e.kenar); c.lineWidth = pr.kalinlik || 5; rr(c, -w / 2, -h / 2, w, h, pr.r); c.stroke(); }
    } else if (e.tur === 'daire') {
      if (e.halka) { c.strokeStyle = rk; c.lineWidth = pr.halka || 10; c.beginPath(); c.arc(0, 0, pr.r || 50, 0, 6.3 * cl(pr.cizim)); c.stroke(); } else { c.fillStyle = dolgu(-(pr.r || 50), -(pr.r || 50), pr.r || 50, pr.r || 50); c.beginPath(); c.arc(0, 0, pr.r || 50, 0, 6.3); c.fill(); }
    } else if (e.tur === 'elips') {
      const rx = pr.rx || 80, ry = pr.ry || 50; c.beginPath(); c.ellipse(0, 0, rx, ry, 0, 0, 6.3 * (e.halka ? cl(pr.cizim) : 1)); if (e.halka) { c.strokeStyle = rk; c.lineWidth = pr.halka || 8; c.stroke(); } else { c.fillStyle = dolgu(-rx, -ry, rx, ry); c.fill(); } if (e.kenar && !e.halka) { c.strokeStyle = renk(e.kenar); c.lineWidth = pr.kalinlik || 5; c.stroke(); }
    } else if (e.tur === 'yay') {
      const a0 = (pr.a0 || 0) * Math.PI / 180, a1 = (pr.a1 || 180) * Math.PI / 180; c.strokeStyle = rk; c.lineWidth = pr.kalinlik || 10; c.lineCap = 'round'; c.beginPath(); c.arc(0, 0, pr.r || 60, a0, a0 + (a1 - a0) * cl(pr.cizim)); c.stroke();
    } else if (e.tur === 'yol') {
      const q = (e.noktalar || []).filter(function (n) { return n && n.length >= 2; }); if (q.length >= 2) {
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, L = 0; q.forEach(function (n, i) { x0 = Math.min(x0, n[0]); y0 = Math.min(y0, n[1]); x1 = Math.max(x1, n[0]); y1 = Math.max(y1, n[1]); if (i) L += Math.hypot(n[0] - q[i - 1][0], n[1] - q[i - 1][1]); });
        const kap = !!e.kapali; c.beginPath(); const nn = q.length;
        if (!e.yumusak || nn < 3) { q.forEach(function (n, i) { if (i) c.lineTo(n[0], n[1]); else c.moveTo(n[0], n[1]); }); }
        else if (kap) { c.moveTo((q[nn - 1][0] + q[0][0]) / 2, (q[nn - 1][1] + q[0][1]) / 2); for (let i = 0; i < nn; i++) { const a = q[i], b = q[(i + 1) % nn]; c.quadraticCurveTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); } }
        else { c.moveTo(q[0][0], q[0][1]); for (let i = 1; i < nn - 1; i++) { const a = q[i], b = q[i + 1]; c.quadraticCurveTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); } c.lineTo(q[nn - 1][0], q[nn - 1][1]); }
        if (kap) c.closePath();
        if (kap && !e.sadece_kenar) { c.fillStyle = dolgu(x0, y0, x1, y1); c.globalAlpha = c.globalAlpha * cl(pr.cizim > 0 ? Math.max(pr.cizim, 0) : 1); c.fill(); c.globalAlpha = taban * al; }
        if (e.kenar || !kap || e.sadece_kenar) { c.strokeStyle = renk(e.kenar || e.renk); c.lineWidth = pr.kalinlik || (kap ? 5 : 8); c.lineCap = 'round'; c.lineJoin = 'round'; if (!kap && pr.cizim < 1) c.setLineDash([L * cl(pr.cizim), L + 50]); c.stroke(); c.setLineDash([]); }
      }
    } else if (e.tur === 'grup') {
      (e.cocuklar || []).slice(0, 30).forEach(function (ch, k) { ozelEleman(c, ch, lt, t, id * 31 + k + 1); });
    } else if (e.tur === 'cizgi' || e.tur === 'ok') {
      c.translate(-pr.x, -pr.y); const x1 = pr.x1 || 0, y1 = pr.y1 || 0, x2 = lerp(x1, pr.x2 || 0, cl(pr.cizim)), y2 = lerp(y1, pr.y2 || 0, cl(pr.cizim));
      c.strokeStyle = rk; c.lineWidth = pr.kalinlik || 8; c.lineCap = 'round'; c.lineJoin = 'round'; if (e.kesikli) c.setLineDash([22, 18]); c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke(); c.setLineDash([]);
      if (e.tur === 'ok' && pr.cizim > 0.95) { const a = Math.atan2(y2 - y1, x2 - x1); c.fillStyle = rk; c.beginPath(); c.moveTo(x2, y2); c.lineTo(x2 - Math.cos(a - 0.5) * 34, y2 - Math.sin(a - 0.5) * 34); c.lineTo(x2 - Math.cos(a + 0.5) * 34, y2 - Math.sin(a + 0.5) * 34); c.closePath(); c.fill(); }
    } else if (e.tur === 'yazi') {
      yazi(c, String(e.metin || '').slice(0, 40), 0, 0, pr.boyut, rk, e.hiza || 'center', e.kontur !== false);
    } else if (e.tur === 'ikon' && IKONLAR[e.ad]) {
      IKONLAR[e.ad](c, t, { renk: e.renk, doluluk: pr.doluluk });
    } else if (e.tur === 'parcacik') {
      const n = Math.min(40, e.sayi || 14), gw = pr.w || 100, yon = e.yon || 'yukari'; for (let k = 0; k < n; k++) { const q = (t * (e.hiz || 0.5) + k / n) % 1, bx = (Math.sin(k * 7.3) * 0.5) * gw; let px = bx, py = 0; const dist = pr.h || 160;
        if (yon === 'yukari') py = -q * dist; else if (yon === 'asagi') py = q * dist; else if (yon === 'sag') { px = q * dist; py = Math.sin(k * 3.1) * gw * 0.4; } else if (yon === 'sol') { px = -q * dist; py = Math.sin(k * 3.1) * gw * 0.4; } else { px = Math.cos(k * 2.4 + t) * q * dist; py = Math.sin(k * 2.4 + t) * q * dist; }
        c.globalAlpha = taban * al * Math.sin(q * Math.PI); c.fillStyle = rk; c.beginPath(); c.arc(px, py, (e.boyut || 8) * (0.6 + (k % 3) * 0.25), 0, 6.3); c.fill(); }
    }
    c.restore();
  }
  /* ---------- RESİM: yapay zekâ görseli + sinematik kamera (iki plan: geniş → yakın kesme), toz/ışık parçacıkları, görsele yapışık animasyonlu katman ---------- */
  S.resim = function (c) {
    const { x, W, H, lt, d, t, p, i } = c, im = (A.gorseller || [])[i];
    if (!im) { c.arka(p.tema || 'mavi'); return; }
    const od = p.odak || [0.5, 0.45];
    let od2 = p.odak2 || [cl(od[0] + (od[0] < 0.5 ? 0.16 : -0.16), 0.2, 0.8), cl(od[1] - 0.05, 0.25, 0.7)];
    if (p.katman && p.katman.length) {   // yakın çekim, animasyon katmanının ağırlık merkezine de bakar (etiketler kadraja girsin)
      let sx = 0, sy = 0, n = 0; p.katman.forEach(function (e) { if (e.tur === 'grup' || e.tur === 'parcacik') return; const ex = e.x != null ? e.x : ((e.x1 || 0) + (e.x2 || 0)) / 2, ey = e.y != null ? e.y : ((e.y1 || 0) + (e.y2 || 0)) / 2; if (ex || ey) { sx += ex; sy += ey; n++; } });
      if (n) od2 = [cl(0.65 * (sx / n / im.width) + 0.35 * od2[0], 0.25, 0.75), cl(0.65 * (sy / n / im.height) + 0.35 * od2[1], 0.3, 0.65)];
    }
    const kesme = d > 3.2 ? Math.min(d * 0.5, d - 1.4) : 1e9;   // sahnenin ortasında ikinci plana (yakın çekim) kesilir
    const ikinci = lt >= kesme, mod = p.hareket || 'yakin';
    const q = ikinci ? sm((lt - kesme) / Math.max(0.5, d - kesme)) : sm(lt / Math.min(d, kesme));
    let z, fx, fy, kx = 0, ky = 0;
    if (!ikinci) {
      z = mod === 'uzak' ? lerp(1.32, 1.08, q) : lerp(1.06, mod === 'yakin' ? 1.34 : 1.2, q);
      fx = od[0]; fy = od[1];
      kx = mod === 'sol' ? lerp(0.10, -0.10, q) : mod === 'sag' ? lerp(-0.10, 0.10, q) : 0; ky = mod === 'yukari' ? lerp(0.08, -0.08, q) : mod === 'asagi' ? lerp(-0.08, 0.08, q) : 0;
    } else { z = lerp(1.42, 1.62, q); fx = od2[0]; fy = od2[1]; kx = lerp(0.03, -0.03, q); }
    // kesme anında kısa sarsıntı + beyaz parlama
    const vur = ikinci ? cl(1 - (lt - kesme) / 0.22) : 0; z += vur * 0.06;
    const el = [Math.sin(t * 2.3) * 4 + Math.sin(t * 5.1) * 2, Math.cos(t * 1.9) * 4 + Math.cos(t * 4.3) * 2];   // hafif el kamerası
    const sc = Math.max(W / im.width, H / im.height) * z, w = im.width * sc, h = im.height * sc;
    let ox = W / 2 - fx * w + kx * W + el[0], oy = H * 0.46 - fy * h + ky * H + el[1];
    ox = Math.min(0, Math.max(W - w, ox)); oy = Math.min(0, Math.max(H - h, oy));
    x.fillStyle = '#000'; x.fillRect(0, 0, W, H); x.drawImage(im, ox, oy, w, h);
    // görsele yapışık animasyonlu katman (oklar, halkalar, etiketler, sayılar…; görsel pikseli 1024x1536 koordinatında)
    if (p.katman && p.katman.length) { x.save(); x.translate(ox, oy); x.scale(sc, sc); p.katman.forEach(function (e, k) { ozelEleman(x, e, lt, t, k + 7); }); x.restore(); }
    // sinematik finiş: alt yazı için alt karartma, köşe karartma, ışık süpürmesi, uçuşan toz/ışık parçacıkları
    let g = x.createLinearGradient(0, H * 0.58, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.72)'); x.fillStyle = g; x.fillRect(0, H * 0.58, W, H * 0.42);
    g = x.createRadialGradient(W / 2, H * 0.45, 380, W / 2, H * 0.45, 1250); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.38)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
    const sw = ((t * 0.22) % 1.6 - 0.3) * W * 1.4; g = x.createLinearGradient(sw - 260, 0, sw + 260, 0); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(0.5, 'rgba(255,255,255,0.08)'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
    for (let k = 0; k < 26; k++) { const px = (k * 211 + t * (14 + (k % 5) * 6)) % (W + 60) - 30, py = ((k * 397 - t * (22 + (k % 7) * 8)) % (H + 60) + H + 60) % (H + 60) - 30, r = 2 + (k % 4) * 1.6; x.fillStyle = 'rgba(255,240,210,' + (0.10 + 0.16 * Math.abs(Math.sin(t * 1.4 + k))) + ')'; x.beginPath(); x.arc(px, py, r, 0, 6.3); x.fill(); }
    if (vur > 0) { x.fillStyle = 'rgba(255,255,255,' + (0.30 * vur) + ')'; x.fillRect(0, 0, W, H); }
    if (lt < 0.4) { x.fillStyle = 'rgba(0,0,0,' + (0.35 * (1 - cl(lt / 0.4))) + ')'; x.fillRect(0, 0, W, H); }
  };

  S.ozel = function (c) {
    const { x, t, lt, d, p } = c; c.arka(p.tema || 'mavi'); const els = (p.elemanlar || []).slice(0, 60), cam = p.kamera || [[540, 760, 1.0], [540, 760, 1.08]];
    c.dunya(cam[0], cam[1] || cam[0], function () { els.forEach(function (e, i) { ozelEleman(x, e, lt, t, i); }); });
    (p.etiket_noktalari || []).slice(0, 2).forEach(function (q, k) { const a = c.nokta(q[0], q[1]); c.etiket(k, a[0], a[1], q[2] || 1.2 + k * 0.8, q[3] || 1); });
  };

  A.tipler = Object.keys(S);
})();
