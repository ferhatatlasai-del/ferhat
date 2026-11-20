/* Doktor Filament — 3D animasyonlu dikey video sahne motoru.
 * Tamamen deterministik: kare(t) yalnızca t'nin fonksiyonudur; aynı plan her zaman aynı kareleri üretir.
 * Kullanım (render.js): await hazirla(plan, olcek); sonra her kare için kare(t) → JPEG data URL.
 */
'use strict';
const T = THREE;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const k01 = (t, a, b) => clamp((t - a) / (b - a));
const sm = x => { x = clamp(x); return x * x * (3 - 2 * x); };
const outCubic = x => 1 - Math.pow(1 - clamp(x), 3);
const outBack = x => { x = clamp(x); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const lerp = (a, b, t) => a + (b - a) * t;
const rng = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const TUR = 'tr-TR';

const RENK = { bg: 0x070b16, turuncu: 0xff7a1a, camgobegi: 0x22d3ee, yesil: 0x34d399, kirmizi: 0xf43f5e, sari: 0xffd43b, beyaz: 0xf4f7ff, plaka: 0x1d2640, taban: 0x0e1424 };
const CSS = { turuncu: '#ff7a1a', cyan: '#22d3ee', yesil: '#34d399', kirmizi: '#f43f5e', sari: '#ffd43b' };

const FANLAR = [];
let P, W, H, OL, renderer, scene3, kam, glc, c2, ctx, GLOW, sahneler = [], isiklar = {};
const OFS = 70;               // sahneler arası dünya uzaklığı
const UZAK = { baski: 1.65, temizlik: 1.6, sicaklik: 1.6, hiz: 1.55, yapistirici: 1.6, ozet: 1.25, ilk_katman: 1.0, sayi: 1.2, karsilastir: 1.2, cta: 1.45 };
const GECIS = 0.55;           // geçiş penceresi (sn)

/* ---------- yardımcılar ---------- */
function mat(renk, o) { return new T.MeshStandardMaterial(Object.assign({ color: renk, roughness: .55, metalness: .15, flatShading: true }, o || {})); }
function kutu(w, h, d, renk, o) { return new T.Mesh(new T.BoxGeometry(w, h, d), mat(renk, o)); }
function silin(r1, r2, h, renk, seg, o) { return new T.Mesh(new T.CylinderGeometry(r1, r2, h, seg || 20), mat(renk, o)); }
function glowTex() { const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d'); const g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.25, 'rgba(255,255,255,.5)'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, 128, 128); return new T.CanvasTexture(c); }
function parilti(renk, boyut, op) { const s = new T.Sprite(new T.SpriteMaterial({ map: GLOW, color: renk, blending: T.AdditiveBlending, transparent: true, depthWrite: false, opacity: op == null ? 1 : op })); s.scale.set(boyut, boyut, 1); return s; }
function gridTex() { const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d'); x.fillStyle = '#0a1020'; x.fillRect(0, 0, 256, 256); x.strokeStyle = '#1d3a5c'; x.lineWidth = 3; x.strokeRect(0, 0, 256, 256); const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; t.anisotropy = 4; return t; }


/* ---------- dokular ve fiziksel malzemeler (ayrıntı) ---------- */
function benekTex(boyut, tohum, taban, acik, adet, tekrar) {   // ince benekli yüzey (PEI tabla, plastik): renk + kabartma için
  const c = document.createElement('canvas'); c.width = c.height = boyut; const x = c.getContext('2d'), R = rng(tohum);
  x.fillStyle = taban; x.fillRect(0, 0, boyut, boyut);
  for (let i = 0; i < adet; i++) { const v = R(); x.fillStyle = v < .5 ? `rgba(${acik},${(.05 + R() * .18).toFixed(2)})` : `rgba(0,0,0,${(.08 + R() * .22).toFixed(2)})`; x.fillRect(R() * boyut, R() * boyut, 1 + (R() < .15 ? 1 : 0), 1); }
  const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(tekrar || 3, tekrar || 3); t.anisotropy = 4; return t;
}
function cizgiTex(w, h, adet, koyu) {   // yatay çizgiler: filament sargısı / katman çizgileri kabartması
  const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.fillStyle = '#808080'; x.fillRect(0, 0, w, h);
  for (let i = 0; i < adet; i++) { const y = i * h / adet; const g = x.createLinearGradient(0, y, 0, y + h / adet); g.addColorStop(0, '#d0d0d0'); g.addColorStop(.5, koyu || '#303030'); g.addColorStop(1, '#d0d0d0'); x.fillStyle = g; x.fillRect(0, y, w, h / adet); }
  const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; return t;
}
function lcdTex() {
  const c = document.createElement('canvas'); c.width = 256; c.height = 128; const x = c.getContext('2d');
  x.fillStyle = '#06222c'; x.fillRect(0, 0, 256, 128); x.fillStyle = '#17c3e8'; x.font = 'bold 20px monospace';
  x.fillText('Nozzle 205/205C', 10, 30); x.fillText('Bed    60/ 60C', 10, 58); x.fillText('Speed 100%  Z 0.20', 10, 86);
  x.fillStyle = '#0b4f63'; x.fillRect(10, 98, 236, 12); x.fillStyle = '#ff9a3d'; x.fillRect(10, 98, 150, 12);
  const t = new T.CanvasTexture(c); return t;
}
function fiz(renk, o) {   // parlak filament / lake: clearcoat'lı fiziksel malzeme
  return new T.MeshPhysicalMaterial(Object.assign({ color: renk, roughness: .38, metalness: 0, clearcoat: .6, clearcoatRoughness: .25 }, o || {}));
}

function yatak(g, w, d) {   // yazıcı tablası: üstü y=0
  const taban = kutu(w + 1.4, .9, d + 1.4, RENK.taban, { metalness: .5, roughness: .45 }); taban.position.y = -1.05; g.add(taban);
  // ısıtıcı yatağın alüminyum taşıyıcısı + vidalı seviyeleme düğmeleri
  const sinir = kutu(w + 1.5, .08, d + 1.5, 0xc2410c, { emissive: 0xc2410c, emissiveIntensity: .45 }); sinir.position.y = -.58; g.add(sinir);
  const plaka = kutu(w, .5, d, 0x4a5368, { metalness: .85, roughness: .32 }); plaka.position.y = -.34; g.add(plaka);
  // manyetik PEI yüzey: ince benekli doku + kabartma, kenarda hafif pah
  const pei = benekTex(512, 3, '#262b35', '210,215,225', 26000, Math.max(2, Math.round(w / 3)));
  const yuz = new T.Mesh(new T.BoxGeometry(w - .2, .1, d - .2), new T.MeshStandardMaterial({ map: pei, bumpMap: pei, bumpScale: .9, color: 0xffffff, roughness: .55, metalness: .25 }));
  yuz.position.y = -.05; g.add(yuz);
  [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(k => {   // köşe düğmeleri (seviyeleme)
    
    const vida = silin(.14, .14, .5, 0x9aa7c4, 10, { metalness: .9, roughness: .3 }); vida.position.set(k[0] * (w / 2 + .35), -.62, k[1] * (d / 2 + .35)); g.add(vida);
    const kn = silin(.34, .34, .3, 0xffb020, 16, { flatShading: false, metalness: .2, roughness: .4 }); kn.position.set(k[0] * (w / 2 + .35), -.9, k[1] * (d / 2 + .35)); g.add(kn);
  });
  const bant = kutu(w + .1, .02, .28, 0xc98a2a, { emissive: 0x6a4210, emissiveIntensity: .25 }); bant.position.set(0, -.06, d / 2 - .05); g.add(bant);   // kapton bant şeridi
  return yuz;
}
function nozul(renk) {   // sıcak uç grubu: kökü (uç) y=0
  const g = new T.Group(), pirinc = mat(0xd9a441, { metalness: .9, roughness: .25 }), celik = mat(0xaab4c8, { metalness: .95, roughness: .22 });
  const uc = new T.Mesh(new T.ConeGeometry(.3, .55, 24), pirinc); uc.rotation.x = Math.PI; uc.position.y = .275; g.add(uc);
  const hex = new T.Mesh(new T.CylinderGeometry(.36, .36, .3, 6), pirinc); hex.position.y = .7; g.add(hex);
  const blok = kutu(1.25, .85, 1.05, 0x9aa3b5, { metalness: .9, roughness: .3 }); blok.position.y = 1.3; g.add(blok);
  const sock = kutu(1.4, .95, 1.2, 0xe0521d, { roughness: .8, metalness: 0 }); sock.position.set(0, 1.32, 0); sock.scale.set(1, 1, 1); g.add(sock);   // silikon çorap
  const kirik = silin(.2, .2, .55, 0xc9d1e0, 14, { metalness: .95, roughness: .2 }); kirik.position.y = 1.97; g.add(kirik);   // ısı kırıcı
  for (let i = 0; i < 8; i++) { const f = new T.Mesh(new T.CylinderGeometry(.72, .72, .07, 28), celik); f.position.y = 2.35 + i * .16; g.add(f); }   // soğutma kanatları
  const govde = kutu(1.4, 1.3, .9, 0x1a2540, { roughness: .6 }); govde.position.set(0, 1.55, -.95); g.add(govde);   // fan kanalı (shroud)
  const fan = new T.Group(); const hal = silin(.52, .52, .12, 0x0b1020, 28, { flatShading: false }); hal.rotation.x = Math.PI / 2; fan.add(hal);
  for (let i = 0; i < 7; i++) { const k = kutu(.07, .42, .05, 0x8da0c4); k.position.y = .22; const kk = new T.Group(); kk.add(k); kk.rotation.z = i * Math.PI * 2 / 7; fan.add(kk); }
  fan.position.set(0, 1.55, -1.42); fan.rotation.y = Math.PI; g.add(fan); g.userData.fan = fan; FANLAR.push(fan);
  const ptfe = silin(.1, .1, 1.7, 0xeaf0ff, 12, { roughness: .5, flatShading: false }); ptfe.position.y = 4.1; g.add(ptfe);   // PTFE boru
  [[.25, 0xe83a3a], [.4, 0x1c1c24], [.55, 0x2a8cff]].forEach((k, i) => { const kb = silin(.05, .05, 2.0, k[1], 8, { flatShading: false, roughness: .7 }); kb.position.set(-.55 + i * .07, 3.5, -.45); g.add(kb); });   // kablolar
  const isik = parilti(renk || RENK.turuncu, 1.6, .9); isik.position.y = .1; g.add(isik); g.userData.isik = isik;
  return g;
}
function toz(g, n, yay, tohum) {
  const r = rng(tohum || 7), poz = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { poz[i * 3] = (r() - .5) * yay; poz[i * 3 + 1] = r() * 14; poz[i * 3 + 2] = (r() - .5) * yay; }
  const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(poz, 3));
  const p = new T.Points(geo, new T.PointsMaterial({ color: 0x7fb8ff, size: .09, transparent: true, opacity: .55, depthWrite: false })); g.add(p);
  p.userData.ilk = poz.slice(); return p;
}
function tozGuncelle(p, t) {
  const a = p.geometry.attributes.position, i0 = p.userData.ilk;
  for (let i = 0; i < a.count; i++) { a.array[i * 3 + 1] = (i0[i * 3 + 1] + t * (.25 + (i % 5) * .07)) % 14; a.array[i * 3] = i0[i * 3] + Math.sin(t * .4 + i) * .3; }
  a.needsUpdate = true;
}
function onaylaPil(g, ok) { return ok; }


function ortamHaritasi() {   // stüdyo ışığı gibi: gradyan + yumuşak ışık kutuları → parlak yüzeylerde gerçekçi yansıma
  const c = document.createElement('canvas'); c.width = 512; c.height = 256; const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, '#41588f'); g.addColorStop(.5, '#1b2744'); g.addColorStop(1, '#0a0f1e'); x.fillStyle = g; x.fillRect(0, 0, 512, 256);
  [[90, 60, 120, 40, '#ffffff'], [330, 50, 90, 30, '#ffd9b0'], [450, 100, 60, 60, '#7fe8ff'], [200, 120, 70, 24, '#ff9a4d']].forEach(a => { x.fillStyle = a[4]; x.filter = 'blur(10px)'; x.fillRect(a[0], a[1], a[2], a[3]); });
  const t = new T.CanvasTexture(c); t.mapping = T.EquirectangularReflectionMapping;
  const pm = new T.PMREMGenerator(renderer); const e = pm.fromEquirectangular(t).texture; pm.dispose(); return e;
}
function havuzTex(renk) { const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d'); const g = x.createRadialGradient(128, 128, 0, 128, 128, 128); g.addColorStop(0, renk); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, 0, 256, 256); return new T.CanvasTexture(c); }
function zeminIsigi(g, r, renk) {   // nesnenin altında zemine yayılan renkli ışık havuzu
  const m = new T.Mesh(new T.CircleGeometry(r, 48), new T.MeshBasicMaterial({ map: havuzTex(renk || 'rgba(255,122,26,.55)'), transparent: true, blending: T.AdditiveBlending, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.y = -1.49; g.add(m); return m;
}
function bokeh(g, tohum) {   // arka planda yumuşak, yavaş kayan ışık küreleri (derinlik hissi)
  const R = rng(tohum || 5), liste = [];
  for (let i = 0; i < 16; i++) { const renk = [0x22d3ee, 0xff7a1a, 0x7c5cff, 0xff4d8d][i % 4], s = parilti(renk, 3 + R() * 7, .1 + R() * .12); s.userData = { x: (R() - .5) * 46, y: 1 + R() * 14, z: -10 - R() * 26, v: .1 + R() * .25, f: R() * 6 }; g.add(s); liste.push(s); }
  return liste;
}
function bokehGuncelle(liste, t) { liste.forEach(s => { const u = s.userData; s.position.set(u.x + Math.sin(t * u.v + u.f) * 1.5, u.y + Math.cos(t * u.v * .8 + u.f) * 1.2, u.z); }); }
function yaziciArka(g, x, z) {   // arka planda ayrıntılı yazıcı: T-yuvalı profiller, motor, kayış, makara, LCD, kablo zinciri
  const a = new T.Group(), alu = { metalness: .92, roughness: .28 }, siyah = { metalness: .4, roughness: .6 };
  [-5.2, 5.2].forEach(px => {
    const d = kutu(.7, 13, .7, 0xa4b0cc, alu); d.position.set(px, 5, 0); a.add(d);
    [[0, .36], [0, -.36]].forEach(k => { const y = kutu(.2, 13, .06, 0x161c2e, siyah); y.position.set(px, 5, k[1]); a.add(y); });   // T-yuva şeritleri
    [[.36, 0], [-.36, 0]].forEach(k => { const y = kutu(.06, 13, .2, 0x161c2e, siyah); y.position.set(px + k[0], 5, 0); a.add(y); });
    const vida = silin(.09, .09, 12.6, 0xd2d8e6, 10, { metalness: .95, roughness: .25 }); vida.position.set(px + (px < 0 ? 1.0 : -1.0), 5, .1); a.add(vida);   // Z vidası
    const mot = kutu(.95, .95, .95, 0x1a1f2e, { metalness: .6, roughness: .4 }); mot.position.set(px + (px < 0 ? 1.0 : -1.0), -.6, .1); a.add(mot);   // Z motoru
  });
  const kiris = kutu(11.4, .8, .9, 0xa4b0cc, alu); kiris.position.y = 11.6; a.add(kiris);
  [[.46, 0], [-.46, 0]].forEach(k => { const y = kutu(11.2, .16, .06, 0x161c2e, siyah); y.position.set(0, 11.6, k[0]); a.add(y); });
  const ray = kutu(10.2, .3, .3, 0x2a3350, { metalness: .85, roughness: .3 }); ray.position.set(0, 7.6, .1); a.add(ray);
  const kayis = kutu(10.0, .09, .5, 0x151820, { roughness: .9, metalness: 0 }); kayis.position.set(0, 7.95, .5); a.add(kayis);   // X kayışı
  const tas = kutu(1.7, 1.1, 1.0, 0xff7a1a, { metalness: .3, roughness: .45 }); tas.position.set(-1.2, 7.6, .6); a.add(tas);
  const xmot = kutu(1.0, 1.0, 1.0, 0x1a1f2e, { metalness: .6, roughness: .4 }); xmot.position.set(5.6, 8.0, .1); a.add(xmot);
  const mk = new T.Group();   // filament makarası: yan diskler + sarım halkaları (kabartmalı)
  const sarimDoku = cizgiTex(64, 128, 26); sarimDoku.repeat.set(1, 2);
  const sarim = new T.Mesh(new T.CylinderGeometry(2.1, 2.1, 1.0, 56, 1), fiz(0xff7a1a, { bumpMap: sarimDoku, bumpScale: 1.4, roughness: .5 })); sarim.rotation.x = Math.PI / 2; mk.add(sarim);
  [-.55, .55].forEach(zz => { const disk = new T.Mesh(new T.CylinderGeometry(2.7, 2.7, .12, 56), new T.MeshStandardMaterial({ color: 0x20283f, roughness: .35, metalness: .1, transparent: true, opacity: .86 })); disk.rotation.x = Math.PI / 2; disk.position.z = zz; mk.add(disk); });
  const kb = silin(.7, .7, 1.2, 0x0e1424, 24); kb.rotation.x = Math.PI / 2; mk.add(kb);
  for (let i = 0; i < 5; i++) { const k = kutu(.12, .5, .1, 0x303a5a); k.position.set(Math.cos(i * 1.2566) * 1.5, Math.sin(i * 1.2566) * 1.5, .62); k.rotation.z = i * 1.2566; mk.add(k); }   // makara kolları
  mk.position.set(7.8, 9.4, .4); a.add(mk); a.userData.makara = mk;
  const kutuE = kutu(3.2, 2.2, 1.4, 0x141b2e, { metalness: .5, roughness: .45 }); kutuE.position.set(-7.6, 1.3, .6); a.add(kutuE);
  const lcd = new T.Mesh(new T.PlaneGeometry(2.4, 1.2), new T.MeshBasicMaterial({ map: lcdTex() })); lcd.position.set(-7.6, 1.55, 1.31); a.add(lcd);   // LCD ekran: sıcaklıklar ve ilerleme çubuğu
  const dugme = silin(.24, .24, .18, 0xff7a1a, 16, { flatShading: false }); dugme.rotation.x = Math.PI / 2; dugme.position.set(-6.7, .55, 1.35); a.add(dugme);
  const zincir = new T.Group(); for (let i = 0; i < 12; i++) { const k = kutu(.5, .34, .5, 0x1b2236, { metalness: .3, roughness: .7 }); k.position.set(-6.2 + i * .1, 3.4 + i * .5, .85 + Math.sin(i * .5) * .1); zincir.add(k); } a.add(zincir);   // kablo zinciri
  a.position.set(x || 0, -.6, z == null ? -9 : z); g.add(a); return a;
}

/* ---------- 2D metin ---------- */
function yazi(s, x, y, boyut, o) {
  o = o || {};
  ctx.save(); ctx.font = `${o.agirlik || 800} ${boyut}px IB, Inter, "DejaVu Sans", sans-serif`; ctx.textAlign = o.hiza || 'center'; ctx.textBaseline = 'middle';
  ctx.globalAlpha = o.alfa == null ? 1 : o.alfa;
  if (o.olcek && o.olcek !== 1) { ctx.translate(x, y); ctx.scale(o.olcek, o.olcek); x = 0; y = 0; }
  if (o.golge !== false) { ctx.shadowColor = 'rgba(0,0,0,.65)'; ctx.shadowBlur = boyut * .18; ctx.shadowOffsetY = boyut * .05; }
  if (o.kontur) { ctx.lineJoin = 'round'; ctx.lineWidth = o.kontur; ctx.strokeStyle = o.konturRenk || 'rgba(5,8,18,.95)'; ctx.strokeText(s, x, y); }
  ctx.shadowColor = 'transparent'; ctx.fillStyle = o.renk || '#fff'; ctx.fillText(s, x, y); ctx.restore();
}
function leke(x, y, r, a) { ctx.save(); const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, `rgba(4,7,16,${a})`); g.addColorStop(1, 'rgba(4,7,16,0)'); ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2); ctx.restore(); }
function olcu(s, boyut) { ctx.save(); ctx.font = `800 ${boyut}px IB, Inter, "DejaVu Sans", sans-serif`; const w = ctx.measureText(s).width; ctx.restore(); return w; }
function sar(s, boyut, genis) {
  const k = s.split(/\s+/), satir = []; let su = '';
  for (const w of k) { const t = su ? su + ' ' + w : w; if (olcu(t, boyut) > genis && su) { satir.push(su); su = w; } else su = t; }
  if (su) satir.push(su); return satir;
}
function yuvarlak(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function hap(s, cx, cy, boyut, renk, metinRenk, alfa, olcek) {   // yuvarlak köşeli etiket
  ctx.save(); ctx.globalAlpha = alfa == null ? 1 : alfa; ctx.translate(cx, cy); ctx.scale(olcek || 1, olcek || 1);
  const w = olcu(s, boyut) + boyut * 1.1, h = boyut * 1.6;
  ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 8; ctx.fillStyle = renk; yuvarlak(-w / 2, -h / 2, w, h, h / 2); ctx.fill();
  ctx.restore(); yazi(s, cx, cy + boyut * .03, boyut, { renk: metinRenk || '#08101f', golge: false, alfa, olcek });
}

/* ---------- sahneler ---------- */
const SAHNE = {};

SAHNE.baski = (g, pr) => {
  yatak(g, 12, 12);
  const nesne = pr.nesne || 'vazo', renk = new T.Color(pr.renk != null ? pr.renk : RENK.turuncu), N = 46, lh = .2, kat = [];
  const noz = nozul(renk.getHex()); g.add(noz);
  const dislSekil = (() => { const s = new T.Shape(), n = 12, ri = 1.9, ro = 2.45; for (let i = 0; i < n * 4; i++) { const a = i / (n * 4) * Math.PI * 2, r = (i % 4 < 2) ? ro : ri; const x = Math.cos(a) * r, y = Math.sin(a) * r; if (i === 0) s.moveTo(x, y); else s.lineTo(x, y); } s.closePath(); const h = new T.Path(); h.absarc(0, 0, .8, 0, Math.PI * 2, true); s.holes.push(h); return s; })();
  const dislGeo = nesne === 'disli' ? new T.ExtrudeGeometry(dislSekil, { depth: lh, bevelEnabled: false }) : null;
  const yaricap = h => 1.5 + .85 * Math.sin(h * Math.PI * 1.2) + .12 * Math.sin(h * 30);
  const warpGeo = nesne === 'warp' ? new T.BoxGeometry(7, 1.2, 7, 18, 3, 18) : null;
  let warpMesh, warpIlk;
  if (warpGeo) { warpMesh = new T.Mesh(warpGeo, fiz(renk.getHex())); warpMesh.position.y = .6; g.add(warpMesh); warpIlk = warpGeo.attributes.position.array.slice(); }
  else for (let k = 0; k < N; k++) {
    const h0 = k / N, h1 = (k + 1) / N, c = renk.clone().lerp(new T.Color(0xffe2b0), .5 * h0 + .1 * (k % 2));
    let m;
    if (nesne === 'disli') { m = new T.Mesh(dislGeo, fiz(c.getHex())); m.rotation.x = -Math.PI / 2; m.rotation.z = k * .015; m.position.y = k * lh; }
    else if (nesne === 'kule') { m = new T.Mesh(new T.BoxGeometry(2.6 - 1.2 * h0, lh, 2.6 - 1.2 * h0), fiz(c.getHex())); m.rotation.y = k * .075; m.position.y = k * lh + lh / 2; }
    else { m = new T.Mesh(new T.CylinderGeometry(yaricap(h1), yaricap(h0), lh, 30), fiz(c.getHex())); m.position.y = k * lh + lh / 2; }
    m.visible = false; g.add(m); kat.push(m);
  }
  const isi = parilti(0xff3355, 5, 0); isi.position.y = 1; g.add(isi);
  const k4 = [[-3.5, -3.5], [3.5, -3.5], [3.5, 3.5], [-3.5, 3.5]].map(a => { const s = parilti(0xff2d55, 3, 0); g.add(s); s.position.set(a[0], .2, a[1]); return s; });
  const toz1 = toz(g, 60, 40, 3);
  return {
    cam: (p) => { const a = .55 + p * 1.2, r = 15 - 2 * p; return [Math.cos(a) * r, 6.5 + 2 * p, Math.sin(a) * r, 0, 2.2, 0]; },
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const q = sm(k01(p, .04, .96));
      if (nesne === 'warp') {
        const ust = lerp(.2, 1, sm(k01(p, 0, .5))), kal = sm(k01(p, .22, .85)) * 1.7, a = warpGeo.attributes.position;
        for (let i = 0; i < a.count; i++) {
          const x = warpIlk[i * 3], y = warpIlk[i * 3 + 1], z = warpIlk[i * 3 + 2], dd = Math.max(Math.abs(x), Math.abs(z)) / 3.5;
          a.array[i * 3 + 1] = y * ust + kal * Math.pow(dd, 3) * (y < 0 ? 1 : .7);
        }
        a.needsUpdate = true; warpGeo.computeVertexNormals();
        warpMesh.position.y = .6 * ust;
        const ac = Math.sin(lt * 9) * .5 + .5; k4.forEach(s => { s.material.opacity = kal > .3 ? ac * clamp(kal / 1.2) : 0; s.position.y = .3 + kal * .6; });
        const an = lt * 6; noz.position.set(Math.cos(an) * 2.8 * Math.sin(lt * 1.3), 1.2 * ust, Math.sin(an * 1.3) * 2.5);
        return;
      }
      const n = q * N;
      kat.forEach((m, k) => { const v = clamp(n - k); m.visible = v > .01; if (nesne === 'disli') { m.scale.z = Math.max(v, .01); } else m.scale.y = Math.max(v, .01); });
      const h = n * lh, hh = clamp(n / N), an = lt * 8.5, r = nesne === 'disli' ? 2.2 : nesne === 'kule' ? 1.5 : yaricap(hh);
      noz.position.set(Math.cos(an) * r, h, Math.sin(an) * r);
    },
    ek: (c, p, lt, d) => {
      if (nesne === 'warp') { const kal = sm(k01(p, .22, .85)); if (kal > .25) hap('⚠ KÖŞELER KALKIYOR', W / 2, 1010, 54, '#f43f5e', '#fff', outCubic(k01(kal, .25, .45)), 1 + .04 * Math.sin(lt * 10)); return; }
      const n = Math.floor(sm(k01(p, .04, .96)) * N); hap('KATMAN ' + n + ' / ' + N, W / 2, 1010, 48, 'rgba(255,255,255,.14)', '#fff', .95);
    },
  };
};

SAHNE.temizlik = (g, pr) => {
  const plaka = yatak(g, 13, 13); plaka.material.color.set(0x9aa8d0); plaka.material.roughness = .4;
  const sat = 4, gen = 5.2, yol = s => { const u = clamp(s) * sat, r = Math.min(Math.floor(u), sat - 1), f = u - r, x = (r % 2 ? 1 - f : f) * 2 * gen - gen; return [x, -4.6 + r * 3.0]; };
  const lekeler = [], R = rng(11);
  for (let i = 0; i < 11; i++) {
    const s = .06 + i / 11 * .88, [x, z] = yol(s), m = new T.Mesh(new T.CircleGeometry(.75 + R() * .5, 20), new T.MeshBasicMaterial({ color: i % 3 === 0 ? 0xffb066 : 0xffe2bd, transparent: true, opacity: .75, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.position.set(x + (R() - .5) * .6, .02 + i * .001, z + (R() - .5) * .8); m.scale.set(1 + R() * .5, 1, 1); g.add(m); lekeler.push({ m, s, x: m.position.x, z: m.position.z });
  }
  const bez = kutu(3.2, .45, 2.4, 0xcfe8ff, { roughness: .9, flatShading: false }); g.add(bez);
  const bezKenar = kutu(3.25, .1, 2.45, 0x22d3ee, { emissive: 0x22d3ee, emissiveIntensity: .6 }); bez.add(bezKenar); bezKenar.position.y = -.15;
  const sise = new T.Group(); const gov = silin(.9, .9, 2.6, 0xe9f0ff, 24, { flatShading: false }); gov.position.y = 1.3; sise.add(gov);
  const boyun = silin(.35, .9, .7, 0xe9f0ff, 24, { flatShading: false }); boyun.position.y = 2.9; sise.add(boyun);
  const kap = silin(.3, .3, .7, 0x22d3ee, 16); kap.position.y = 3.6; sise.add(kap); const ucu = kutu(.9, .35, .45, 0x22d3ee); ucu.position.set(.35, 3.9, 0); sise.add(ucu);
  const etk = kutu(1.8, 1.3, .05, 0x0e1424); etk.position.set(0, 1.3, .91); sise.add(etk); const et2 = kutu(1.4, .5, .06, 0x22d3ee, { emissive: 0x22d3ee, emissiveIntensity: .6 }); et2.position.set(0, 1.45, .93); sise.add(et2);
  sise.position.set(-6.4, 0, 5.2); sise.rotation.y = .6; g.add(sise);
  const sprey = []; for (let i = 0; i < 26; i++) { const s = parilti(0xcfeaff, .7, 0); g.add(s); sprey.push(s); }
  const par = []; for (let i = 0; i < lekeler.length; i++) { const s = parilti(0xffffff, 2.6, 0); g.add(s); par.push(s); }
  const toz1 = toz(g, 50, 40, 5);
  return {
    cam: p => [-2 + 4 * p, 15 - 2 * p, 10.5 - 1 * p, 0, 0, .8],
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const q = sm(k01(p, .22, .94)), [bx, bz] = yol(q);
      bez.position.set(bx, .3 + .08 * Math.sin(lt * 18), bz); bez.rotation.y = Math.sin(lt * 5) * .08;
      if (p < .22) { const e = p / .22; bez.position.set(lerp(-9, bx, sm(e)), .3 + 2.2 * (1 - sm(e)), lerp(-8, bz, sm(e))); }
      sise.rotation.z = -.9 * Math.sin(Math.PI * clamp(k01(p, .02, .2)) * 1) ; sise.position.y = .3 * Math.sin(Math.PI * k01(p, .0, .22));
      sprey.forEach((s, i) => { const u = (lt * 2.4 + i / sprey.length) % 1, aktif = p > .02 && p < .22; s.material.opacity = aktif ? (1 - u) * .8 : 0; s.position.set(-6.1 + (-2 - -6.1 + 0) * u * 1.0 + (i % 3 - 1) * .2, 3.5 - 2.6 * u, 5.2 + (-3 - 5.2) * u * .3 + (i % 4 - 1.5) * .25); });
      lekeler.forEach((l, i) => { const v = 1 - sm(k01(q, l.s - .035, l.s + .02)); l.m.scale.set(v * (1 + (i % 3) * .2), v, v); l.m.material.opacity = .75 * v;
        const sp = k01(q, l.s, l.s + .1); par[i].position.set(l.x, .8, l.z); par[i].material.opacity = sp > 0 && sp < 1 ? Math.sin(sp * Math.PI) * .9 : 0; par[i].scale.set(2 + sp * 2.5, 2 + sp * 2.5, 1); });
      plaka.material.emissive = new T.Color(0x22d3ee); plaka.material.emissiveIntensity = .22 * q;
    },
    ek: (c, p, lt, d) => { if (p > .9) hap('✓ TEMİZ YÜZEY', W / 2, 1010, 56, '#34d399', '#06231a', outCubic(k01(p, .9, .96))); else if (p > .1) hap('İZOPROPİL ALKOL', W / 2, 1010, 48, 'rgba(255,255,255,.14)', '#fff', .95); },
  };
};

SAHNE.ilk_katman = (g, pr) => {
  // Kesit görünümü: üç istasyon (nozul yüksekliği ve çıkan hat profili). Kamera sırayla yakınlaşır, sonunda üçünü birlikte gösterir.
  const X = [-3.2, 0, 3.2], renkS = [0xf43f5e, 0x34d399, 0xf43f5e], baslik = ['ÇOK YUKARI', 'TAM DOĞRU', 'ÇOK AŞAĞI'], simge = ['✗', '✓', '✗'];
  const zemin = kutu(10.4, .5, 4.2, RENK.plaka, { metalness: .5, roughness: .4 }); zemin.position.y = -.25; g.add(zemin);
  const taban = kutu(11, .5, 5, RENK.taban); taban.position.y = -.75; g.add(taban);
  const nz = [], bn = [], gap = [];
  X.forEach((x, i) => {
    const n = nozul(); n.scale.setScalar(.95); n.position.x = x; g.add(n); nz.push(n);
    const hy = [1.55, .34, .08][i];
    let b;
    if (i === 0) { b = new T.Mesh(new T.CylinderGeometry(.2, .2, 3.4, 14), mat(RENK.turuncu, { flatShading: false })); b.rotation.x = Math.PI / 2; b.position.set(x + 1.1, .78, 0); }
    else if (i === 1) { b = new T.Mesh(new T.CylinderGeometry(.55, .55, 3.4, 20), mat(RENK.turuncu, { flatShading: false })); b.rotation.x = Math.PI / 2; b.scale.set(1.0, 1, .5); b.position.set(x, .14, 0); }
    else { b = new T.Group(); const m = kutu(2.5, .08, 3.4, RENK.turuncu, { flatShading: false }); m.position.y = .04; b.add(m); [-1, 1].forEach(sd => { const k = new T.Mesh(new T.CylinderGeometry(.14, .14, 3.4, 12), mat(0xffa050, { flatShading: false })); k.rotation.x = Math.PI / 2; k.position.set(sd * 1.2, .13, 0); b.add(k); }); b.position.set(x, 0, 0); }
    b.scale.multiplyScalar(0.001); g.add(b); bn.push(b);
    const ok = new T.Mesh(new T.CylinderGeometry(.05, .05, 1, 8), new T.MeshBasicMaterial({ color: renkS[i] })); g.add(ok); gap.push(ok);
  });
  const isl = renkS.map((c, i) => { const s = parilti(c, 5, 0); s.position.set(X[i], .5, 1); g.add(s); return s; });
  const kivilcim = []; for (let i = 0; i < 14; i++) { const s = parilti(0xffd43b, .55, 0); g.add(s); kivilcim.push(s); }
  const toz1 = toz(g, 40, 36, 9);
  const kamX = p => p < .72 ? X[Math.min(2, Math.floor(p / .24))] : lerp(X[2], 0, sm(k01(p, .72, .8)));
  return {
    cam: p => { const e = sm(k01(p, .72, .82)); const x = p < .72 ? lerp(X[Math.max(0, Math.floor(p / .24) - 1)], X[Math.min(2, Math.floor(p / .24))], sm(k01(p % .24, 0, .06) + (p < .24 ? 1 : 0))) : lerp(X[2], 0, e); return [x, lerp(2.3, 4.6, e), lerp(8.6, 17, e), x, lerp(.8, 1, e), 0]; },
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const fin = p >= .72;
      X.forEach((x, i) => {
        const bas = i * .24 + .03, v = outBack(k01(p, bas, bas + .08));
        bn[i].scale.setScalar(Math.max(v, .001)); if (i === 1) bn[i].scale.set(Math.max(v, .001), Math.max(v, .001), Math.max(v * .5, .001) * 1);
        const hy = [1.55, .34, .08][i], girTemp = outCubic(k01(p, bas - .02, bas + .06));
        nz[i].position.y = lerp(2.4, hy, girTemp) + (i === 2 && p > bas ? .015 * Math.sin(lt * 40) : 0);
        gap[i].scale.set(1, Math.max(hy * v, .001), 1); gap[i].position.set(x - 1.1, hy * v / 2, 0); gap[i].visible = i !== 2;
        isl[i].material.opacity = (fin || (p >= bas && p < bas + .24)) ? .45 + .2 * Math.sin(lt * 6) : 0;
      });
      nz[0].position.y += .05 * Math.sin(lt * 5);
      const s = Math.min(2, Math.floor(p / .24));
      kivilcim.forEach((k, i) => { const w = (lt * 3 + i * .37) % 1, act = (p > .52 && p < .72) || fin; k.material.opacity = act ? (1 - w) : 0; k.position.set(3.2 + (i % 5 - 2) * .35 + w * (i % 2 ? 1 : -1), .15 + w * 1.1 * ((i % 3) + 1) * .4, .4); });
    },
    ek: (c, p, lt, d) => {
      const s = Math.min(2, Math.floor(p / .24)), u = (p % .24) / .24;
      if (p < .72) hap(baslik[s] + '  ' + simge[s], W / 2, 1010, 60, s === 1 ? '#34d399' : '#f43f5e', s === 1 ? '#06231a' : '#fff', outCubic(k01(u, .1, .3)), 1 + .03 * Math.sin(lt * 8));
      else [0, 1, 2].forEach(i => hap(simge[i], 540 + (i - 1) * 300, 1010, 66, i === 1 ? '#34d399' : '#f43f5e', i === 1 ? '#06231a' : '#fff', outCubic(k01(p, .8 + i * .03, .88 + i * .03))));
    },
  };
};

SAHNE.sicaklik = (g, pr) => {
  const hedef = pr.deger != null ? +pr.deger : 60, birim = pr.birim || '°C', etiket = pr.etiket || 'PLA TABLA';
  const plaka = yatak(g, 11, 11); plaka.material.color.set(0x8a9ad8); plaka.material.emissive = new T.Color(0x2a60ff); plaka.material.emissiveIntensity = .1;
  const th = new T.Group(); th.position.x = -3.4; g.add(th);
  const tup = new T.Mesh(new T.CylinderGeometry(.5, .5, 6, 24), new T.MeshStandardMaterial({ color: 0xbfe3ff, transparent: true, opacity: .28, roughness: .1, metalness: .2 })); tup.position.set(0, 3.0, 0); th.add(tup);
  const sivi = silin(.34, .34, 1, 0xff4d2d, 20, { emissive: 0xff3a1a, emissiveIntensity: .7, flatShading: false }); th.add(sivi);
  const bulb = new T.Mesh(new T.SphereGeometry(.85, 24, 18), new T.MeshStandardMaterial({ color: 0xff4d2d, emissive: 0xff3a1a, emissiveIntensity: .8 })); bulb.position.y = .55; th.add(bulb);
  const glow = parilti(0xff5a2a, 9, 0); glow.position.y = 1; th.add(glow);
  const cizg = []; for (let i = 0; i <= 8; i++) { const c = kutu(i % 2 ? .6 : 1, .06, .06, 0xdfe9ff); c.position.set(.75, .8 + i * .66, 0); th.add(c); }
  const isi = []; for (let i = 0; i < 40; i++) { const s = parilti(0xff7a3a, 1.1, 0); g.add(s); isi.push(s); }
  const toz1 = toz(g, 40, 30, 13);
  return {
    cam: p => { const a = -.35 + p * .35; return [Math.sin(a) * 15, 6 - 1 * p, Math.cos(a) * 15 - 2 * p, -1.5, 3.2, 0]; },
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const q = sm(k01(p, .08, .8)), yuks = 1 + 4.5 * q;
      sivi.scale.y = yuks; sivi.position.y = .6 + yuks / 2 - .5;
      const c = new T.Color(0x2a60ff).lerp(new T.Color(0xff5a1a), q); plaka.material.emissive = c; plaka.material.emissiveIntensity = .1 + .9 * q;
      glow.material.opacity = .15 + .6 * q; glow.scale.setScalar(7 + 3 * q + Math.sin(lt * 5) * .3);
      isi.forEach((s, i) => { const w = (lt * (.35 + (i % 7) * .05) + i * .137) % 1, a = i * 2.4; s.position.set(Math.cos(a) * (.5 + (i % 5) * 1.2), w * 9, Math.sin(a) * (.5 + (i % 5) * 1.2)); s.material.opacity = q * .35 * Math.sin(w * Math.PI); });
    },
    ek: (c, p, lt, d) => {
      const q = sm(k01(p, .08, .8)), sayi = Math.round(lerp(22, hedef, q));
      const ol = 1 + .06 * Math.sin(lt * 9) * (q < 1 ? 1 : 0) + (p > .8 ? .0 : 0);
      yazi(sayi + birim, W * .66, 760, 210, { renk: q > .5 ? '#ffb066' : '#aee3ff', kontur: 14, olcek: ol * outBack(k01(p, 0, .12)) });
      hap(etiket, W * .66, 900, 44, 'rgba(255,255,255,.14)', '#fff', .95);
    },
  };
};

SAHNE.hiz = (g, pr) => {
  const hedef = pr.deger != null ? +pr.deger : 25;
  yatak(g, 12, 12);
  const noz = nozul(); g.add(noz);
  const sat = 9, gen = 4.4, sSat = .62, seg = [];
  for (let r = 0; r < sat; r++) { const m = kutu(1, .16, .38, RENK.turuncu, { flatShading: false }); m.position.set(0, .08, -gen + r * sSat); m.visible = false; g.add(m); seg.push(m); }
  const fan = new T.Group(), govde = kutu(2.2, 2.2, .7, 0x3a4663, { metalness: .5 }); fan.add(govde);
  const kanat = new T.Group(); for (let i = 0; i < 5; i++) { const k = kutu(.22, 1.5, .08, 0xc5d2f0); k.position.y = .75; const kk = new T.Group(); kk.add(k); kk.rotation.z = i * Math.PI * 2 / 5; kanat.add(kk); } kanat.position.z = .4; fan.add(kanat);
  fan.position.set(6.8, 3.4, -1); fan.rotation.y = -.5; g.add(fan);
  const x1 = new T.Group(), a1 = kutu(3.4, .5, .3, 0xf43f5e, { emissive: 0xf43f5e, emissiveIntensity: .8 }); a1.rotation.z = Math.PI / 4; const a2 = a1.clone(); a2.rotation.z = -Math.PI / 4; x1.add(a1, a2); x1.position.set(6.2, 3.4, 0); x1.rotation.y = -.5; x1.scale.setScalar(0); g.add(x1);
  const toz1 = toz(g, 40, 30, 17);
  return {
    cam: p => [lerp(-5, 3, p), lerp(8.5, 6.5, p), lerp(12, 11, p), 1, 1.3, 0],
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const q = k01(p, .08, .92) * sat; let yaz;
      seg.forEach((m, r) => { const v = clamp(q - r), yon = r % 2 ? -1 : 1; m.visible = v > .01; m.scale.x = Math.max(v * gen * 2, .01); m.position.x = yon === 1 ? -gen + v * gen : gen - v * gen; });
      const r = Math.min(sat - 1, Math.floor(q)), v = clamp(q - r), yon = r % 2 ? -1 : 1, nx = yon === 1 ? -gen + v * gen * 2 : gen - v * gen * 2;
      noz.position.set(nx, .0, -gen + r * sSat);
      const dur = sm(k01(p, .12, .5)); kanat.rotation.z = lt * 14 * (1 - dur) + 0; kanat.rotation.z = (kanat.rotation.z) % (Math.PI * 2);
      x1.scale.setScalar(outBack(k01(p, .5, .62))); x1.position.y = 3.4;
    },
    ek: (c, p, lt, d) => {
      const sayi = Math.round(lerp(60, hedef, sm(k01(p, .05, .45))));
      yazi(sayi + ' mm/s', W / 2, 880, 150, { renk: '#ffd43b', kontur: 12, olcek: outBack(k01(p, 0, .1)) });
      hap(p > .5 ? 'FAN KAPALI' : 'YAVAŞ BAŞLA', W / 2, 1020, 50, p > .5 ? '#f43f5e' : 'rgba(255,255,255,.14)', '#fff', .95);
    },
  };
};

SAHNE.yapistirici = (g, pr) => {
  const plaka = yatak(g, 12, 12);
  const film = new T.Mesh(new T.PlaneGeometry(10.6, 10.6), new T.MeshBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0, depthWrite: false })); film.rotation.x = -Math.PI / 2; film.position.y = .03; g.add(film);
  const seritler = []; for (let i = 0; i < 6; i++) { const m = new T.Mesh(new T.PlaneGeometry(1, 1.9), new T.MeshBasicMaterial({ color: 0xbfe6ff, transparent: true, opacity: .0, depthWrite: false })); m.rotation.x = -Math.PI / 2; m.position.set(0, .04 + i * .001, -4.4 + i * 1.75); g.add(m); seritler.push(m); }
  const stik = new T.Group(); const gv = silin(.85, .85, 3, 0xff4d8d, 24, { flatShading: false }); gv.position.y = 1.5; stik.add(gv); const ic = silin(.62, .62, 1.2, 0xeaf6ff, 24, { flatShading: false }); ic.position.y = 3.4; stik.add(ic); const kp = silin(.9, .9, .3, 0xffffff, 24); kp.position.y = .15; stik.add(kp); g.add(stik);
  const parca = new T.Mesh(new T.BoxGeometry(3.6, 1.4, 3.6), fiz(0xff7a1a)); parca.position.y = .7; parca.scale.y = 0; g.add(parca);
  const brim = []; [[0, -2.9, 8.4, 1.3], [0, 2.9, 8.4, 1.3], [-2.9, 0, 1.3, 4.4], [2.9, 0, 1.3, 4.4]].forEach(a => { const m = kutu(a[2], .12, a[3], 0xffb066, { emissive: 0xff7a1a, emissiveIntensity: .35, flatShading: false }); m.position.set(a[0], .09, a[1]); m.scale.set(0, 1, 0); g.add(m); brim.push([m, a]); });
  const toz1 = toz(g, 40, 30, 21);
  return {
    cam: p => [lerp(-6, 5, p), lerp(13, 9, p), lerp(8, 10.5, p), 0, 0, 0],
    upd: (p, lt, d) => {
      tozGuncelle(toz1, lt);
      const q = sm(k01(p, .06, .5));
      seritler.forEach((m, i) => { const v = clamp(q * 6 - i); m.scale.set(10.6 * v, 1, 1); m.position.x = -5.3 + 5.3 * v; m.material.opacity = .32 * (v > .01 ? 1 : 0); });
      film.material.opacity = 0;
      const r = Math.min(5, Math.floor(q * 6)), v = clamp(q * 6 - r), yon = r % 2 ? -1 : 1;
      stik.position.set((yon === 1 ? -5.3 + v * 10.6 : 5.3 - v * 10.6) * (q >= 1 ? 0 : 1) + (q >= 1 ? 8 : 0), 1.2 + (q >= 1 ? 3 : 0) + .15 * Math.sin(lt * 18), -4.4 + r * 1.75); stik.rotation.z = yon * .25 * (q >= 1 ? 0 : 1);
      stik.visible = p < .62; stik.position.x = p > .5 ? lerp(stik.position.x, 9, sm(k01(p, .5, .6))) : stik.position.x;
      parca.scale.y = Math.max(.001, sm(k01(p, .52, .62)));
      const b = sm(k01(p, .62, .9)); brim.forEach(([m, a]) => { m.scale.set(b, 1, b); });
    },
    ek: (c, p, lt, d) => { hap(p < .55 ? 'YAPIŞTIRICI ÇUBUK' : 'BRIM: GENİŞ KENAR', W / 2, 1010, 50, p < .55 ? 'rgba(255,255,255,.14)' : '#ff7a1a', p < .55 ? '#fff' : '#1a0d00', .95); },
  };
};

SAHNE.sayi = (g, pr) => {
  const hedef = pr.deger != null ? +pr.deger : 100, birim = pr.birim || '%', etiket = pr.etiket || '';
  const halka = []; for (let i = 0; i < 4; i++) { const t = new T.Mesh(new T.TorusGeometry(2.6 + i * .9, .05 + i * .015, 10, 70), mat(i % 2 ? RENK.camgobegi : RENK.turuncu, { emissive: i % 2 ? RENK.camgobegi : RENK.turuncu, emissiveIntensity: .7, flatShading: false })); t.position.y = 4; g.add(t); halka.push(t); }
  const kup = []; const R = rng(33); for (let i = 0; i < 26; i++) { const k = kutu(.5 + R() * .6, .5 + R() * .6, .5 + R() * .6, i % 3 ? 0x2b3a66 : RENK.turuncu); k.userData = { a: R() * 6.28, r: 5 + R() * 5, y: 1 + R() * 7, v: .15 + R() * .3 }; g.add(k); kup.push(k); }
  const toz1 = toz(g, 60, 40, 23);
  const zemin = kutu(14, .3, 14, RENK.plaka, { metalness: .5 }); zemin.position.y = -.2; g.add(zemin);
  return {
    cam: p => [Math.sin(p * .5) * 4, 4.5, 14 - 2 * p, 0, 4, 0],
    upd: (p, lt) => { tozGuncelle(toz1, lt); halka.forEach((h, i) => { h.rotation.x = Math.PI / 2 + Math.sin(lt * .7 + i) * .5; h.rotation.y = lt * (.3 + i * .15) * (i % 2 ? -1 : 1); }); kup.forEach(k => { const u = k.userData, a = u.a + lt * u.v; k.position.set(Math.cos(a) * u.r, u.y + Math.sin(lt + u.a) * .5, Math.sin(a) * u.r - 2); k.rotation.set(lt * u.v * 2, lt * u.v, 0); }); },
    ek: (c, p, lt) => {
      const q = outCubic(k01(p, .05, .55)), s = Math.round(hedef * q); leke(W / 2, 900, 520, .75);
      yazi(s + birim, W / 2, 800, 290, { renk: '#ffb066', kontur: 16, olcek: outBack(k01(p, 0, .12)) });
      if (etiket) { const sat = sar(etiket, 58, 820); sat.forEach((s2, i) => yazi(s2, W / 2, 1000 + i * 76, 58, { renk: '#fff', kontur: 8, alfa: outCubic(k01(p, .25, .4)) })); }
    },
  };
};

SAHNE.karsilastir = (g, pr) => {
  const A = pr.a || { ad: 'A', deger: 30 }, B = pr.b || { ad: 'B', deger: 90 }, mx = Math.max(A.deger, B.deger, 1);
  const zemin = kutu(15, .4, 8, RENK.plaka, { metalness: .5 }); zemin.position.y = -.2; g.add(zemin);
  const sutun = (x, renk) => { const m = silin(1.6, 1.6, 1, renk, 6, { emissive: renk, emissiveIntensity: .22 }); m.position.x = x; g.add(m); const ust = parilti(renk, 5, .5); g.add(ust); return [m, ust]; };
  const a = sutun(-3.4, 0xf43f5e), b = sutun(3.4, 0x34d399), toz1 = toz(g, 50, 40, 29);
  const maxH = 8;
  return {
    cam: p => [Math.sin(p) * 3, 5.5, 15, 0, 4.2, 0],
    upd: (p, lt) => { tozGuncelle(toz1, lt); [[a, A], [b, B]].forEach(([s, v], i) => { const h = Math.max(.05, maxH * v.deger / mx * outBack(k01(p, .1 + i * .12, .55 + i * .12))); s[0].scale.y = h; s[0].position.y = h / 2; s[0].rotation.y = lt * .5; s[1].position.set(s[0].position.x, h + .3, 0); }); },
    ek: (c, p, lt) => {
      [[A, 270, '#f43f5e'], [B, 810, '#34d399']].forEach(([v, x, r], i) => { const a2 = outCubic(k01(p, .3 + i * .12, .5 + i * .12)); yazi(String(v.deger_yazi || v.deger) + (v.birim || ''), x, 760 + (1 - a2) * 40, 110, { renk: r, kontur: 10, alfa: a2 }); yazi(v.ad, x, 1010, 52, { renk: '#fff', kontur: 8, alfa: a2 }); });
    },
  };
};

SAHNE.ozet = (g, pr) => {
  const maddeler = (pr.maddeler || []).slice(0, 5);
  const plaka = yatak(g, 12, 12), noz = nozul(); g.add(noz);
  const kup = []; const R = rng(41); for (let i = 0; i < 18; i++) { const k = kutu(.8, .8, .8, i % 3 ? 0x2b3a66 : RENK.turuncu); k.userData = { a: R() * 6.28, r: 5 + R() * 4, y: 2 + R() * 7, v: .12 + R() * .25 }; g.add(k); kup.push(k); }
  const toz1 = toz(g, 50, 40, 31);
  return {
    cam: p => [Math.sin(p * .8) * 5, 7.5, 16, 0, 3.5, 0],
    upd: (p, lt) => { tozGuncelle(toz1, lt); noz.position.set(Math.cos(lt * 3) * 3, 3.5 + Math.sin(lt * 2), Math.sin(lt * 3) * 3); kup.forEach(k => { const u = k.userData, a = u.a + lt * u.v; k.position.set(Math.cos(a) * u.r, u.y + Math.sin(lt + u.a) * .4, Math.sin(a) * u.r - 3); k.rotation.set(lt * u.v * 2, lt * u.v, 0); }); },
    ek: (c, p, lt, d) => {
      const bas = 640, ara = 128;
      maddeler.forEach((m, i) => {
        const a = outBack(k01(p, .08 + i * (.55 / Math.max(maddeler.length, 1)), .08 + i * (.55 / Math.max(maddeler.length, 1)) + .12)), y = bas + i * ara;
        ctx.save(); ctx.globalAlpha = clamp(a); ctx.translate(W / 2 + (1 - clamp(a)) * 160, y); ctx.fillStyle = 'rgba(14,20,36,.82)'; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 24; yuvarlak(-420, -48, 840, 96, 30); ctx.fill(); ctx.restore();
        ctx.save(); ctx.globalAlpha = clamp(a); ctx.fillStyle = '#34d399'; ctx.beginPath(); ctx.arc(W / 2 - 360 + (1 - clamp(a)) * 160, y, 30, 0, 7); ctx.fill(); ctx.restore();
        yazi('✓', W / 2 - 360 + (1 - clamp(a)) * 160, y + 2, 38, { renk: '#06231a', golge: false, alfa: clamp(a) });
        yazi(m, W / 2 - 300 + (1 - clamp(a)) * 160, y + 2, 50, { renk: '#fff', hiza: 'left', golge: false, alfa: clamp(a), agirlik: 800 });
      });
    },
  };
};

SAHNE.cta = (g, pr) => {
  const yuz = new T.Mesh(new T.IcosahedronGeometry(1.9, 1), mat(RENK.turuncu, { emissive: RENK.turuncu, emissiveIntensity: .35 })); yuz.position.y = 4.6; g.add(yuz);
  const hl = new T.Mesh(new T.TorusGeometry(3.1, .1, 10, 80), mat(RENK.camgobegi, { emissive: RENK.camgobegi, emissiveIntensity: .9, flatShading: false })); hl.position.y = 4.6; g.add(hl);
  const hl2 = hl.clone(); hl2.scale.setScalar(1.25); g.add(hl2);
  const gl = parilti(RENK.turuncu, 12, .55); gl.position.y = 4.6; g.add(gl);
  const toz1 = toz(g, 70, 40, 37);
  const zemin = kutu(14, .3, 14, RENK.plaka, { metalness: .5 }); zemin.position.y = -.2; g.add(zemin);
  return {
    cam: p => [Math.sin(p * .6) * 3, 5, 15 - 2 * p, 0, 4.6, 0],
    upd: (p, lt) => { tozGuncelle(toz1, lt); yuz.rotation.set(lt * .6, lt * .9, 0); hl.rotation.set(lt * .5, lt * .3, 0); hl2.rotation.set(-lt * .3, lt * .45, 1); yuz.scale.setScalar(1 + .04 * Math.sin(lt * 4)); },
    ek: (c, p, lt) => {
      const a = outBack(k01(p, .05, .25)); leke(W / 2, 930, 520, .8);
      yazi(pr.ana || 'TAKİP ET', W / 2, 860, 150, { renk: '#fff', kontur: 12, olcek: a });
      hap(pr.alt || '@gurtechs3d', W / 2, 1020, 62, '#ff7a1a', '#1a0d00', outCubic(k01(p, .2, .35)), 1 + .025 * Math.sin(lt * 5));
    },
  };
};

/* ---------- ana motor ---------- */
window.hazirla = async function (plan, olcek) {
  P = plan; OL = olcek || 1; W = plan.genislik; H = plan.yukseklik;
  glc = document.getElementById('gl'); c2 = document.getElementById('c2');
  renderer = new T.WebGLRenderer({ canvas: glc, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(W * OL, H * OL, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
  renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = .95;
  c2.width = W * OL; c2.height = H * OL; ctx = c2.getContext('2d');
  await document.fonts.load('800 80px IB'); await document.fonts.load('600 40px IS');
  GLOW = glowTex();
  scene3 = new T.Scene(); scene3.background = new T.Color(RENK.bg); scene3.environment = ortamHaritasi(); scene3.fog = new T.Fog(RENK.bg, 26, 80);
  kam = new T.PerspectiveCamera(46, W / H, .1, 300);
  const zemin = new T.Mesh(new T.PlaneGeometry(OFS * (plan.sahneler.length + 4), 160), new T.MeshBasicMaterial({ map: gridTex() }));
  zemin.material.map.repeat.set(OFS * (plan.sahneler.length + 4) / 4, 40); zemin.rotation.x = -Math.PI / 2; zemin.position.set(OFS * plan.sahneler.length / 2, -1.52, 0); scene3.add(zemin);
  scene3.add(new T.HemisphereLight(0xaec8ff, 0x1a1030, .35));
  isiklar.k = new T.DirectionalLight(0xfff0dd, 1.0); isiklar.k.castShadow = true; isiklar.k.shadow.mapSize.set(1536, 1536);
  Object.assign(isiklar.k.shadow.camera, { left: -13, right: 13, top: 13, bottom: -13, near: 1, far: 70 }); isiklar.k.shadow.bias = -.0006; isiklar.k.shadow.radius = 3; scene3.add(isiklar.k, isiklar.k.target);
  isiklar.r = new T.PointLight(0x22d3ee, .6, 60); scene3.add(isiklar.r);
  isiklar.s = new T.PointLight(0xff7a1a, .35, 40); scene3.add(isiklar.s);
  sahneler = plan.sahneler.map((s, i) => {
    const g = new T.Group(); g.position.set(i * OFS, 0, 0); scene3.add(g);
    const yap = SAHNE[s.tip] || SAHNE.baski;
    const n = Object.assign({ g, s }, yap(g, s.params || {}));
    if (['baski', 'hiz', 'yapistirici', 'ozet', 'sicaklik', 'temizlik'].includes(s.tip)) n.yazici = yaziciArka(g, 0, -10);
    n.bokeh = bokeh(g, 11 + i * 7); n.havuz = zeminIsigi(g, 12, s.tip === 'sicaklik' ? 'rgba(255,90,40,.5)' : s.tip === 'temizlik' ? 'rgba(34,211,238,.4)' : 'rgba(255,122,26,.5)');
    g.traverse(m => { if (m.isMesh) { const mm = m.material; const seffaf = mm && (mm.transparent || mm.isMeshBasicMaterial); if (mm && mm.isMeshStandardMaterial) mm.envMapIntensity = .45; m.castShadow = !seffaf; m.receiveShadow = !seffaf; } });
    return n;
  });
  return { sahne: sahneler.length };
};

function kameraSec(t) {
  // etkin sahne + geçiş karışımı
  let i = sahneler.findIndex(x => t < x.s.t1); if (i < 0) i = sahneler.length - 1;
  const s = sahneler[i], d = s.s.t1 - s.s.t0, lp = clamp((t - s.s.t0) / d);
  const cam = (n, p) => { const c = n.cam(p, p * (n.s.t1 - n.s.t0)); return c.map((v, k) => k % 3 === 0 && k < 6 ? v : v); };
  const dunya = (n, idx, c) => [c[0] + idx * OFS, c[1], c[2], c[3] + idx * OFS, c[4], c[5]];
  let c = dunya(s, i, cam(s, lp)), fov = 46, u = 0;
  // geçiş: sahne sonu → sonraki sahne başı
  const sonraki = sahneler[i + 1];
  if (sonraki && t > s.s.t1 - GECIS / 2) {
    u = (t - (s.s.t1 - GECIS / 2)) / GECIS; const e = sm(u), b = dunya(sonraki, i + 1, cam(sonraki, 0)), a = dunya(s, i, cam(s, 1));
    c = a.map((v, k) => lerp(v, b[k], e)); fov = 46 + 16 * Math.sin(Math.PI * u);
  } else if (i > 0 && t < s.s.t0 + GECIS / 2) {
    u = .5 + (t - s.s.t0) / GECIS; const e = sm(u), onceki = sahneler[i - 1], a = dunya(onceki, i - 1, cam(onceki, 1)), b = dunya(s, i, cam(s, 0));
    c = a.map((v, k) => lerp(v, b[k], e)); fov = 46 + 16 * Math.sin(Math.PI * u);
  }
  const uz = (sahneler[Math.min(sahneler.length - 1, Math.max(0, Math.round((c[3]) / OFS)))].s.uzak) || UZAK[sahneler[Math.min(sahneler.length - 1, Math.max(0, Math.round((c[3]) / OFS)))].s.tip] || 1.3;
  c = [c[3] + (c[0] - c[3]) * uz, c[4] + (c[1] - c[4]) * uz, c[5] + (c[2] - c[5]) * uz, c[3], c[4], c[5]];
  return { c, fov, u };
}

function ciz3(t) {
  const { c, fov, u } = kameraSec(t);
  const sar2 = u > 0 ? Math.sin(Math.PI * u) * .02 : 0;
  kam.fov = fov; kam.setViewOffset(W * OL, H * OL, 0, 250 * OL, W * OL, H * OL);
  kam.position.set(c[0] + Math.sin(t * 1.3) * .04, c[1] + Math.cos(t * 1.1) * .04, c[2]); kam.lookAt(c[3], c[4], c[5]); kam.rotation.z += sar2 * Math.sin(t * 40);
  isiklar.k.position.set(c[3] + 8, 14, c[5] + 8); isiklar.k.target.position.set(c[3], 0, c[5]);
  isiklar.r.position.set(c[3] - 8, 6, c[5] + 4); isiklar.s.position.set(c[3] + 3, 3, c[5] + 6);
  sahneler.forEach((n, i) => { const d = n.s.t1 - n.s.t0, lt = clamp(t - n.s.t0, 0, d + 1), p = clamp((t - n.s.t0) / d); n.g.visible = Math.abs(i * OFS - c[3]) < OFS * 1.1; if (n.g.visible) { n.upd(p, lt, d); FANLAR.forEach(f => { f.rotation.z = -t * 28; }); bokehGuncelle(n.bokeh, t); if (n.yazici) n.yazici.userData.makara.rotation.z = -t * .6; n.havuz.material.opacity = .85 + .15 * Math.sin(t * 2 + i); } });
  renderer.render(scene3, kam);
}

function ekranYazilari(t) {
  let i = sahneler.findIndex(x => t < x.s.t1); if (i < 0) i = sahneler.length - 1;
  const n = sahneler[i], s = n.s, d = s.t1 - s.t0, lt = t - s.t0, p = clamp(lt / d);
  // vinyet
  const gr = ctx.createRadialGradient(W / 2, H * .5, H * .25, W / 2, H * .5, H * .75); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(2,4,12,.62)'); ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  // başlık
  if (s.ekran) {
    const gir = outBack(k01(lt, .12, .5)), cik = 1 - k01(lt, d - .45, d - .15), a = clamp(gir) * cik;
    const boyut = s.ekran.length > 22 ? 86 : 104, sat = sar(s.ekran, boyut, 900), y0 = 250 - (sat.length - 1) * boyut * .55;
    if (s.rozet) { const ra = outBack(k01(lt, .05, .4)); ctx.save(); ctx.globalAlpha = clamp(ra) * cik; ctx.translate(W / 2, y0 - boyut * .95 - 30); ctx.scale(ra, ra); ctx.fillStyle = '#ff7a1a'; ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 20; ctx.beginPath(); ctx.arc(0, 0, 54, 0, 7); ctx.fill(); ctx.restore(); yazi(String(s.rozet), W / 2, y0 - boyut * .95 - 28, 64, { renk: '#1a0d00', golge: false, alfa: clamp(ra) * cik, olcek: ra }); }
    sat.forEach((l, k) => yazi(l, W / 2, y0 + k * boyut * 1.08 + (1 - clamp(gir)) * 40, boyut, { renk: s.vurgu_renk || '#fff', kontur: 16, alfa: a, olcek: .7 + .3 * clamp(gir) }));
  }
  n.ek && n.ek(ctx, p, lt, d);
  // altyazı
  const al = P.altyazi.find(x => t >= x.t0 - .05 && t < x.t1 + .12);
  if (al) {
    const boyut = 74, kelimeler = al.kelimeler, satir = [[]], gen = 900; let cur = 0;
    kelimeler.forEach(w => { const wd = olcu(w.k, boyut) + boyut * .3; if (cur + wd > gen && satir[satir.length - 1].length) { satir.push([]); cur = 0; } satir[satir.length - 1].push(w); cur += wd; });
    const y0 = 1330 - (satir.length - 1) * 50, giris = outCubic(k01(t, al.t0 - .05, al.t0 + .1));
    satir.forEach((sa, li) => {
      const tg = sa.reduce((a, w) => a + olcu(w.k, boyut) + boyut * .3, 0) - boyut * .3; let x = W / 2 - tg / 2;
      sa.forEach(w => {
        const wd = olcu(w.k, boyut), aktif = t >= w.t0 && t < w.t1 + .02, gecti = t >= w.t1, cx = x + wd / 2, pop = aktif ? 1 + .12 * Math.sin(Math.PI * clamp((t - w.t0) / Math.max(.18, w.t1 - w.t0))) : 1;
        yazi(w.k, cx, y0 + li * 104 + (1 - giris) * 30, boyut, { renk: aktif ? '#ffd43b' : gecti ? '#ffffff' : 'rgba(255,255,255,.88)', kontur: 18, alfa: giris, olcek: pop });
        x += wd + boyut * .3;
      });
    });
  }
  // geçiş patlaması
  for (let k = 0; k < sahneler.length - 1; k++) { const b = sahneler[k].s.t1, dt = Math.abs(t - b); if (dt < .28) { ctx.fillStyle = `rgba(255,255,255,${(.3 * Math.pow(1 - dt / .28, 2)).toFixed(3)})`; ctx.fillRect(0, 0, W, H); } }
  // açılış/bitiş yumuşatma
  const son = P.sure - t, bas = t; const kar = Math.max(1 - k01(bas, 0, .25), 1 - k01(son, 0, .5)); if (kar > 0) { ctx.fillStyle = `rgba(5,8,18,${kar.toFixed(3)})`; ctx.fillRect(0, 0, W, H); }
}

let BK1, BK2, BK0, BRT, BBUF, BK3, GRAIN;
function parlama() {   // bloom: sahneyi küçük bir hedefe ayrıca çizer (ucuz), parlak bölgeyi süzüp bulanıklaştırır, üste "lighter" ile ekler
  const w0 = Math.round(c2.width / 5), h0 = Math.round(c2.height / 5), w2 = Math.round(c2.width / 12), h2 = Math.round(c2.height / 12);
  if (!BK1) {
    BK0 = document.createElement('canvas'); BK1 = document.createElement('canvas'); BK2 = document.createElement('canvas');
    BK0.width = BK1.width = w0; BK0.height = BK1.height = h0; BK2.width = w2; BK2.height = h2;
    BRT = new T.WebGLRenderTarget(w0, h0); BBUF = new Uint8ClampedArray(w0 * h0 * 4);
    BK3 = document.createElement('canvas'); BK3.width = w0; BK3.height = h0;
    GRAIN = document.createElement('canvas'); GRAIN.width = GRAIN.height = 256; const gx = GRAIN.getContext('2d'), gi = gx.createImageData(256, 256), R2 = rng(99); for (let i = 0; i < gi.data.length; i += 4) { const v = 118 + Math.floor(R2() * 40); gi.data[i] = gi.data[i + 1] = gi.data[i + 2] = v; gi.data[i + 3] = 255; } gx.putImageData(gi, 0, 0);
  }
  const sg = renderer.shadowMap.enabled; renderer.shadowMap.autoUpdate = false;
  renderer.setRenderTarget(BRT); renderer.render(scene3, kam); renderer.setRenderTarget(null); renderer.shadowMap.autoUpdate = true;
  renderer.readRenderTargetPixels(BRT, 0, 0, w0, h0, new Uint8Array(BBUF.buffer));
  const z = BK0.getContext('2d'), a = BK1.getContext('2d'), b = BK2.getContext('2d');
  z.putImageData(new ImageData(BBUF, w0, h0), 0, 0);
  a.save(); a.setTransform(1, 0, 0, -1, 0, h0); a.filter = 'brightness(.5) contrast(3.4) blur(2px)'; a.drawImage(BK0, 0, 0); a.restore();
  b.filter = 'blur(2px)'; b.drawImage(BK1, 0, 0, w2, h2); b.filter = 'none';
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'lighter'; ctx.imageSmoothingQuality = 'high';
  ctx.globalAlpha = .45; ctx.drawImage(BK2, 0, 0, c2.width, c2.height); ctx.restore();
  // tilt-shift: alt ve üst bantlar bulanık (sinematik alan derinliği)
  const a3 = BK3.getContext('2d'); a3.save(); a3.setTransform(1, 0, 0, -1, 0, h0); a3.filter = 'blur(2.5px)'; a3.drawImage(BK0, 0, 0); a3.restore(); a3.filter = 'none';
  a3.globalCompositeOperation = 'destination-in'; const gr = a3.createLinearGradient(0, 0, 0, h0); gr.addColorStop(0, 'rgba(0,0,0,.85)'); gr.addColorStop(.17, 'rgba(0,0,0,0)'); gr.addColorStop(.62, 'rgba(0,0,0,0)'); gr.addColorStop(.86, 'rgba(0,0,0,.9)'); gr.addColorStop(1, 'rgba(0,0,0,1)'); a3.fillStyle = gr; a3.fillRect(0, 0, w0, h0); a3.globalCompositeOperation = 'source-over';
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.imageSmoothingQuality = 'high'; ctx.drawImage(BK3, 0, 0, c2.width, c2.height);
  // film greni
  const ox = Math.floor(Math.abs(Math.sin(c2.width + (window.__kareNo = (window.__kareNo || 0) + 1) * 12.9898)) * 256), oy = Math.floor(Math.abs(Math.sin(window.__kareNo * 78.233)) * 256);
  ctx.globalCompositeOperation = 'overlay'; ctx.globalAlpha = .12; ctx.translate(-ox, -oy); ctx.fillStyle = ctx.createPattern(GRAIN, 'repeat'); ctx.fillRect(0, 0, c2.width + 256, c2.height + 256); ctx.restore();
}
function hud(t, s, lt, d) {   // nesne alanının köşe işaretleri (hareket tasarımı detayı)
  const a = outCubic(k01(lt, .2, .7)) * (1 - k01(lt, d - .4, d - .1)) * .75, x0 = 70, x1 = W - 70, y0 = 420, y1 = 980, u = 64 + 6 * Math.sin(t * 3);
  if (a <= 0.01) return;
  ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.shadowColor = '#22d3ee'; ctx.shadowBlur = 14;
  [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]].forEach(([x, y, dx, dy]) => { ctx.beginPath(); ctx.moveTo(x + dx * u, y); ctx.lineTo(x, y); ctx.lineTo(x, y + dy * u); ctx.stroke(); });
  ctx.restore();
}
window.kare = function (t, kalite) {
  // geçiş penceresinde hareket bulanıklığı: 4 alt kare ortalaması
  let gecis = false; for (let k = 0; k < sahneler.length - 1; k++) if (Math.abs(t - sahneler[k].s.t1) < GECIS / 2) gecis = true;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, c2.width, c2.height);
  const n = gecis ? 4 : 1;
  for (let k = 0; k < n; k++) { ciz3(Math.max(0, t - k * .011)); ctx.globalAlpha = 1 / (k + 1); ctx.drawImage(glc, 0, 0, c2.width, c2.height); }
  ctx.globalAlpha = 1; parlama();
  ctx.setTransform(OL, 0, 0, OL, 0, 0);
  let i = sahneler.findIndex(x => t < x.s.t1); if (i < 0) i = sahneler.length - 1; const sc = sahneler[i].s; hud(t, sc, t - sc.t0, sc.t1 - sc.t0);
  ekranYazilari(t);
  return c2.toDataURL('image/jpeg', kalite || .92).slice(23);
};
