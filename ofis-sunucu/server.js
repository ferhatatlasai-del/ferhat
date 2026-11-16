'use strict';
// Ajan Ofisi sunucusu. Bağımlılık yok (Node 22). GitHub anahtarı yalnızca burada, Fly gizli anahtarı olarak durur.
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = +process.env.PORT || 3000;
const REPO = process.env.GH_REPO || 'ferhatatlasai-del/ferhat';
// Anahtarın başındaki/sonundaki boşluk, satır sonu ve tırnakları temizle (komut satırından gelebiliyor)
const TOKEN = (process.env.GITHUB_TOKEN || '').trim().replace(/^["']+|["']+$/g, '').trim();
const SIFRE = process.env.PANEL_SIFRE || '';
const AKIS = 'icerik-direktif.yml';
const AKIS_IG = 'yayinla.yml';
const AKIS_YT = 'youtube-yukle.yml';
const GH_API = process.env.GH_API || 'https://api.github.com';
const MAX_VIDEO = 30 * 1024 * 1024;
const YZ_SATIRI = '🤖 Doktor Filament yapay zekâ ile üretilmiş bir karakterdir.';
const PUBLIC = path.join(__dirname, 'public');
const TURLER = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

function sifreDogru(girilen) {
  if (!SIFRE || typeof girilen !== 'string') return false;
  const a = crypto.createHash('sha256').update(girilen).digest();
  const b = crypto.createHash('sha256').update(SIFRE).digest();
  return crypto.timingSafeEqual(a, b);
}

// Çok basit hız sınırı: yanlış şifre ve direktif için IP başına
const yanlis = new Map(), direktifler = [], yayinlar = [], linkler = new Map();
function ip(req) { return (req.headers['fly-client-ip'] || req.socket.remoteAddress || '?'); }
function kilitliMi(req) { const k = yanlis.get(ip(req)); return k && k.n >= 8 && Date.now() - k.t < 15 * 60e3; }
function yanlisKaydet(req) { const k = yanlis.get(ip(req)) || { n: 0, t: 0 }; k.n = Date.now() - k.t > 15 * 60e3 ? 1 : k.n + 1; k.t = Date.now(); yanlis.set(ip(req), k); }

async function gh(yol, secenek = {}) {
  const r = await fetch(GH_API + yol, {
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

function govdeIkili(req, limit) {
  return new Promise((ok, hata) => {
    const parcalar = []; let n = 0;
    req.on('data', c => { n += c.length; if (n > limit) { hata(new Error('buyuk')); req.destroy(); return; } parcalar.push(c); });
    req.on('end', () => ok(Buffer.concat(parcalar)));
    req.on('error', hata);
  });
}

async function dosyaYaz(yol, icerik, mesaj, dal) {
  const r = await gh(`/repos/${REPO}/contents/${yol}`, { method: 'PUT', body: JSON.stringify({ message: mesaj, content: Buffer.from(icerik).toString('base64'), branch: dal }) });
  if (!r.ok) { const t = await r.text(); const e = new Error('GitHub dosyayı kaydetmedi (' + r.status + '). ' + t.slice(0, 120)); e.kullanici = true; throw e; }
}

function damga() { return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14); }
function temiz(s, max) { return String(s || '').replace(/\r/g, '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim().slice(0, max); }
function yzEkle(metin) {
  if (metin.includes(YZ_SATIRI)) return metin;
  const satirlar = metin.split('\n'); const i = satirlar.findIndex(l => l.trim().startsWith('#'));
  if (i < 0) satirlar.push('', YZ_SATIRI); else satirlar.splice(i, 0, YZ_SATIRI, '');
  return satirlar.join('\n');
}
async function calismaLinki(run) {
  if (linkler.has(run.id)) return linkler.get(run.id);
  try {
    const jr = await gh(`/repos/${REPO}/actions/runs/${run.id}/jobs`); const job = ((await jr.json()).jobs || [])[0];
    if (!job) return '';
    const lr = await gh(`/repos/${REPO}/actions/jobs/${job.id}/logs`); const t = await lr.text();
    const m = t.match(/https:\/\/www\.(?:instagram|youtube)\.com\/[^\s"'<>]+/);
    const link = m ? m[0] : ''; if (link) linkler.set(run.id, link); return link;
  } catch (e) { return ''; }
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

  if (url.pathname === '/api/video-yukle' && req.method === 'POST') {
    if (+req.headers['content-length'] > MAX_VIDEO) return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' });
    let tampon; try { tampon = await govdeIkili(req, MAX_VIDEO); } catch (e) { return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' }); }
    if (tampon.length < 1024 || tampon.slice(4, 8).toString('latin1') !== 'ftyp') return json(res, 400, { hata: 'Bu bir MP4 video dosyası gibi görünmüyor.' });
    const dal = await varsayilanDal();
    const yol = `videolar/yukleme_${damga()}.mp4`;
    try { await dosyaYaz(yol, tampon, 'Panelden video yüklendi', dal); } catch (e) { return json(res, 502, { hata: e.kullanici ? e.message : 'Video kaydedilemedi.' }); }
    return json(res, 200, { ok: true, yol, boyut: tampon.length });
  }

  if (url.pathname === '/api/yayinla' && req.method === 'POST') {
    const simdi = Date.now();
    while (yayinlar.length && simdi - yayinlar[0] > 3600e3) yayinlar.shift();
    if (yayinlar.length >= 6) return json(res, 429, { hata: 'Saatte en fazla 6 yayın başlatılabilir.' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    if (b.onay !== true) return json(res, 400, { hata: 'Onay verilmedi.' });
    if (!/^videolar\/yukleme_\d{14}\.mp4$/.test(String(b.yol || ''))) return json(res, 400, { hata: 'Geçersiz video yolu.' });
    const hedefler = Array.isArray(b.hedefler) ? b.hedefler.filter(h => h === 'instagram' || h === 'youtube') : [];
    if (!hedefler.length) return json(res, 400, { hata: 'En az bir platform seç.' });
    const baslik = temiz(b.baslik, 100), aciklama = temiz(b.aciklama, 2000);
    if (baslik.length < 3) return json(res, 400, { hata: 'Başlık çok kısa.' });
    if (aciklama.length < 3) return json(res, 400, { hata: 'Açıklama çok kısa.' });
    const dal = await varsayilanDal();
    const ad = b.yol.slice('videolar/'.length, -4);
    const metin = yzEkle(aciklama);
    const igDosya = `yayin/${ad}_instagram.txt`, ytDosya = `yayin/${ad}_youtube.txt`;
    try {
      if (hedefler.includes('instagram')) await dosyaYaz(igDosya, metin + '\n', 'Panelden Instagram metni', dal);
      if (hedefler.includes('youtube')) await dosyaYaz(ytDosya, baslik + '\n' + (/#shorts/i.test(metin) ? metin : metin + '\n\n#Shorts') + '\n', 'Panelden YouTube metni', dal);
    } catch (e) { return json(res, 502, { hata: e.kullanici ? e.message : 'Metin kaydedilemedi.' }); }
    await new Promise(r => setTimeout(r, 2500));
    const baslangic = new Date(Date.now() - 5000).toISOString();
    const sonuc = {};
    for (const h of hedefler) {
      const ak = h === 'instagram' ? AKIS_IG : AKIS_YT;
      const inputs = h === 'instagram' ? { video: b.yol, aciklama: igDosya, onay: 'EVET' } : { video: b.yol, metin: ytDosya, gizlilik: 'public', onay: 'EVET' };
      const r = await gh(`/repos/${REPO}/actions/workflows/${ak}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs }) });
      sonuc[h] = r.status === 204 ? 'basladi' : 'GitHub kabul etmedi (' + r.status + ')';
    }
    yayinlar.push(simdi);
    return json(res, 200, { ok: true, baslangic, sonuc });
  }

  if (url.pathname === '/api/yayin-durum') {
    const since = Date.parse(url.searchParams.get('since') || '') || 0;
    const cikti = {};
    for (const [ad, ak] of [['instagram', AKIS_IG], ['youtube', AKIS_YT]]) {
      const r = await gh(`/repos/${REPO}/actions/workflows/${ak}/runs?per_page=5&event=workflow_dispatch`);
      if (!r.ok) { cikti[ad] = { durum: 'okunamadi' }; continue; }
      const run = ((await r.json()).workflow_runs || []).find(x => Date.parse(x.created_at) >= since);
      if (!run) { cikti[ad] = { durum: 'bekliyor' }; continue; }
      const o = { durum: run.status, sonuc: run.conclusion, adres: run.html_url };
      if (run.status === 'completed' && run.conclusion === 'success') o.link = await calismaLinki(run);
      cikti[ad] = o;
    }
    return json(res, 200, cikti);
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
  } catch (e) {
    const m = String((e && e.message) || e);
    const guvenli = TOKEN ? m.split(TOKEN).join('***') : m;
    console.error('hata:', e && e.name, guvenli.slice(0, 300));
    const gecersiz = /invalid header|ERR_INVALID_CHAR/i.test(m);
    json(res, 500, { hata: gecersiz ? 'GitHub anahtarında geçersiz karakter var. Anahtarı yeniden kaydet.' : 'Sunucu hatası (' + ((e && e.name) || '?') + ').' });
  }
}).listen(PORT, () => console.log('Ajan ofisi dinliyor: ' + PORT));
