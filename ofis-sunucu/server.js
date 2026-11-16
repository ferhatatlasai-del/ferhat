'use strict';
// Ajan Ofisi sunucusu. Bağımlılık yok (Node 22). GitHub anahtarı yalnızca burada, Fly gizli anahtarı olarak durur.
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = +process.env.PORT || 3000;
const REPO = process.env.GH_REPO || 'ferhatatlasai-del/ferhat';
const TOKEN = process.env.GITHUB_TOKEN || '';
const SIFRE = process.env.PANEL_SIFRE || '';
const AKIS = 'icerik-direktif.yml';
const PUBLIC = path.join(__dirname, 'public');
const TURLER = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

function sifreDogru(girilen) {
  if (!SIFRE || typeof girilen !== 'string') return false;
  const a = crypto.createHash('sha256').update(girilen).digest();
  const b = crypto.createHash('sha256').update(SIFRE).digest();
  return crypto.timingSafeEqual(a, b);
}

// Çok basit hız sınırı: yanlış şifre ve direktif için IP başına
const yanlis = new Map(), direktifler = [];
function ip(req) { return (req.headers['fly-client-ip'] || req.socket.remoteAddress || '?'); }
function kilitliMi(req) { const k = yanlis.get(ip(req)); return k && k.n >= 8 && Date.now() - k.t < 15 * 60e3; }
function yanlisKaydet(req) { const k = yanlis.get(ip(req)) || { n: 0, t: 0 }; k.n = Date.now() - k.t > 15 * 60e3 ? 1 : k.n + 1; k.t = Date.now(); yanlis.set(ip(req), k); }

async function gh(yol, secenek = {}) {
  const r = await fetch('https://api.github.com' + yol, {
    ...secenek,
    headers: { Authorization: 'Bearer ' + TOKEN, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'ajan-ofisi', ...(secenek.headers || {}) },
  });
  return r;
}

function json(res, kod, nesne) {
  res.writeHead(kod, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(nesne));
}
function govde(req) {
  return new Promise((ok, hata) => {
    let d = ''; req.on('data', c => { d += c; if (d.length > 8000) { hata(new Error('büyük')); req.destroy(); } });
    req.on('end', () => { try { ok(JSON.parse(d || '{}')); } catch (e) { hata(e); } });
  });
}

async function varsayilanDal() { const r = await gh(`/repos/${REPO}`); const j = await r.json(); return j.default_branch; }

async function api(req, res, url) {
  if (url.pathname === '/api/ping') return json(res, 200, { ok: true, hazir: !!(TOKEN && SIFRE) });
  if (!TOKEN || !SIFRE) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN ya da PANEL_SIFRE tanımlı değil.' });
  if (kilitliMi(req)) return json(res, 429, { hata: 'Çok fazla yanlış deneme. 15 dakika sonra tekrar dene.' });
  if (!sifreDogru(req.headers['x-sifre'])) { yanlisKaydet(req); return json(res, 401, { hata: 'Şifre yanlış.' }); }

  if (url.pathname === '/api/direktif' && req.method === 'POST') {
    const simdi = Date.now();
    while (direktifler.length && simdi - direktifler[0] > 3600e3) direktifler.shift();
    if (direktifler.length >= 12) return json(res, 429, { hata: 'Saatte en fazla 12 direktif.' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const metin = String(b.metin || '').replace(/\s+/g, ' ').trim().slice(0, 500);
    if (metin.length < 3) return json(res, 400, { hata: 'Direktif çok kısa.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { direktif: metin } }) });
    if (r.status !== 204) { const t = await r.text(); return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').', ayrinti: t.slice(0, 200) }); }
    direktifler.push(simdi);
    return json(res, 200, { ok: true, baslangic: new Date(simdi - 5000).toISOString() });
  }

  if (url.pathname === '/api/durum') {
    const since = Date.parse(url.searchParams.get('since') || '') || 0;
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS}/runs?per_page=5&event=workflow_dispatch`);
    if (!r.ok) return json(res, 502, { hata: 'GitHub okunamadı (' + r.status + ').' });
    const j = await r.json();
    const run = (j.workflow_runs || []).find(x => Date.parse(x.created_at) >= since);
    if (!run) return json(res, 200, { durum: 'bekliyor' });
    return json(res, 200, { durum: run.status, sonuc: run.conclusion, adres: run.html_url, baslangic: run.created_at });
  }

  if (url.pathname === '/api/taslak') {
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/contents/taslaklar?ref=${encodeURIComponent(dal)}`);
    if (!r.ok) return json(res, 502, { hata: 'Taslaklar okunamadı.' });
    const liste = (await r.json()).filter(f => f.name.endsWith('.md')).sort((a, b) => a.name < b.name ? -1 : 1);
    const dir = liste.filter(f => f.name.includes('_direktif_')).pop() || liste.pop();
    if (!dir) return json(res, 404, { hata: 'Taslak yok.' });
    const d = await (await gh(`/repos/${REPO}/contents/${dir.path}?ref=${encodeURIComponent(dal)}`)).json();
    const metin = Buffer.from(d.content || '', 'base64').toString('utf8');
    const baslik = (metin.match(/^# (.+)$/m) || [])[1] || dir.name;
    return json(res, 200, { ad: dir.name, baslik, icerik: metin.slice(0, 6000), adres: dir.html_url });
  }
  return json(res, 404, { hata: 'Yok.' });
}

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://x');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    if (url.pathname.startsWith('/api/')) return await api(req, res, url);
    let dosya = path.normalize(path.join(PUBLIC, url.pathname === '/' ? 'index.html' : url.pathname));
    if (!dosya.startsWith(PUBLIC)) { res.writeHead(403); return res.end(); }
    fs.readFile(dosya, (e, d) => {
      if (e) { res.writeHead(404); return res.end('Bulunamadı'); }
      res.writeHead(200, { 'Content-Type': TURLER[path.extname(dosya)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
      res.end(d);
    });
  } catch (e) { json(res, 500, { hata: 'Sunucu hatası.' }); }
}).listen(PORT, () => console.log('Ajan ofisi dinliyor: ' + PORT));
