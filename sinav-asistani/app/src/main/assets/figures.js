/* Sınav Asistanı — soru görselleri için çizim motoru.
 * Yapay zekâ şekli çizmez; yalnızca hangi şeklin hangi değerlerle çizileceğini (JSON) söyler.
 * Bu dosya o tarifi tutarlı, ders kitabı düzeninde bir SVG'ye çevirir.
 */
"use strict";

const FIG = (() => {
  const C = {
    ink: "#1f2937",
    line: "#334155",
    soft: "#94a3b8",
    fill: "#dbeafe",
    shade: "#3b82f6",
    shade2: "#93c5fd",
    accent: "#f59e0b",
    accentInk: "#92400e",
    grid: "#e2e8f0",
    head: "#dbeafe",
    zebra: "#f8fafc",
  };
  const FONT = "Roboto, 'Noto Sans', Arial, sans-serif";

  const x = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
  const int = (v, lo, hi, d) => Math.min(hi, Math.max(lo, Math.round(num(v, d))));
  const r1 = (v) => Math.round(v * 10) / 10;
  const fmt = (v) => {
    const n = Math.round(v * 1000) / 1000;
    return String(n).replace(".", ",");
  };

  function text(tx, ty, s, o = {}) {
    const size = o.size || 18;
    const anchor = o.anchor || "middle";
    const weight = o.bold ? 700 : 400;
    const fill = o.fill || C.ink;
    const base = o.base || "middle";
    return `<text x="${r1(tx)}" y="${r1(ty)}" font-family="${FONT}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" dominant-baseline="${base}">${x(s)}</text>`;
  }

  function wrap(w, h, body) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${Math.round(w)} ${Math.round(h)}" width="${Math.round(w)}" height="${Math.round(h)}">` +
      `<rect width="100%" height="100%" fill="#ffffff"/>${body}</svg>`;
  }

  const arrowDefs = `<defs><marker id="ok" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${C.line}"/></marker></defs>`;

  /** Soru işaretli / harfli işaret balonu */
  function badge(cx, cy, label) {
    const w = Math.max(30, String(label).length * 12 + 16);
    return `<rect x="${r1(cx - w / 2)}" y="${r1(cy - 15)}" width="${w}" height="30" rx="15" fill="${C.accent}"/>` +
      text(cx, cy + 1, label, { size: 18, bold: true, fill: "#ffffff" });
  }

  /* ---------- Sayı doğrusu ---------- */
  function sayiDogrusu(f) {
    let a = num(f.baslangic, 0), b = num(f.bitis, 10), s = Math.abs(num(f.adim, 1)) || 1;
    if (b <= a) b = a + 10 * s;
    let steps = Math.round((b - a) / s);
    if (steps > 24) { s = (b - a) / 20; steps = 20; }
    const W = 560, H = 170, X0 = 40, X1 = W - 40, Y = 100;
    const px = (v) => X0 + ((v - a) / (b - a)) * (X1 - X0);
    let g = arrowDefs + `<line x1="${X0 - 25}" y1="${Y}" x2="${X1 + 25}" y2="${Y}" stroke="${C.line}" stroke-width="3" marker-start="url(#ok)" marker-end="url(#ok)"/>`;
    const show = f.sayilari_goster !== false;
    for (let i = 0; i <= steps; i++) {
      const v = a + i * s, p = px(v);
      g += `<line x1="${r1(p)}" y1="${Y - 10}" x2="${r1(p)}" y2="${Y + 10}" stroke="${C.line}" stroke-width="2.5"/>`;
      if (show) g += text(p, Y + 30, fmt(v), { size: 17 });
    }
    for (const m of (f.isaretler || []).slice(0, 6)) {
      const v = num(m.deger, NaN);
      if (!Number.isFinite(v) || v < a - 1e-9 || v > b + 1e-9) continue;
      const p = px(v);
      g += `<circle cx="${r1(p)}" cy="${Y}" r="8" fill="${C.accent}" stroke="#ffffff" stroke-width="2"/>`;
      if (m.yazi) g += `<line x1="${r1(p)}" y1="${Y - 12}" x2="${r1(p)}" y2="${Y - 30}" stroke="${C.accent}" stroke-width="2"/>` + badge(p, Y - 46, m.yazi);
    }
    return wrap(W, H, g);
  }

  /* ---------- Kesir modelleri ---------- */
  function pie(cx, cy, r, n, k) {
    if (n === 1) return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${k ? C.shade : "#fff"}" stroke="${C.line}" stroke-width="2.5"/>`;
    let g = "";
    for (let i = 0; i < n; i++) {
      const t0 = -Math.PI / 2 + (i * 2 * Math.PI) / n, t1 = -Math.PI / 2 + ((i + 1) * 2 * Math.PI) / n;
      const p0 = [cx + r * Math.cos(t0), cy + r * Math.sin(t0)], p1 = [cx + r * Math.cos(t1), cy + r * Math.sin(t1)];
      const large = t1 - t0 > Math.PI ? 1 : 0;
      g += `<path d="M${r1(cx)},${r1(cy)} L${r1(p0[0])},${r1(p0[1])} A${r},${r} 0 ${large} 1 ${r1(p1[0])},${r1(p1[1])} Z" fill="${i < k ? C.shade : "#ffffff"}" stroke="${C.line}" stroke-width="2.5" stroke-linejoin="round"/>`;
    }
    return g;
  }

  function kesir(f) {
    const models = (f.modeller || []).slice(0, 4);
    if (!models.length) return "";
    const n = models.length;
    const W = n === 1 ? 380 : n * 190 + 40, H = 230;
    const cell = (W - 40) / n;
    let g = "";
    models.forEach((m, i) => {
      const parts = int(m.parca, 1, 24, 4), sh = int(m.boyali, 0, parts, 0);
      const cx = 20 + cell * i + cell / 2;
      if (m.sekil === "daire") {
        g += pie(cx, 95, n === 1 ? 85 : 70, parts, sh);
      } else {
        const w = Math.min(cell - 30, n === 1 ? 300 : 170), h = n === 1 ? 110 : 90, x0 = cx - w / 2, y0 = n === 1 ? 40 : 50;
        const pw = w / parts;
        for (let j = 0; j < parts; j++) {
          g += `<rect x="${r1(x0 + j * pw)}" y="${y0}" width="${r1(pw)}" height="${h}" fill="${j < sh ? C.shade : "#ffffff"}" stroke="${C.line}" stroke-width="2.5"/>`;
        }
      }
      if (m.yazi) g += text(cx, 200, m.yazi, { size: 20, bold: true });
    });
    return wrap(W, H, g);
  }

  /* ---------- Sütun grafiği ---------- */
  function niceMax(v) {
    if (v <= 0) return 10;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const k of [1, 2, 2.5, 5, 10]) if (k * p >= v) return k * p;
    return 10 * p;
  }

  function sutunGrafik(f) {
    const bars = (f.cubuklar || []).slice(0, 8).map((c) => ({ ad: String(c.ad || ""), v: Math.max(0, num(c.deger, 0)) }));
    if (!bars.length) return "";
    const W = 560, H = 320, L = 64, R = 20, T = f.baslik ? 48 : 22, B = 50;
    const max = niceMax(Math.max(...bars.map((b) => b.v)));
    const ticks = 5;
    const py = (v) => H - B - (v / max) * (H - B - T);
    let g = "";
    if (f.baslik) g += text(W / 2, 24, f.baslik, { size: 19, bold: true });
    for (let i = 0; i <= ticks; i++) {
      const v = (max / ticks) * i, y = py(v);
      g += `<line x1="${L}" y1="${r1(y)}" x2="${W - R}" y2="${r1(y)}" stroke="${i ? C.grid : C.line}" stroke-width="${i ? 1.5 : 2.5}"/>`;
      g += text(L - 10, y, fmt(v), { size: 15, anchor: "end", fill: "#475569" });
    }
    g += `<line x1="${L}" y1="${T - 6}" x2="${L}" y2="${H - B}" stroke="${C.line}" stroke-width="2.5"/>`;
    if (f.birim) g += `<text x="18" y="${r1((T + H - B) / 2)}" font-family="${FONT}" font-size="15" fill="#475569" text-anchor="middle" transform="rotate(-90 18 ${r1((T + H - B) / 2)})">${x(f.birim)}</text>`;
    const slot = (W - L - R) / bars.length, bw = Math.min(56, slot * 0.6);
    bars.forEach((b, i) => {
      const cx = L + slot * i + slot / 2, y = py(b.v);
      g += `<rect x="${r1(cx - bw / 2)}" y="${r1(y)}" width="${r1(bw)}" height="${r1(H - B - y)}" rx="4" fill="${C.shade}"/>`;
      g += text(cx, y - 12, fmt(b.v), { size: 15, bold: true });
      const label = b.ad.length > 12 ? b.ad.slice(0, 11) + "…" : b.ad;
      g += text(cx, H - B + 22, label, { size: 15 });
    });
    return wrap(W, H, g);
  }

  /* ---------- Tablo ---------- */
  function tablo(f) {
    const head = (f.basliklar || []).slice(0, 6).map(String);
    const rows = (f.satirlar || []).slice(0, 8).map((r) => (r || []).slice(0, 6).map(String));
    const cols = Math.max(head.length, ...rows.map((r) => r.length), 0);
    if (!cols) return "";
    const widths = [];
    for (let c = 0; c < cols; c++) {
      const longest = Math.max(String(head[c] || "").length, ...rows.map((r) => String(r[c] || "").length));
      widths.push(Math.min(220, Math.max(70, longest * 10.5 + 28)));
    }
    const rh = 40, W = widths.reduce((s, w) => s + w, 0) + 2, H = rh * (rows.length + (head.length ? 1 : 0)) + 2;
    let g = "", y = 1;
    const row = (cells, bg, bold) => {
      let xx = 1, out = `<rect x="1" y="${y}" width="${W - 2}" height="${rh}" fill="${bg}"/>`;
      for (let c = 0; c < cols; c++) {
        const t = String(cells[c] || "");
        out += text(xx + widths[c] / 2, y + rh / 2 + 1, t, { size: 17, bold, fill: t === "?" ? C.accentInk : C.ink });
        xx += widths[c];
      }
      y += rh;
      return out;
    };
    if (head.length) g += row(head, C.head, true);
    rows.forEach((r, i) => { g += row(r, i % 2 ? C.zebra : "#ffffff", false); });
    let xx = 1;
    for (let c = 0; c < cols - 1; c++) { xx += widths[c]; g += `<line x1="${xx}" y1="1" x2="${xx}" y2="${H - 1}" stroke="${C.soft}" stroke-width="1.5"/>`; }
    for (let i = 1; i < rows.length + (head.length ? 1 : 0); i++) g += `<line x1="1" y1="${1 + i * rh}" x2="${W - 1}" y2="${1 + i * rh}" stroke="${C.soft}" stroke-width="1.5"/>`;
    g += `<rect x="1" y="1" width="${W - 2}" height="${H - 2}" fill="none" stroke="${C.line}" stroke-width="2.5" rx="6"/>`;
    return wrap(W, H, g);
  }

  /* ---------- Saat ---------- */
  function saat(f) {
    const h = int(f.saat, 0, 23, 3) % 12, m = int(f.dakika, 0, 59, 0);
    const S = 260, c = S / 2, R = 112;
    let g = `<circle cx="${c}" cy="${c}" r="${R}" fill="#ffffff" stroke="${C.line}" stroke-width="5"/>`;
    for (let i = 0; i < 60; i++) {
      const t = (i * Math.PI) / 30, big = i % 5 === 0, r0 = big ? R - 14 : R - 7;
      g += `<line x1="${r1(c + r0 * Math.sin(t))}" y1="${r1(c - r0 * Math.cos(t))}" x2="${r1(c + (R - 3) * Math.sin(t))}" y2="${r1(c - (R - 3) * Math.cos(t))}" stroke="${big ? C.line : C.soft}" stroke-width="${big ? 3 : 1.5}"/>`;
    }
    for (let i = 1; i <= 12; i++) {
      const t = (i * Math.PI) / 6;
      g += text(c + (R - 32) * Math.sin(t), c - (R - 32) * Math.cos(t) + 1, i, { size: 20, bold: true });
    }
    const ha = ((h + m / 60) * Math.PI) / 6, ma = (m * Math.PI) / 30;
    g += `<line x1="${c}" y1="${c}" x2="${r1(c + 55 * Math.sin(ha))}" y2="${r1(c - 55 * Math.cos(ha))}" stroke="${C.ink}" stroke-width="8" stroke-linecap="round"/>`;
    g += `<line x1="${c}" y1="${c}" x2="${r1(c + 85 * Math.sin(ma))}" y2="${r1(c - 85 * Math.cos(ma))}" stroke="${C.shade}" stroke-width="5" stroke-linecap="round"/>`;
    g += `<circle cx="${c}" cy="${c}" r="7" fill="${C.ink}"/>`;
    return wrap(S, S, g);
  }

  /* ---------- Geometrik şekiller ---------- */
  const SHAPES = {
    kare: [[0, 0], [1, 0], [1, 1], [0, 1]],
    dikdortgen: [[0, 0], [1.7, 0], [1.7, 1], [0, 1]],
    ucgen: [[0.5, 0], [1, 0.9], [0, 0.9]],
    dik_ucgen: [[0, 0], [0, 1], [1.4, 1]],
    paralelkenar: [[0.4, 0], [1.9, 0], [1.5, 1], [0, 1]],
    yamuk: [[0.4, 0], [1.3, 0], [1.7, 1], [0, 1]],
    besgen: null,
    altigen: null,
  };

  function regular(n) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const t = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      pts.push([0.5 + 0.5 * Math.cos(t), 0.5 + 0.5 * Math.sin(t)]);
    }
    return pts;
  }

  function geometri(f) {
    const labels = (f.kenar_yazilari || []).map(String);
    const W = 460, H = 300;
    if (f.sekil === "daire") {
      const cx = W / 2, cy = H / 2, R = 110;
      let g = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="${C.fill}" stroke="${C.line}" stroke-width="3"/>`;
      g += `<circle cx="${cx}" cy="${cy}" r="4.5" fill="${C.ink}"/>`;
      if (labels[0]) {
        g += `<line x1="${cx}" y1="${cy}" x2="${cx + R}" y2="${cy}" stroke="${C.line}" stroke-width="2.5" stroke-dasharray="7 5"/>`;
        g += text(cx + R / 2, cy - 16, labels[0], { size: 19, bold: true });
      }
      if (f.ic_yazi) g += text(cx, cy + 34, f.ic_yazi, { size: 18 });
      return wrap(W, H, g);
    }
    let pts = SHAPES[f.sekil];
    if (f.sekil === "besgen") pts = regular(5);
    if (f.sekil === "altigen") pts = regular(6);
    if (!pts) return "";
    const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
    const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
    const scale = Math.min((W - 140) / (maxX - minX), (H - 110) / (maxY - minY));
    const ox = (W - (maxX - minX) * scale) / 2, oy = (H - (maxY - minY) * scale) / 2;
    const P = pts.map((p) => [ox + (p[0] - minX) * scale, oy + (p[1] - minY) * scale]);
    const cx = P.reduce((s, p) => s + p[0], 0) / P.length, cy = P.reduce((s, p) => s + p[1], 0) / P.length;
    let g = `<polygon points="${P.map((p) => r1(p[0]) + "," + r1(p[1])).join(" ")}" fill="${C.fill}" stroke="${C.line}" stroke-width="3" stroke-linejoin="round"/>`;
    if (f.sekil === "dik_ucgen") {
      const [vx, vy] = P[1], k = 18;
      g += `<path d="M${r1(vx)},${r1(vy - k)} L${r1(vx + k)},${r1(vy - k)} L${r1(vx + k)},${r1(vy)}" fill="none" stroke="${C.line}" stroke-width="2"/>`;
    }
    if (f.sekil === "kare" || f.sekil === "dikdortgen") {
      for (const [vx, vy] of P) {
        const sx = vx < cx ? 1 : -1, sy = vy < cy ? 1 : -1, k = 14;
        g += `<path d="M${r1(vx + sx * k)},${r1(vy)} L${r1(vx + sx * k)},${r1(vy + sy * k)} L${r1(vx)},${r1(vy + sy * k)}" fill="none" stroke="${C.soft}" stroke-width="1.8"/>`;
      }
    }
    P.forEach((p, i) => {
      const q = P[(i + 1) % P.length];
      const label = labels[i];
      if (!label) return;
      const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
      let nx = -(q[1] - p[1]), ny = q[0] - p[0];
      const len = Math.hypot(nx, ny) || 1;
      nx /= len; ny /= len;
      if ((mx - cx) * nx + (my - cy) * ny < 0) { nx = -nx; ny = -ny; }
      g += text(mx + nx * 26, my + ny * 26, label, { size: 19, bold: true, fill: label === "?" ? C.accentInk : C.ink });
    });
    if (f.ic_yazi) g += text(cx, cy, f.ic_yazi, { size: 18 });
    return wrap(W, H, g);
  }

  /* ---------- Açı ---------- */
  function aci(f) {
    const d = Math.max(1, Math.min(359, num(f.derece, 60)));
    const W = 420, H = 280, M = 24;
    const vx = d > 90 ? W / 2 : 80, vy = d > 180 ? H / 2 : H - 50;
    const t = (-d * Math.PI) / 180;
    // Her iki kol da çerçeveye sığsın
    const fit = (cx, sy) => {
      let l = 240;
      if (cx > 1e-6) l = Math.min(l, (W - M - vx) / cx);
      if (cx < -1e-6) l = Math.min(l, (vx - M) / -cx);
      if (sy > 1e-6) l = Math.min(l, (H - M - vy) / sy);
      if (sy < -1e-6) l = Math.min(l, (vy - M) / -sy);
      return l;
    };
    const L = Math.max(90, Math.min(fit(1, 0), fit(Math.cos(t), Math.sin(t))));
    const ex = vx + L * Math.cos(t), ey = vy + L * Math.sin(t);
    const r = 50, ax = vx + r * Math.cos(t), ay = vy + r * Math.sin(t);
    let g = `<line x1="${vx}" y1="${vy}" x2="${vx + L}" y2="${vy}" stroke="${C.line}" stroke-width="3.5" stroke-linecap="round"/>`;
    g += `<line x1="${vx}" y1="${vy}" x2="${r1(ex)}" y2="${r1(ey)}" stroke="${C.line}" stroke-width="3.5" stroke-linecap="round"/>`;
    if (Math.abs(d - 90) < 0.01) {
      g += `<path d="M${vx + 26},${vy} L${vx + 26},${vy - 26} L${vx},${vy - 26}" fill="${C.fill}" stroke="${C.shade}" stroke-width="2.5"/>`;
    } else {
      g += `<path d="M${vx + r},${vy} A${r},${r} 0 ${d > 180 ? 1 : 0} 0 ${r1(ax)},${r1(ay)}" fill="none" stroke="${C.shade}" stroke-width="3"/>`;
    }
    const mid = t / 2, lr = d < 40 ? r + 60 : r + 30;
    const label = f.yazi || fmt(d) + "°";
    g += text(vx + lr * Math.cos(mid), vy + lr * Math.sin(mid), label, { size: 20, bold: true, fill: label === "?" ? C.accentInk : C.ink });
    g += `<circle cx="${vx}" cy="${vy}" r="4.5" fill="${C.ink}"/>`;
    return wrap(W, H, g);
  }

  /* ---------- Kareli alan ---------- */
  function kareliAlan(f) {
    const rows = int(f.satir, 1, 12, 4), cols = int(f.sutun, 1, 16, 6);
    const cell = Math.min(36, Math.floor(480 / cols), Math.floor(300 / rows));
    const W = cols * cell + 20, H = rows * cell + 20;
    const shaded = new Set((f.boyali || []).map((p) => (p && p.length >= 2 ? `${int(p[0], 0, rows - 1, 0)},${int(p[1], 0, cols - 1, 0)}` : "")));
    let g = "";
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      g += `<rect x="${10 + c * cell}" y="${10 + r * cell}" width="${cell}" height="${cell}" fill="${shaded.has(`${r},${c}`) ? C.shade2 : "#ffffff"}" stroke="${C.soft}" stroke-width="1.5"/>`;
    }
    g += `<rect x="10" y="10" width="${cols * cell}" height="${rows * cell}" fill="none" stroke="${C.line}" stroke-width="2.5"/>`;
    return wrap(W, H, g);
  }

  /* ---------- Örüntü ---------- */
  function oruntu(f) {
    const items = (f.ogeler || []).slice(0, 10).map(String);
    if (!items.length) return "";
    const box = Math.max(64, Math.min(96, Math.max(...items.map((s) => s.length)) * 14 + 30));
    const gap = 16, W = items.length * (box + gap) - gap + 30, H = box + 40;
    let g = "";
    items.forEach((s, i) => {
      const x0 = 15 + i * (box + gap), q = s.trim() === "?";
      g += `<rect x="${x0}" y="20" width="${box}" height="${box}" rx="12" fill="${q ? "#fff7e6" : C.fill}" stroke="${q ? C.accent : C.shade}" stroke-width="3" ${q ? 'stroke-dasharray="8 6"' : ""}/>`;
      g += text(x0 + box / 2, 20 + box / 2 + 2, s, { size: s.length > 3 ? 22 : 30, bold: true, fill: q ? C.accentInk : C.ink });
    });
    return wrap(W, H, g);
  }

  const RENDER = {
    sayi_dogrusu: sayiDogrusu,
    kesir,
    sutun_grafik: sutunGrafik,
    tablo,
    saat,
    geometri,
    aci,
    kareli_alan: kareliAlan,
    oruntu,
  };

  /** Görsel tarifini SVG'ye çevirir. Geçersizse boş metin döner. */
  function render(spec) {
    if (!spec || typeof spec !== "object") return "";
    const fn = RENDER[spec.tur];
    if (!fn) return "";
    try { return fn(spec) || ""; } catch (e) { return ""; }
  }

  /* ---------- Yapay zekâ için JSON şeması ---------- */
  const S = { type: "string" }, N = { type: "number" }, I = { type: "integer" }, B = { type: "boolean" };
  const arr = (items) => ({ type: "array", items });
  const o = (props) => ({ type: "object", additionalProperties: false, required: Object.keys(props), properties: props });
  const kind = (tur, props, description) => ({ ...o({ tur: { type: "string", enum: [tur] }, ...props }), description });

  const SCHEMA = {
    anyOf: [
      { type: "null" },
      kind("sayi_dogrusu", {
        baslangic: N, bitis: N, adim: N, sayilari_goster: B,
        isaretler: arr(o({ deger: N, yazi: S })),
      }, "Sayı doğrusu. isaretler: doğru üzerinde turuncu noktayla gösterilecek değerler ve üstlerindeki yazı (ör. 'A', '?')."),
      kind("kesir", {
        modeller: arr(o({ sekil: { type: "string", enum: ["dikdortgen", "daire"] }, parca: I, boyali: I, yazi: S })),
      }, "Bir veya birkaç kesir modeli (en fazla 4). Her model eş parçalara bölünür, ilk 'boyali' kadar parça boyanır; yazi modelin altında görünür (ör. 'A', 'B' veya boş)."),
      kind("sutun_grafik", {
        baslik: S, birim: S, cubuklar: arr(o({ ad: S, deger: N })),
      }, "Sütun grafiği (en fazla 8 sütun)."),
      kind("tablo", {
        basliklar: arr(S), satirlar: arr(arr(S)),
      }, "Tablo (en fazla 6 sütun, 8 satır). Bilinmeyen hücreye '?' yaz."),
      kind("saat", { saat: I, dakika: I }, "Akrep ve yelkovanlı analog saat."),
      kind("geometri", {
        sekil: { type: "string", enum: ["kare", "dikdortgen", "ucgen", "dik_ucgen", "paralelkenar", "yamuk", "besgen", "altigen", "daire"] },
        kenar_yazilari: arr(S), ic_yazi: S,
      }, "Geometrik şekil. kenar_yazilari kenarların dışına sırayla yazılır (üst kenardan başlayıp saat yönünde; dik üçgende sol dik kenar, alt dik kenar, hipotenüs; dairede yalnızca yarıçap). Bilinmeyen kenara '?' yaz, yazı istemediğin kenara boş metin."),
      kind("aci", { derece: N, yazi: S }, "Açı çizimi. yazi boşsa derece yazılır; bilinmeyen açı için '?' yaz."),
      kind("kareli_alan", {
        satir: I, sutun: I, boyali: arr(arr(I)),
      }, "Birim karelerden oluşan ızgara; boyali [satır, sütun] çiftleri (0'dan başlar). Alan ve çevre soruları için."),
      kind("oruntu", { ogeler: arr(S) }, "Kutular içinde sıralı öğeler (sayı, harf veya emoji). Bilinmeyen öğe için '?' yaz."),
    ],
  };

  return { render, SCHEMA };
})();
