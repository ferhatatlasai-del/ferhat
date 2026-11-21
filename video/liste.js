/* Doktor Filament — "geri sayım listesi" biçimli dikey video çizicisi (2D tuval, fotoğraf tabanlı).
 * Her madde: konuya özel gerçekçi görsel (yapay zekâ) + yavaş kamera hareketi + işaret iğnesi ve halka + sayaçlı bilgi kartı,
 * üstte "N … 1" sıra göstergesi, kartın üstünde kelime kelime aydınlanan alt yazı, maddeler arası yakınlaşmalı geçiş.
 * Tamamen deterministik: kare(t) yalnızca t'ye bağlıdır.
 */
'use strict';
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const k01 = (t, a, b) => clamp((t - a) / (b - a));
const sm = x => { x = clamp(x); return x * x * (3 - 2 * x); };
const outCubic = x => 1 - Math.pow(1 - clamp(x), 3);
const outBack = x => { x = clamp(x); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const lerp = (a, b, t) => a + (b - a) * t;

const ALTIN = '#f4c542', KART = 'rgba(14,16,22,.84)', CIZGI = 'rgba(255,255,255,.10)';
const GECIS = 0.7;
let P, W, H, OL, c2, ctx, gorseller = [], GRAIN;

function yuvarlak(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function font(boyut, agir) { return `${agir || 800} ${boyut}px ${agir === 600 ? 'IS' : 'IB'}, Inter, "DejaVu Sans", sans-serif`; }
function yazi(s, x, y, boyut, o) {
  o = o || {}; ctx.save(); ctx.font = font(boyut, o.agir); ctx.textAlign = o.hiza || 'left'; ctx.textBaseline = o.taban || 'alphabetic';
  if (o.aralik) ctx.letterSpacing = o.aralik + 'px';
  ctx.globalAlpha = o.alfa == null ? 1 : o.alfa;
  if (o.golge) { ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = boyut * .25; ctx.shadowOffsetY = boyut * .05; }
  ctx.fillStyle = o.renk || '#fff'; ctx.fillText(s, x, y); ctx.restore();
}
function olcu(s, boyut, agir, aralik) { ctx.save(); ctx.font = font(boyut, agir); if (aralik) ctx.letterSpacing = aralik + 'px'; const w = ctx.measureText(s).width; ctx.restore(); return w; }
function sayiYaz(v, ondalik) {   // Türkçe biçim: 3.550 / 2,5
  const s = Number(v).toFixed(ondalik || 0).split('.');
  return s[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (s[1] ? ',' + s[1] : '');
}

/* ---------- görsel katmanı: kapla + yavaş kamera ---------- */
function kamera(n, lp) {   // dönen: {s, cx, cy} — görselin hangi noktası ekranın ortasına ve hangi ölçekte
  const od = n.odak;
  const s = lerp(1.06, 1.20, sm(lp));
  const cx = lerp(.5, lerp(.5, od[0], .55), sm(lp)), cy = lerp(.5, lerp(.5, od[1], .45), sm(lp));
  return { s, cx, cy, don: (n.yon || 1) * lerp(-.004, .004, lp) };
}
function gorselCiz(n, lp, ek, alfa, bulanik) {
  const img = n.img; if (!img) return null;
  const k = kamera(n, lp), sc = Math.max(W / img.width, H / img.height) * k.s * (ek || 1);
  const ox = W / 2 - k.cx * img.width * sc, oy = H / 2 - k.cy * img.height * sc;
  ctx.save(); ctx.globalAlpha = alfa == null ? 1 : alfa;
  if (bulanik > .3) ctx.filter = `blur(${bulanik.toFixed(1)}px)`;
  ctx.translate(W / 2, H / 2); ctx.rotate(k.don); ctx.translate(-W / 2, -H / 2);
  ctx.drawImage(img, ox, oy, img.width * sc, img.height * sc);
  ctx.restore();
  // odak noktasının ekrandaki yeri (iğne için)
  const px = ox + n.odak[0] * img.width * sc, py = oy + n.odak[1] * img.height * sc;
  return [W / 2 + (px - W / 2) * Math.cos(k.don) - (py - H / 2) * Math.sin(k.don), H / 2 + (px - W / 2) * Math.sin(k.don) + (py - H / 2) * Math.cos(k.don)];
}

/* ---------- iğne + halka ---------- */
function igne(x, y, ad, lt, cik) {
  const a = outCubic(k01(lt, .25, .7)) * cik; if (a <= .01) return;
  const boy = 250 * outCubic(k01(lt, .3, .8)), r = 96 * outBack(k01(lt, .25, .65));
  y = Math.min(Math.max(y, 520), 1180);
  ctx.save(); ctx.globalAlpha = a;
  // halka: zemine yatık elips, nabız gibi atan ikinci halka
  ctx.strokeStyle = 'rgba(244,197,66,.95)'; ctx.lineWidth = 7; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 14;
  ctx.beginPath(); ctx.ellipse(x, y, r, r * .32, 0, 0, Math.PI * 2); ctx.stroke();
  const nb = (lt * .9) % 1; ctx.globalAlpha = a * (1 - nb) * .7; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.ellipse(x, y, r * (1 + nb * .6), r * .32 * (1 + nb * .6), 0, 0, Math.PI * 2); ctx.stroke();
  ctx.globalAlpha = a;
  // çizgi + uç noktası
  const g = ctx.createLinearGradient(x, y - boy, x, y); g.addColorStop(0, '#fff3c4'); g.addColorStop(1, ALTIN);
  ctx.strokeStyle = g; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - boy); ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y - boy, 13, 0, 7); ctx.fill();
  // etiket hapı
  if (boy > 200) {
    const pa = outBack(k01(lt, .7, 1.0)), bw = olcu(ad, 40) + 44, bh = 64, bx = clamp(x - bw / 2, 40, W - 40 - bw), by = y - boy - 40 - bh;
    ctx.translate(bx + bw / 2, by + bh / 2); ctx.scale(pa, pa); ctx.translate(-(bx + bw / 2), -(by + bh / 2));
    ctx.fillStyle = ALTIN; yuvarlak(bx, by, bw, bh, 18); ctx.fill();
    ctx.shadowColor = 'transparent'; yazi(ad, bx + bw / 2, by + bh / 2 + 14, 40, { hiza: 'center', renk: '#1c1606' });
  }
  ctx.restore();
}

/* ---------- üst bilgi: başlık + sıra göstergesi ---------- */
function ustBilgi(aktifSira, alfa) {
  if (alfa <= .01) return;
  const N = P.toplam;
  yazi(P.baslik_ust, W / 2, 132, 32, { hiza: 'center', aralik: 5, renk: '#fff', golge: true, alfa });
  const cw = 58, ch = 44, ara = 10, top = N * cw + (N - 1) * ara, x0 = W / 2 - top / 2, y0 = 168;
  for (let i = 0; i < N; i++) {
    const sira = N - i, x = x0 + i * (cw + ara), gecti = aktifSira != null && sira > aktifSira, aktif = sira === aktifSira;
    ctx.save(); ctx.globalAlpha = alfa;
    yuvarlak(x, y0, cw, ch, 10);
    if (aktif) { ctx.fillStyle = ALTIN; ctx.fill(); }
    else { ctx.fillStyle = gecti ? 'rgba(255,255,255,.22)' : 'rgba(10,12,18,.45)'; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 2; ctx.stroke(); }
    ctx.restore();
    yazi(String(sira), x + cw / 2, y0 + ch / 2 + 11, 28, { hiza: 'center', renk: aktif ? '#1c1606' : (gecti ? 'rgba(255,255,255,.75)' : 'rgba(255,255,255,.6)'), alfa });
  }
}

/* ---------- bilgi kartı ---------- */
function kart(m, lt, d, alfa) {
  const gir = outCubic(k01(lt, .15, .6)), a = gir * alfa; if (a <= .01) return;
  const x = 46, w = W - 92, y = 1478 + (1 - gir) * 60, h = 262;
  ctx.save(); ctx.globalAlpha = a; ctx.shadowColor = 'rgba(0,0,0,.45)'; ctx.shadowBlur = 40; ctx.shadowOffsetY = 12;
  ctx.fillStyle = KART; yuvarlak(x, y, w, h, 30); ctx.fill(); ctx.shadowColor = 'transparent';
  ctx.strokeStyle = CIZGI; ctx.lineWidth = 2; ctx.stroke(); ctx.restore();
  // sıra numarası
  yazi(String(m.sira), x + 40, y + 148, 150, { renk: ALTIN, alfa: a });
  const nx = x + 40 + olcu(String(m.sira), 150) + 34;
  yazi(m.ad, nx, y + 86, 58, { renk: '#fff', alfa: a });
  if (m.alt) {   // konum yerine kısa açıklama, iğne simgesiyle
    ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = ALTIN; ctx.beginPath(); ctx.arc(nx + 9, y + 121, 8, 0, 7); ctx.fill(); ctx.restore();
    yazi(m.alt, nx + 28, y + 132, 30, { renk: 'rgba(255,255,255,.72)', agir: 600, alfa: a });
  }
  if (P.olcu && m.deger != null) {
    const q = outCubic(k01(lt, .55, 1.9)), v = m.deger * q, en = P.olcu.en_buyuk || Math.max(m.deger, 1);
    yazi(P.olcu.ad, x + 40, y + 206, 24, { renk: 'rgba(255,255,255,.55)', aralik: 4, agir: 600, alfa: a });
    const metin = (q < 1 ? sayiYaz(v, P.olcu.ondalik) : (m.deger_yazi || sayiYaz(m.deger, P.olcu.ondalik)));
    const birim = P.olcu.birim || '';
    const bwid = olcu(birim, 36);
    yazi(birim, x + w - 40, y + 210, 36, { hiza: 'right', renk: 'rgba(255,255,255,.8)', alfa: a });
    yazi(metin, x + w - 40 - bwid - 10, y + 212, 70, { hiza: 'right', renk: '#fff', alfa: a });
    const by = y + 232, bx = x + 40, bw = w - 80;
    ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = 'rgba(255,255,255,.12)'; yuvarlak(bx, by, bw, 8, 4); ctx.fill();
    ctx.fillStyle = ALTIN; yuvarlak(bx, by, Math.max(8, bw * clamp(v / en)), 8, 4); ctx.fill(); ctx.restore();
    yazi('0', bx, by + 26, 18, { renk: 'rgba(255,255,255,.45)', agir: 600, alfa: a });
    if (P.olcu.en_buyuk_ad) yazi(`${P.olcu.en_buyuk_ad} ${sayiYaz(en, P.olcu.ondalik)}${birim ? ' ' + birim : ''}`, bx + bw, by + 26, 18, { hiza: 'right', renk: 'rgba(255,255,255,.45)', agir: 600, alfa: a });
  }
}

/* ---------- alt yazı (kartın üstünde, kelime kelime aydınlanır) ---------- */
function altyazi(t, yTaban) {
  const al = P.altyazi.find(x => t >= x.t0 - .08 && t < x.t1 + .15); if (!al) return;
  const boyut = 46, gen = 940, satirlar = [[]]; let cur = 0;
  al.kelimeler.forEach(w => { const wd = olcu(w.k, boyut) + 14; if (cur + wd > gen && satirlar[satirlar.length - 1].length) { satirlar.push([]); cur = 0; } satirlar[satirlar.length - 1].push(w); cur += wd; });
  const giris = outCubic(k01(t, al.t0 - .08, al.t0 + .1)), y0 = yTaban - (satirlar.length - 1) * 58;
  satirlar.forEach((sa, li) => {
    const top = sa.reduce((a, w) => a + olcu(w.k, boyut) + 14, 0) - 14; let x = W / 2 - top / 2;
    sa.forEach(w => {
      const parlak = clamp((t - w.t0) / .12);
      yazi(w.k, x, y0 + li * 58, boyut, { renk: `rgba(255,255,255,${(.42 + .58 * parlak).toFixed(2)})`, golge: true, alfa: giris });
      x += olcu(w.k, boyut) + 14;
    });
  });
}

/* ---------- ana motor ---------- */
window.hazirla = async function (plan, olcek) {
  P = plan; OL = olcek || 1; W = plan.genislik; H = plan.yukseklik;
  c2 = document.getElementById('c2'); c2.width = W * OL; c2.height = H * OL; ctx = c2.getContext('2d');
  await document.fonts.load('800 80px IB'); await document.fonts.load('600 40px IS');
  gorseller = await Promise.all(plan.sahneler.map(async (s, i) => {
    const n = { s, odak: (s.params && s.params.odak) || [.5, .45], yon: i % 2 ? -1 : 1, img: null };
    if (s.params && s.params.gorsel) { const im = new Image(); im.src = s.params.gorsel; try { await im.decode(); n.img = im; } catch (e) { console.error('görsel yüklenemedi: ' + s.params.gorsel); } }
    return n;
  }));
  GRAIN = document.createElement('canvas'); GRAIN.width = GRAIN.height = 256;
  const gx = GRAIN.getContext('2d'), gi = gx.createImageData(256, 256); let r = 99;
  for (let i = 0; i < gi.data.length; i += 4) { r = (r * 16807) % 2147483647; const v = 118 + (r % 40); gi.data[i] = gi.data[i + 1] = gi.data[i + 2] = v; gi.data[i + 3] = 255; }
  gx.putImageData(gi, 0, 0);
  return { sahne: gorseller.length };
};

function etkin(t) { let i = gorseller.findIndex(n => t < n.s.t1); return i < 0 ? gorseller.length - 1 : i; }

window.kare = function (t, kalite) {
  ctx.setTransform(OL, 0, 0, OL, 0, 0); ctx.fillStyle = '#05070c'; ctx.fillRect(0, 0, W, H);
  const i = etkin(t), n = gorseller[i], s = n.s, d = s.t1 - s.t0, lt = t - s.t0, lp = clamp(lt / d);
  // geçiş: önceki sahnenin sonundan bu sahnenin başına yakınlaşarak akış
  const onceki = gorseller[i - 1], sonraki = gorseller[i + 1];
  let nokta = null;
  if (onceki && lt < GECIS / 2) {
    const u = .5 + lt / GECIS;   // .5..1
    gorselCiz(onceki, 1, 1 + .5 * sm(u) , 1, 18 * Math.sin(Math.PI * u));
    nokta = gorselCiz(n, lp, 1.35 - .35 * sm(u), sm((u - .5) * 2), 14 * (1 - sm((u - .5) * 2)));
  } else if (sonraki && lt > d - GECIS / 2) {
    const u = (lt - (d - GECIS / 2)) / GECIS;   // 0..0.5
    nokta = gorselCiz(n, lp, 1 + .5 * sm(u), 1, 18 * Math.sin(Math.PI * u));
  } else nokta = gorselCiz(n, lp, 1, 1, 0);
  // okunabilirlik: üst ve alt koyulaştırma + kenar karartma
  let g = ctx.createLinearGradient(0, 0, 0, 420); g.addColorStop(0, 'rgba(0,0,0,.62)'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, 420);
  g = ctx.createLinearGradient(0, H * .58, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.78)'); ctx.fillStyle = g; ctx.fillRect(0, H * .58, W, H * .42);
  g = ctx.createRadialGradient(W / 2, H / 2, H * .3, W / 2, H / 2, H * .78); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.45)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const cik = 1 - k01(lt, d - .45, d - .2), pr = s.params || {};
  if (s.tip === 'liste_madde') {
    ustBilgi(pr.sira, 1);
    if (nokta) igne(nokta[0], nokta[1], pr.ad, lt, cik);
    kart(pr, lt, d, cik);
    altyazi(t, 1420);
  } else if (s.tip === 'liste_giris') {
    ustBilgi(null, outCubic(k01(lt, .2, .8)));
    const a = outBack(k01(lt, .1, .6)) * cik, satir = (pr.baslik || P.baslik_ust).split('\n');
    satir.forEach((l, k) => yazi(l, W / 2, 900 + k * 120 - (satir.length - 1) * 60, 104, { hiza: 'center', renk: k === satir.length - 1 ? ALTIN : '#fff', golge: true, alfa: clamp(a) }));
    altyazi(t, 1560);
  } else {   // kapanış
    ustBilgi(0, 1);
    const a = outBack(k01(lt, .1, .5));
    yazi(pr.ana || 'TAKİP ET', W / 2, 880, 130, { hiza: 'center', golge: true, alfa: clamp(a) });
    const h = pr.alt || '@gurtechs3d', bw = olcu(h, 54) + 60;
    ctx.save(); ctx.globalAlpha = clamp(a); ctx.fillStyle = ALTIN; yuvarlak(W / 2 - bw / 2, 940, bw, 86, 43); ctx.fill(); ctx.restore();
    yazi(h, W / 2, 1000, 54, { hiza: 'center', renk: '#1c1606', alfa: clamp(a) });
    altyazi(t, 1560);
  }
  // film greni + açılış/kapanış kararması
  const kn = Math.round(t * 30) + 1;
  ctx.save(); ctx.globalCompositeOperation = 'overlay'; ctx.globalAlpha = .08; ctx.translate(-(kn * 37 % 256), -(kn * 91 % 256)); ctx.fillStyle = ctx.createPattern(GRAIN, 'repeat'); ctx.fillRect(0, 0, W + 256, H + 256); ctx.restore();
  const kar = Math.max(1 - k01(t, 0, .3), 1 - k01(P.sure - t, 0, .5));
  if (kar > 0) { ctx.fillStyle = `rgba(5,7,12,${kar.toFixed(3)})`; ctx.fillRect(0, 0, W, H); }
  return c2.toDataURL('image/jpeg', kalite || .9).slice(23);
};
