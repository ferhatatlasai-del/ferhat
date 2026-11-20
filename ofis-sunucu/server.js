'use strict';
// Ajan Ofisi sunucusu. Bağımlılık yok (Node 22). GitHub anahtarı yalnızca burada, Fly gizli anahtarı olarak durur.
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

let webpush = null;
try { webpush = require('web-push'); } catch (e) { console.error('web-push yüklü değil, bildirim kapalı'); }
const VAPID_PUB = (process.env.VAPID_PUBLIC_KEY || '').trim();
const VAPID_PRIV = (process.env.VAPID_PRIVATE_KEY || '').trim();
const BILDIRIM_SIRRI = (process.env.BILDIRIM_SIRRI || '').trim();
const VAPID_KONU = process.env.VAPID_KONU || 'https://gurtechs-ajan-ofisi.fly.dev';
const BILDIRIM_ACIK = !!(webpush && VAPID_PUB && VAPID_PRIV && BILDIRIM_SIRRI);
if (BILDIRIM_ACIK) webpush.setVapidDetails(VAPID_KONU, VAPID_PUB, VAPID_PRIV);
const BILDIRIM_KURU = !!process.env.BILDIRIM_KURU;   // yalnızca test: gerçek gönderim yerine kaydeder
const kuruKayit = [];
const PORT = +process.env.PORT || 3000;
const REPO = process.env.GH_REPO || 'ferhatatlasai-del/ferhat';
// Anahtarın başındaki/sonundaki boşluk, satır sonu ve tırnakları temizle (komut satırından gelebiliyor)
const TOKEN = (process.env.GITHUB_TOKEN || '').trim().replace(/^["']+|["']+$/g, '').trim();
const SIFRE = process.env.PANEL_SIFRE || '';
const AKIS = 'zincir.yml';   // "İçerik üret" zinciri: trend -> içerik ajanı -> video paketi
const ZINCIR_ADIMLARI = ['Trend kontrolü', 'İçerik ajanı', 'Video paketi', 'Kaydet'];
const KAYIT_RE = /^[cy]\d{8}-\d{6}$/;
const AKIS_IG = 'yayinla.yml';
const AKIS_YT = 'youtube-yukle.yml';
// Ajan kimliği -> iş akışı dosyası (panel durumu buradan okunur)
const AKIS_HIKAYE = 'hikaye-yayinla.yml';
const AKIS_URETIM = 'hikaye-uret.yml';
const AKIS_AKADEMI = 'akademi.yml';
const AKIS_KISA = 'kisa-video.yml';
const AKIS_VIRAL = 'viral-video.yml';
const AKIS_TREND = 'trend.yml';
const AKIS_ISTATISTIK = 'istatistik-rapor.yml';
const SHORTS_RE = /^s\d{8}-\d{6}$/;
const AKADEMI_RE = /^o\d{8}-\d+$/;
const HIKAYE_RE = /^h\d{8}-\d{6}-[a-z0-9]{3}$/;
const AJAN_AKISLARI = { hikaye: 'hikaye-yayinla.yml', icerik: ['gunluk-taslak.yml', 'zincir.yml'], istatistik: 'istatistik-rapor.yml', instagram: 'yayinla.yml', youtube: 'youtube-yukle.yml', gorsel: 'zincir.yml', trend: 'trend.yml' };
let ajanOnbellek = { t: 0, veri: null };
let trendOnbellek = { t: 0, veri: null };
let zincirOnbellek = { t: 0, veri: null };
let hikayeOnbellek = { t: 0, veri: null };
const hikayeTetikler = [], uretimTetikler = [], akademiTetikler = [], kisaTetikler = [], viralTetikler = [], trendTetikler = [], istatistikTetikler = [], bildirimler = [];
const guncellenenler = new Set();
const GH_API = process.env.GH_API || 'https://api.github.com';
const MAX_VIDEO = 30 * 1024 * 1024;
const YZ_SATIRI = '🤖 Doktor Filament yapay zekâ ile üretilmiş bir karakterdir.';
const PUBLIC = path.join(__dirname, 'public');
const TURLER = { '.html': 'text/html; charset=utf-8', '.webmanifest': 'application/manifest+json', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

function sifreDogru(girilen) {
  if (!SIFRE || typeof girilen !== 'string') return false;
  const a = crypto.createHash('sha256').update(girilen).digest();
  const b = crypto.createHash('sha256').update(SIFRE).digest();
  return crypto.timingSafeEqual(a, b);
}

// Çok basit hız sınırı: yanlış şifre ve direktif için IP başına
const yanlis = new Map(), direktifler = [], yayinlar = [], linkler = new Map();
const videoIzi = new Map();      // yüklenen video yolu -> içerik özeti (aynı videonun iki kez yayınlanmasını önler)
const sonYayinlar = new Map();   // içerik özeti ya da yol -> { hedef: zaman }
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
    if (!job) return null;
    const lr = await gh(`/repos/${REPO}/actions/jobs/${job.id}/logs`); const t = await lr.text();
    const m = t.match(/https:\/\/www\.(?:instagram|youtube)\.com\/[^\s"'<>]+/);
    const k = t.match(/(?:Medya kimliği|Video kimliği):\s*([\w-]+)/);
    const sonuc = m ? { link: m[0], medya: k ? k[1] : '' } : null;
    if (sonuc) linkler.set(run.id, sonuc); return sonuc;
  } catch (e) { return null; }
}

function bekle(ms) { return new Promise(r => setTimeout(r, ms)); }

// ---- Genel depo okuma/yazma/silme (contents API) ----
async function depoOku(yol) {
  const dal = await varsayilanDal();
  const r = await gh(`/repos/${REPO}/contents/${yol}?ref=${encodeURIComponent(dal)}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error('okunamadı: ' + yol);
  const d = await r.json();
  return { sha: d.sha, metin: Buffer.from(d.content || '', 'base64').toString('utf8') };
}
async function depoYaz(yol, icerik, sha, mesaj) {
  const dal = await varsayilanDal();
  const govde = { message: mesaj, content: Buffer.from(icerik).toString('base64'), branch: dal };
  if (sha) govde.sha = sha;
  return gh(`/repos/${REPO}/contents/${yol}`, { method: 'PUT', body: JSON.stringify(govde) });
}
async function depoSil(yol, sha, mesaj) {
  const dal = await varsayilanDal();
  return gh(`/repos/${REPO}/contents/${yol}`, { method: 'DELETE', body: JSON.stringify({ message: mesaj, sha, branch: dal }) });
}
// Çakışmada (409/422) yeniden dene; degistir(veri) false dönerse vazgeç
async function jsonGuncelle(yol, degistir, mesaj, varsayilan) {
  for (let i = 0; i < 3; i++) {
    const k = await depoOku(yol);
    const veri = k ? JSON.parse(k.metin) : JSON.parse(JSON.stringify(varsayilan || {}));
    if (degistir(veri) === false) return false;
    const r = await depoYaz(yol, JSON.stringify(veri, null, 2), k && k.sha, mesaj);
    if (r.ok) return true;
    if (r.status !== 409 && r.status !== 422) return false;
    await bekle(700);
  }
  return false;
}

// ---- Web push: abonelikler şifrelenerek depoda saklanır (makine kapanınca kaybolmasın) ----
function aboneAnahtari() { return Buffer.from(crypto.hkdfSync('sha256', Buffer.from(BILDIRIM_SIRRI), Buffer.from('ofis-bildirim-tuz'), Buffer.from('abonelikler'), 32)); }
function sifrele(nesne) {
  const iv = crypto.randomBytes(12), c = crypto.createCipheriv('aes-256-gcm', aboneAnahtari(), iv);
  const enc = Buffer.concat([c.update(JSON.stringify(nesne), 'utf8'), c.final()]);
  return Buffer.concat([iv, c.getAuthTag(), enc]).toString('base64');
}
function coz(b64) {
  const b = Buffer.from(b64.trim(), 'base64'), d = crypto.createDecipheriv('aes-256-gcm', aboneAnahtari(), b.subarray(0, 12));
  d.setAuthTag(b.subarray(12, 28));
  return JSON.parse(Buffer.concat([d.update(b.subarray(28)), d.final()]).toString('utf8'));
}
const ABONE_YOL = 'bildirim/abonelikler.enc';
async function aboneleriOku() {
  const k = await depoOku(ABONE_YOL);
  if (!k) return { sha: null, liste: [] };
  try { return { sha: k.sha, liste: coz(k.metin) }; } catch (e) { return { sha: k.sha, liste: [] }; }
}
async function aboneleriGuncelle(degistir, mesaj) {
  for (let i = 0; i < 3; i++) {
    const { sha, liste } = await aboneleriOku();
    const yeni = degistir(liste);
    const r = await depoYaz(ABONE_YOL, sifrele(yeni), sha, mesaj);
    if (r.ok) return yeni;
    if (r.status !== 409 && r.status !== 422) throw new Error('abonelik yazılamadı');
    await bekle(700);
  }
  throw new Error('abonelik yazılamadı');
}
function adresGuvenli(u) { return typeof u === 'string' && u.length <= 400 && (/^https:\/\//.test(u) || /^\/(?!\/)/.test(u)); }
async function bildirimGonder(yuk) {
  const { liste } = await aboneleriOku();
  const olu = []; let tamam = 0;
  const govde = JSON.stringify(yuk);
  for (const a of liste) {
    try {
      if (BILDIRIM_KURU) kuruKayit.push({ endpoint: a.endpoint.slice(0, 40), yuk });
      else await webpush.sendNotification(a, govde, { TTL: 3600, urgency: 'normal' });
      tamam++;
    } catch (e) { if (e.statusCode === 404 || e.statusCode === 410) olu.push(a.endpoint); else console.error('push hatası:', e.statusCode || e.message); }
  }
  if (olu.length) { try { await aboneleriGuncelle(l => l.filter(x => !olu.includes(x.endpoint)), 'Bildirim: geçersiz abonelikler silindi'); } catch (e) { /* sonraki sefer */ } }
  return { gonderilen: tamam, abone: liste.length };
}

// ---- Hikaye ----
function jpegBoyut(b) {
  if (b.length < 4 || b[0] !== 0xFF || b[1] !== 0xD8 || b[2] !== 0xFF) return null;
  let i = 2;
  while (i + 9 < b.length) {
    if (b[i] !== 0xFF) { i++; continue; }
    const m = b[i + 1];
    if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) return { y: b.readUInt16BE(i + 5), g: b.readUInt16BE(i + 7) };
    i += 2 + b.readUInt16BE(i + 2);
  }
  return null;
}
const URETIM_VARSAYILAN = { aktif: false, mod: 'otomatik', gunluk_uretim: 3, gunluk_gorsel_siniri: 6, aylik_gorsel_siniri: 90, kalite: 'low', kuyruk_hedefi: 6, referans: 'zorunlu', muzik: true };
async function hikayeListesi() {
  if (Date.now() - hikayeOnbellek.t < 20e3 && hikayeOnbellek.veri) return hikayeOnbellek.veri;
  const dal = await varsayilanDal();
  const ayarK = await depoOku('hikaye/ayar.json');
  const saglikK = await depoOku('hikaye/saglik.json').catch(() => null);
  const r = await gh(`/repos/${REPO}/contents/hikaye/kuyruk?ref=${encodeURIComponent(dal)}`);
  const adlar = r.ok ? (await r.json()).map(f => f.name).filter(n => /^h\d{8}-\d{6}-[a-z0-9]{3}\.json$/.test(n)).sort().reverse().slice(0, 40) : [];
  const kuyruk = (await Promise.all(adlar.map(a => depoOku('hikaye/kuyruk/' + a).then(k => k && JSON.parse(k.metin)).catch(() => null)))).filter(Boolean);
  const uretimK = await depoOku('hikaye/uretim.json').catch(() => null);
  const harcamaK = await depoOku('hikaye/harcama.json').catch(() => null);
  const uretim = Object.assign({}, URETIM_VARSAYILAN, uretimK ? JSON.parse(uretimK.metin) : {});
  const harcama = harcamaK ? JSON.parse(harcamaK.metin) : {};
  const trGun = new Date(Date.now() + 3 * 3600e3).toISOString();
  const harcamaOzet = { bugun: ((harcama.gunler || {})[trGun.slice(0, 10)] || {}).gorsel || 0, ay: ((harcama.aylar || {})[trGun.slice(0, 7)] || {}).gorsel || 0 };
  const veri = { depo: REPO, dal, ayar: ayarK ? JSON.parse(ayarK.metin) : null, kuyruk, saglik: saglikK ? JSON.parse(saglikK.metin) : null, bildirim: BILDIRIM_ACIK, uretim, harcama: harcamaOzet };
  hikayeOnbellek = { t: Date.now(), veri };
  return veri;
}
function hikayeIptal() { hikayeOnbellek = { t: 0, veri: null }; }

async function kayitOku(id) {
  if (!KAYIT_RE.test(id || '')) return null;
  const dal = await varsayilanDal();
  const r = await gh(`/repos/${REPO}/contents/zincir/${id}.json?ref=${encodeURIComponent(dal)}`);
  if (!r.ok) return null;
  const d = await r.json();
  return { sha: d.sha, veri: JSON.parse(Buffer.from(d.content || '', 'base64').toString('utf8')) };
}
async function kayitYaz(id, veri, sha, mesaj) {
  const dal = await varsayilanDal();
  const govde = { message: mesaj, content: Buffer.from(JSON.stringify(veri, null, 2)).toString('base64'), branch: dal };
  if (sha) govde.sha = sha;
  return gh(`/repos/${REPO}/contents/zincir/${id}.json`, { method: 'PUT', body: JSON.stringify(govde) });
}
async function kayitGuncelle(id, degistir, mesaj) {
  for (let i = 0; i < 3; i++) {
    const k = await kayitOku(id);
    if (!k) return false;
    degistir(k.veri);
    const r = await kayitYaz(id, k.veri, k.sha, mesaj);
    if (r.ok) { zincirOnbellek = { t: 0, veri: null }; return true; }
    if (r.status !== 409 && r.status !== 422) return false;
    await bekle(800);
  }
  return false;
}
async function zincirListesi() {
  if (Date.now() - zincirOnbellek.t < 30e3 && zincirOnbellek.veri) return zincirOnbellek.veri;
  const dal = await varsayilanDal();
  const r = await gh(`/repos/${REPO}/contents/zincir?ref=${encodeURIComponent(dal)}`);
  if (r.status === 404) return { depo: REPO, dal, kayitlar: [] };
  if (!r.ok) throw new Error('liste');
  // Ad 'c' ya da 'y' ile başlar; sıralamada harfi değil tarih-saati kullan
  const adlar = (await r.json()).map(f => f.name).filter(n => /^[cy]\d{8}-\d{6}\.json$/.test(n)).sort((x, y) => (y.slice(1) < x.slice(1) ? -1 : 1)).slice(0, 12);
  const kayitlar = (await Promise.all(adlar.map(a => kayitOku(a.slice(0, -5)).then(k => k && k.veri).catch(() => null)))).filter(Boolean)
    .sort((x, y) => Date.parse(y.olusturma || 0) - Date.parse(x.olusturma || 0));
  const veri = { depo: REPO, dal, kayitlar };
  zincirOnbellek = { t: Date.now(), veri };
  return veri;
}
async function direktifBaslat(metin, format) {
  const dal = await varsayilanDal();
  const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { direktif: metin, format } }) });
  return { r, baslangic: new Date(Date.now() - 5000).toISOString() };
}

async function varsayilanDal() { const r = await gh(`/repos/${REPO}`); const j = await r.json(); return j.default_branch; }

let viralIlerleme = null, viralOnbellek = { t: 0, veri: null };
async function viralDurum() {
  // Son viral video çalışması (GitHub) + iş akışının bildirdiği aşama. Sayfa kapanıp açılsa da durum buradan okunur.
  if (Date.now() - viralOnbellek.t < 12e3 && viralOnbellek.veri) return viralOnbellek.veri;
  const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_VIRAL}/runs?per_page=1`);
  const run = r.ok ? ((await r.json()).workflow_runs || [])[0] : null;
  const veri = { var: !!run };
  if (run) {
    const bas = run.run_started_at || run.created_at;
    Object.assign(veri, { calisiyor: ['queued', 'in_progress', 'waiting', 'requested', 'pending'].includes(run.status), durum: run.status, sonuc: run.conclusion,
      baslangic: bas, bitis: run.status === 'completed' ? run.updated_at : null, adres: run.html_url, olay: run.event });
    if (viralIlerleme && Date.parse(viralIlerleme.t) >= Date.parse(bas) - 60e3) Object.assign(veri, { asama: viralIlerleme.asama, yuzde: viralIlerleme.yuzde, mesaj: viralIlerleme.mesaj, ilerleme_t: viralIlerleme.t });
  }
  viralOnbellek = { t: Date.now(), veri };
  return veri;
}

async function ajanDurumlari() {
  if (Date.now() - ajanOnbellek.t < 60e3 && ajanOnbellek.veri) return ajanOnbellek.veri;
  const dosyalar = [...new Set(Object.values(AJAN_AKISLARI).flat())];
  const akis = {};
  for (const d of dosyalar) {
    const r = await gh(`/repos/${REPO}/actions/workflows/${d}/runs?per_page=5`);
    if (!r.ok) { akis[d] = { yok: true }; continue; }
    const run = ((await r.json()).workflow_runs || [])[0];
    akis[d] = run ? { son: run.run_started_at || run.created_at, durum: run.status, sonuc: run.conclusion, adres: run.html_url, olay: run.event } : { yok: true };
  }
  const veri = {};
  for (const [id, d] of Object.entries(AJAN_AKISLARI)) {
    const adaylar = [].concat(d).map(x => akis[x]).filter(x => x && !x.yok).sort((a, b) => Date.parse(b.son) - Date.parse(a.son));
    veri[id] = adaylar[0] || { yok: true };
  }
  ajanOnbellek = { t: Date.now(), veri };
  return veri;
}

async function api(req, res, url) {
  if (url.pathname === '/api/ping') return json(res, 200, { ok: true, hazir: !!(TOKEN && SIFRE), bildirim: BILDIRIM_ACIK });
  if (url.pathname === '/api/zamanlayici') return json(res, 200, { acik: !ZAM_KAPALI && !!TOKEN, son: zamSon });
  if (url.pathname === '/api/kuru-kayit' && BILDIRIM_KURU) return json(res, 200, kuruKayit);
  if (url.pathname === '/api/vapid') return json(res, 200, { acik: BILDIRIM_ACIK, anahtar: BILDIRIM_ACIK ? VAPID_PUB : null });
  if (url.pathname === '/api/hikaye') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    if (url.searchParams.get('taze')) hikayeIptal();
    try { return json(res, 200, await hikayeListesi()); } catch (e) { return json(res, 502, { hata: 'Hikaye verisi okunamadı.' }); }
  }
  if (url.pathname === '/api/istatistik') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    try {
      const son = await depoOku('istatistik/son.json').catch(() => null);
      const gec = await depoOku('istatistik/gecmis.jsonl').catch(() => null);
      const ay = await depoOku('istatistik/ayar.json').catch(() => null);
      const gecmis = gec ? gec.metin.split('\n').filter(Boolean).slice(-120).map(s => { try { return JSON.parse(s); } catch (e) { return null; } }).filter(Boolean) : [];
      return json(res, 200, { son: son ? JSON.parse(son.metin) : null, gecmis, ayar: Object.assign({ aktif: true, artis_yoksa_atla: false }, ay ? JSON.parse(ay.metin) : {}) });
    } catch (e) { return json(res, 502, { hata: 'İstatistik verisi okunamadı.' }); }
  }
  if (url.pathname === '/api/akademi') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    try {
      const r = await depoOku('akademi/rapor-son.json').catch(() => null);
      const o = await depoOku('akademi/oneriler.json').catch(() => null);
      return json(res, 200, { rapor: r ? JSON.parse(r.metin) : null, oneriler: o ? (JSON.parse(o.metin).oneriler || []) : [] });
    } catch (e) { return json(res, 502, { hata: 'Akademi verisi okunamadı.' }); }
  }
  if (url.pathname === '/api/shorts') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    try {
      const dal = await varsayilanDal();
      const r = await gh(`/repos/${REPO}/contents/shorts?ref=${encodeURIComponent(dal)}`);
      const adlar = r.ok ? (await r.json()).map(f => f.name).filter(n => /^s\d{8}-\d{6}\.json$/.test(n)).sort().reverse().slice(0, 10) : [];
      const taslaklar = (await Promise.all(adlar.map(a => depoOku('shorts/' + a).then(k => k && JSON.parse(k.metin)).catch(() => null)))).filter(Boolean);
      return json(res, 200, { depo: REPO, dal, taslaklar });
    } catch (e) { return json(res, 502, { hata: 'Shorts taslakları okunamadı.' }); }
  }
  if (url.pathname === '/api/bildir' && req.method === 'POST') {
    // Sunucudan sunucuya: ajanlar (GitHub iş akışları) kendi sırlarıyla bildirim ister
    if (!BILDIRIM_ACIK) return json(res, 503, { hata: 'Bildirim kapalı (VAPID anahtarları ya da BILDIRIM_SIRRI eksik).' });
    if (kilitliMi(req)) return json(res, 429, { hata: 'Çok fazla yanlış deneme.' });
    const gelen = String(req.headers['x-bildirim'] || '');
    const a = crypto.createHash('sha256').update(gelen).digest(), b2 = crypto.createHash('sha256').update(BILDIRIM_SIRRI).digest();
    if (!crypto.timingSafeEqual(a, b2)) { yanlisKaydet(req); return json(res, 401, { hata: 'Yetkisiz.' }); }
    const simdi = Date.now();
    while (bildirimler.length && simdi - bildirimler[0] > 3600e3) bildirimler.shift();
    if (bildirimler.length >= 60) return json(res, 429, { hata: 'Saatte en fazla 60 bildirim.' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const yuk = { baslik: temiz(b.baslik, 80) || 'Ajan ofisi', govde: temiz(b.govde, 200), etiket: temiz(b.etiket, 30) || 'ajan' };
    if (b.gorsel && adresGuvenli(b.gorsel)) yuk.gorsel = b.gorsel;
    yuk.adres = adresGuvenli(b.adres) ? b.adres : '/';
    bildirimler.push(simdi);
    try { return json(res, 200, await bildirimGonder(yuk)); } catch (e) { return json(res, 502, { hata: 'Bildirim gönderilemedi.' }); }
  }
  if (url.pathname === '/api/ajanlar') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    try { return json(res, 200, { zaman: new Date().toISOString(), ajanlar: await ajanDurumlari() }); }
    catch (e) { return json(res, 502, { hata: 'GitHub okunamadı.' }); }
  }
  if (url.pathname === '/api/zincir') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    if (url.searchParams.get('taze')) zincirOnbellek = { t: 0, veri: null };
    try { return json(res, 200, await zincirListesi()); } catch (e) { return json(res, 502, { hata: 'Zincir okunamadı.' }); }
  }
  if (url.pathname === '/api/trendler') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    if (!url.searchParams.get('taze') && Date.now() - trendOnbellek.t < 60e3 && trendOnbellek.veri) return json(res, 200, trendOnbellek.veri);
    try {
      const dal = await varsayilanDal();
      const r = await gh(`/repos/${REPO}/contents/ajan/trendler.json?ref=${encodeURIComponent(dal)}`);
      if (r.status === 404) return json(res, 200, { yok: true });
      if (!r.ok) return json(res, 502, { hata: 'Trendler okunamadı.' });
      const d = await r.json();
      const veri = JSON.parse(Buffer.from(d.content || '', 'base64').toString('utf8'));
      trendOnbellek = { t: Date.now(), veri };
      return json(res, 200, veri);
    } catch (e) { return json(res, 502, { hata: 'Trendler okunamadı.' }); }
  }
  if (url.pathname === '/api/viral-ilerleme' && req.method === 'POST') {
    // Sunucudan sunucuya: viral video iş akışı aşama/yüzde bildirir (BILDIRIM_SIRRI ile)
    if (!BILDIRIM_SIRRI) return json(res, 503, { hata: 'BILDIRIM_SIRRI tanımlı değil.' });
    if (kilitliMi(req)) return json(res, 429, { hata: 'Çok fazla yanlış deneme.' });
    const gelen = String(req.headers['x-bildirim'] || '');
    const a = crypto.createHash('sha256').update(gelen).digest(), b2 = crypto.createHash('sha256').update(BILDIRIM_SIRRI).digest();
    if (!crypto.timingSafeEqual(a, b2)) { yanlisKaydet(req); return json(res, 401, { hata: 'Yetkisiz.' }); }
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    viralIlerleme = { asama: temiz(b.asama, 60), yuzde: Math.max(0, Math.min(100, Math.round(+b.yuzde || 0))), mesaj: temiz(b.mesaj, 160), t: new Date().toISOString() };
    viralOnbellek.t = 0;
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/viral-durum') {
    if (!TOKEN) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN tanımlı değil.' });
    try { return json(res, 200, await viralDurum()); } catch (e) { return json(res, 502, { hata: 'Durum okunamadı.' }); }
  }
  if (!TOKEN || !SIFRE) return json(res, 503, { hata: 'Sunucuda GITHUB_TOKEN ya da PANEL_SIFRE tanımlı değil.' });
  if (kilitliMi(req)) return json(res, 429, { hata: 'Çok fazla yanlış deneme. 15 dakika sonra tekrar dene.' });
  if (!sifreDogru(req.headers['x-sifre'])) { yanlisKaydet(req); return json(res, 401, { hata: 'Şifre yanlış.' }); }

  if (url.pathname === '/api/abone' && req.method === 'POST') {
    if (!BILDIRIM_ACIK) return json(res, 503, { hata: 'Bildirim kapalı (VAPID anahtarları ya da BILDIRIM_SIRRI eksik).' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const ab = b.abonelik || {};
    if (!(typeof ab.endpoint === 'string' && /^https:\/\//.test(ab.endpoint) && ab.endpoint.length < 600 && ab.keys && typeof ab.keys.p256dh === 'string' && typeof ab.keys.auth === 'string')) return json(res, 400, { hata: 'Geçersiz abonelik.' });
    const temizAb = { endpoint: ab.endpoint, keys: { p256dh: ab.keys.p256dh.slice(0, 200), auth: ab.keys.auth.slice(0, 100) }, tarih: new Date().toISOString() };
    try {
      const yeni = await aboneleriGuncelle(l => l.filter(x => x.endpoint !== temizAb.endpoint).concat([temizAb]).slice(-5), 'Bildirim: abonelik eklendi');
      return json(res, 200, { ok: true, abone: yeni.length });
    } catch (e) { return json(res, 502, { hata: 'Abonelik kaydedilemedi.' }); }
  }
  if (url.pathname === '/api/bildirim-dene' && req.method === 'POST') {
    if (!BILDIRIM_ACIK) return json(res, 503, { hata: 'Bildirim kapalı.' });
    try { return json(res, 200, await bildirimGonder({ baslik: 'Deneme bildirimi', govde: 'Ajan ofisinden bildirim alıyorsun. Hikaye yayınlanınca böyle haber gelecek.', adres: '/', etiket: 'deneme' })); }
    catch (e) { return json(res, 502, { hata: 'Bildirim gönderilemedi.' }); }
  }
  if (url.pathname === '/api/hikaye-ayar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const tam = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
    const guncel = {};
    if ('aktif' in b) guncel.aktif = b.aktif === true;
    if ('gunluk_sayi' in b) { if (!tam(b.gunluk_sayi, 1, 12)) return json(res, 400, { hata: 'Günlük sayı 1 ile 12 arasında olmalı.' }); guncel.gunluk_sayi = b.gunluk_sayi; }
    if ('baslangic_saat' in b) { if (!tam(b.baslangic_saat, 0, 23)) return json(res, 400, { hata: 'Başlangıç saati 0-23 olmalı.' }); guncel.baslangic_saat = b.baslangic_saat; }
    if ('bitis_saat' in b) { if (!tam(b.bitis_saat, 1, 24)) return json(res, 400, { hata: 'Bitiş saati 1-24 olmalı.' }); guncel.bitis_saat = b.bitis_saat; }
    if ('min_aralik_dk' in b) { if (!tam(b.min_aralik_dk, 15, 240)) return json(res, 400, { hata: 'Asgari aralık 15-240 dakika olmalı.' }); guncel.min_aralik_dk = b.min_aralik_dk; }
    if ('gunler' in b) { if (!Array.isArray(b.gunler) || !b.gunler.length || !b.gunler.every(g => tam(g, 1, 7))) return json(res, 400, { hata: 'En az bir gün seç.' }); guncel.gunler = [...new Set(b.gunler)].sort(); }
    if ('mod' in b) { if (!['otomatik', 'onay'].includes(b.mod)) return json(res, 400, { hata: 'Geçersiz mod.' }); guncel.mod = b.mod; }
    const ok = await jsonGuncelle('hikaye/ayar.json', v => {
      Object.assign(v, guncel);
      if (v.bitis_saat <= v.baslangic_saat) return false;
      if (guncel.aktif === true) { v.ardisik_hata = 0; v.son_not = ''; }
    }, 'Panel: hikaye ayarı', { aktif: false, mod: 'otomatik', gunluk_sayi: 4, baslangic_saat: 10, bitis_saat: 22, gunler: [1, 2, 3, 4, 5, 6, 7], min_aralik_dk: 60, ardisik_hata: 0, hata_siniri: 3, son_not: '' });
    hikayeIptal();
    return ok ? json(res, 200, { ok: true }) : json(res, 400, { hata: 'Ayar kaydedilemedi (bitiş saati başlangıçtan büyük olmalı).' });
  }
  if (url.pathname === '/api/akademi-karar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    if (!AKADEMI_RE.test(String(b.id || ''))) return json(res, 400, { hata: 'Geçersiz kimlik.' });
    if (!['onayla', 'reddet', 'kaldir', 'sil'].includes(b.karar)) return json(res, 400, { hata: 'Geçersiz karar.' });
    let bulundu = false;
    const ok = await jsonGuncelle('akademi/oneriler.json', v => {
      v.oneriler = v.oneriler || [];
      const o = v.oneriler.find(x => x.id === b.id);
      if (!o) return false;
      bulundu = true;
      if (b.karar === 'onayla') o.durum = 'onayli';
      else if (b.karar === 'reddet' || b.karar === 'kaldir') o.durum = 'reddedildi';
      else v.oneriler = v.oneriler.filter(x => x.id !== b.id);
    }, 'Panel: akademi dersi ' + b.karar, { oneriler: [] });
    return ok ? json(res, 200, { ok: true }) : json(res, bulundu ? 502 : 404, { hata: bulundu ? 'Kaydedilemedi.' : 'Öneri bulunamadı.' });
  }
  if (url.pathname === '/api/istatistik-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (istatistikTetikler.length && simdi - istatistikTetikler[0] > 3600e3) istatistikTetikler.shift();
    if (istatistikTetikler.length >= 4) return json(res, 429, { hata: 'Saatte en fazla 4 elle istatistik raporu.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_ISTATISTIK}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { elle: 'EVET' } }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    istatistikTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/istatistik-ayar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const yeni = {};
    if (typeof b.aktif === 'boolean') yeni.aktif = b.aktif;
    if (typeof b.artis_yoksa_atla === 'boolean') yeni.artis_yoksa_atla = b.artis_yoksa_atla;
    if (!Object.keys(yeni).length) return json(res, 400, { hata: 'Değişiklik yok.' });
    try {
      let sonuc;
      const yazildi = await jsonGuncelle('istatistik/ayar.json', v => { if (v.aktif === undefined) v.aktif = true; if (v.artis_yoksa_atla === undefined) v.artis_yoksa_atla = false; Object.assign(v, yeni); sonuc = Object.assign({}, v); }, 'İstatistik raporu ayarı (panel)', { aktif: true, artis_yoksa_atla: false });
      if (!yazildi) return json(res, 502, { hata: 'Ayar kaydedilemedi.' });
      return json(res, 200, { ok: true, ayar: sonuc });
    } catch (e) { return json(res, 502, { hata: 'Ayar kaydedilemedi.' }); }
  }
  if (url.pathname === '/api/akademi-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (akademiTetikler.length && simdi - akademiTetikler[0] > 3600e3) akademiTetikler.shift();
    if (akademiTetikler.length >= 3) return json(res, 429, { hata: 'Saatte en fazla 3 elle akademi çalıştırması.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_AKADEMI}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: {} }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    akademiTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/shorts-karar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    if (!SHORTS_RE.test(String(b.id || ''))) return json(res, 400, { hata: 'Geçersiz kimlik.' });
    if (!['reddet', 'sil', 'yayinlandi', 'hikaye', 'geri_al'].includes(b.karar)) return json(res, 400, { hata: 'Geçersiz karar.' });
    const yol = `shorts/${b.id}.json`;
    const k = await depoOku(yol);
    if (!k) return json(res, 404, { hata: 'Taslak bulunamadı.' });
    const t = JSON.parse(k.metin);
    if (b.karar === 'sil') {
      if (t.durum === 'yayinlandi') return json(res, 409, { hata: 'Yayınlanmış taslak silinemez.' });
      if (/^videolar\/yukleme_\d{14}\.mp4$/.test(t.video || '')) { const vk = await depoOku(t.video); if (vk) await depoSil(t.video, vk.sha, 'Panel: Shorts videosu silindi'); }
      const r = await depoSil(yol, k.sha, 'Panel: Shorts taslağı silindi');
      return r.ok ? json(res, 200, { ok: true }) : json(res, 502, { hata: 'Silinemedi.' });
    }
    if (b.karar === 'hikaye') t.hikaye_tarihi = new Date().toISOString();   // aynı video Instagram hikayesi olarak gönderildi
    else if (b.karar === 'geri_al') {   // yayın gerçekte başarısız olduysa (ör. Instagram engeli) o platformu yeniden denemek için açar
      if (!['youtube', 'instagram'].includes(b.hedef)) return json(res, 400, { hata: 'Geçersiz platform.' });
      t.yayinlanan = (t.yayinlanan || []).filter(h => h !== b.hedef);
      t.durum = 'onay_bekliyor';
    }
    else if (b.karar === 'reddet') t.durum = 'reddedildi';
    else if (['youtube', 'instagram'].includes(b.hedef)) {   // tek platform yayınlandı: diğeri için taslak beklemeye devam eder
      t.yayinlanan = [...new Set([...(t.yayinlanan || []), b.hedef])];
      t.yayin_tarihi = new Date().toISOString();
      if (t.yayinlanan.includes('youtube') && t.yayinlanan.includes('instagram')) t.durum = 'yayinlandi';
    } else { t.durum = 'yayinlandi'; t.yayinlanan = ['youtube', 'instagram']; t.yayin_tarihi = new Date().toISOString(); }
    const r = await depoYaz(yol, JSON.stringify(t, null, 2), k.sha, 'Panel: Shorts taslağı ' + t.durum);
    return r.ok ? json(res, 200, { ok: true, durum: t.durum }) : json(res, 502, { hata: 'Kaydedilemedi.' });
  }
  if (url.pathname === '/api/shorts-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (kisaTetikler.length && simdi - kisaTetikler[0] > 3600e3) kisaTetikler.shift();
    if (kisaTetikler.length >= 3) return json(res, 429, { hata: 'Saatte en fazla 3 elle Shorts üretimi.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_KISA}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { hemen: 'EVET' } }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    kisaTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/viral-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (viralTetikler.length && simdi - viralTetikler[0] > 3600e3) viralTetikler.shift();
    if (viralTetikler.length >= 2) return json(res, 429, { hata: 'Saatte en fazla 2 elle viral video üretimi.' });
    let konu = '';
    try { const b = await govde(req); konu = String(b.konu || '').replace(/[\r\n]+/g, ' ').trim().slice(0, 120); } catch (e) { /* konu isteğe bağlı */ }
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_VIRAL}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { hemen: 'EVET', konu } }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    viralTetikler.push(simdi); viralOnbellek.t = 0;
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/trend-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (trendTetikler.length && simdi - trendTetikler[0] > 3600e3) trendTetikler.shift();
    if (trendTetikler.length >= 3) return json(res, 429, { hata: 'Saatte en fazla 3 elle trend araştırması.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_TREND}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: {} }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    trendTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/uretim-ayar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const tam = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
    const guncel = {};
    if ('aktif' in b) guncel.aktif = b.aktif === true;
    if ('mod' in b) { if (!['otomatik', 'onay'].includes(b.mod)) return json(res, 400, { hata: 'Geçersiz mod.' }); guncel.mod = b.mod; }
    if ('gunluk_uretim' in b) { if (!tam(b.gunluk_uretim, 1, 12)) return json(res, 400, { hata: 'Günlük üretim 1-12 olmalı.' }); guncel.gunluk_uretim = b.gunluk_uretim; }
    if ('gunluk_gorsel_siniri' in b) { if (!tam(b.gunluk_gorsel_siniri, 1, 40)) return json(res, 400, { hata: 'Günlük görsel sınırı 1-40 olmalı.' }); guncel.gunluk_gorsel_siniri = b.gunluk_gorsel_siniri; }
    if ('aylik_gorsel_siniri' in b) { if (!tam(b.aylik_gorsel_siniri, 1, 600)) return json(res, 400, { hata: 'Aylık görsel sınırı 1-600 olmalı.' }); guncel.aylik_gorsel_siniri = b.aylik_gorsel_siniri; }
    if ('kuyruk_hedefi' in b) { if (!tam(b.kuyruk_hedefi, 1, 30)) return json(res, 400, { hata: 'Kuyruk hedefi 1-30 olmalı.' }); guncel.kuyruk_hedefi = b.kuyruk_hedefi; }
    if ('muzik' in b) guncel.muzik = b.muzik === true;
    if ('referans' in b) { if (!['zorunlu', 'tercih'].includes(b.referans)) return json(res, 400, { hata: 'Geçersiz referans ayarı.' }); guncel.referans = b.referans; }
    if ('kalite' in b) { if (!['low', 'medium', 'high'].includes(b.kalite)) return json(res, 400, { hata: 'Geçersiz kalite.' }); guncel.kalite = b.kalite; }
    const ok = await jsonGuncelle('hikaye/uretim.json', v => { Object.assign(v, guncel); }, 'Panel: hikaye üretim ayarı', URETIM_VARSAYILAN);
    hikayeIptal();
    return ok ? json(res, 200, { ok: true }) : json(res, 502, { hata: 'Ayar kaydedilemedi.' });
  }
  if (url.pathname === '/api/uretim-calistir' && req.method === 'POST') {
    const simdi = Date.now();
    while (uretimTetikler.length && simdi - uretimTetikler[0] > 3600e3) uretimTetikler.shift();
    if (uretimTetikler.length >= 3) return json(res, 429, { hata: 'Saatte en fazla 3 elle üretim.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_URETIM}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { hemen: 'EVET' } }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + '). Önce iş akışının birleştirildiğinden emin ol.' });
    uretimTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === '/api/hikaye-foto' && req.method === 'POST') {
    if (+req.headers['content-length'] > 3 * 1024 * 1024) return json(res, 413, { hata: 'Fotoğraf 3 MB’tan büyük olamaz (panel otomatik küçültür).' });
    let tampon; try { tampon = await govdeIkili(req, 3 * 1024 * 1024); } catch (e) { return json(res, 413, { hata: 'Fotoğraf çok büyük.' }); }
    const boyut = jpegBoyut(tampon);
    if (!boyut) return json(res, 400, { hata: 'Bu bir JPEG fotoğraf gibi görünmüyor.' });
    if (boyut.g < 360 || boyut.g > 4096 || boyut.y > 8192) return json(res, 400, { hata: 'Fotoğraf boyutu uygun değil.' });
    const liste = await hikayeListesi();
    if (liste.kuyruk.filter(o => o.durum === 'planli').length >= 60) return json(res, 429, { hata: 'Kuyruk dolu (60 planlı hikaye).' });
    const dam = damga();
    const kimlik = 'h' + dam.slice(0, 8) + '-' + dam.slice(8, 14) + '-' + crypto.randomBytes(2).toString('hex').slice(0, 3);
    const gorsel = `hikaye/gorseller/${kimlik}.jpg`;
    const r1 = await depoYaz(gorsel, tampon, null, 'Panel: hikaye fotoğrafı');
    if (!r1.ok) return json(res, 502, { hata: 'Fotoğraf kaydedilemedi (' + r1.status + ').' });
    const oge = { id: kimlik, kaynak: 'foto', durum: 'planli', olusturma: new Date().toISOString(), gorsel, baslik: temiz(url.searchParams.get('baslik') || '', 80), atif: null, yayin: null, hata: '', deneme: 0 };
    const r2 = await depoYaz(`hikaye/kuyruk/${kimlik}.json`, JSON.stringify(oge, null, 2), null, 'Panel: hikaye kuyruğa eklendi');
    hikayeIptal();
    return r2.ok ? json(res, 200, { ok: true, id: kimlik, boyut }) : json(res, 502, { hata: 'Kuyruk kaydı yazılamadı.' });
  }
  if (url.pathname === '/api/hikaye-video' && req.method === 'POST') {
    if (+req.headers['content-length'] > MAX_VIDEO) return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' });
    let tampon; try { tampon = await govdeIkili(req, MAX_VIDEO); } catch (e) { return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' }); }
    if (tampon.length < 1024 || tampon.slice(4, 8).toString('latin1') !== 'ftyp') return json(res, 400, { hata: 'Bu bir MP4 video dosyası gibi görünmüyor.' });
    const liste = await hikayeListesi();
    if (liste.kuyruk.filter(o => o.durum === 'planli').length >= 60) return json(res, 429, { hata: 'Kuyruk dolu (60 planlı hikaye).' });
    const dam = damga();
    const kimlik = 'h' + dam.slice(0, 8) + '-' + dam.slice(8, 14) + '-' + crypto.randomBytes(2).toString('hex').slice(0, 3);
    const gorsel = `hikaye/gorseller/${kimlik}.mp4`;
    const r1 = await depoYaz(gorsel, tampon, null, 'Panel: hikaye videosu');
    if (!r1.ok) return json(res, 502, { hata: 'Video kaydedilemedi (' + r1.status + ').' });
    const oge = { id: kimlik, kaynak: 'video', tur: 'video', durum: 'planli', olusturma: new Date().toISOString(), gorsel, baslik: temiz(url.searchParams.get('baslik') || '', 80), atif: null, yayin: null, hata: '', deneme: 0 };
    const r2 = await depoYaz(`hikaye/kuyruk/${kimlik}.json`, JSON.stringify(oge, null, 2), null, 'Panel: video hikaye kuyruğa eklendi');
    hikayeIptal();
    return r2.ok ? json(res, 200, { ok: true, id: kimlik, boyut: tampon.length }) : json(res, 502, { hata: 'Kuyruk kaydı yazılamadı.' });
  }
  if (url.pathname === '/api/hikaye-karar' && req.method === 'POST') {
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    if (!HIKAYE_RE.test(String(b.id || ''))) return json(res, 400, { hata: 'Geçersiz kimlik.' });
    const yol = `hikaye/kuyruk/${b.id}.json`;
    const k = await depoOku(yol);
    if (!k) return json(res, 404, { hata: 'Hikaye bulunamadı.' });
    const oge = JSON.parse(k.metin);
    if (b.karar === 'sil') {
      if (!['planli', 'onay_bekliyor', 'reddedildi', 'hata'].includes(oge.durum)) return json(res, 409, { hata: 'Yayınlanmış ya da yayınlanıyor olan hikaye silinemez.' });
      for (const yolu of [oge.gorsel, oge.hazir]) {
        if (!(yolu && /^hikaye\/gorseller\/h[\w.-]+\.(jpg|mp4)$/.test(yolu))) continue;
        const gk = await depoOku(yolu);
        if (gk) await depoSil(yolu, gk.sha, 'Panel: hikaye medyası silindi');
      }
      const r = await depoSil(yol, k.sha, 'Panel: hikaye silindi');
      hikayeIptal();
      return r.ok ? json(res, 200, { ok: true }) : json(res, 502, { hata: 'Silinemedi.' });
    }
    if (b.karar === 'onayla' || b.karar === 'reddet') {
      if (oge.durum !== 'onay_bekliyor') return json(res, 409, { hata: 'Bu hikaye onay beklemiyor.' });
      oge.durum = b.karar === 'onayla' ? 'planli' : 'reddedildi';
      const r = await depoYaz(yol, JSON.stringify(oge, null, 2), k.sha, 'Panel: hikaye ' + (b.karar === 'onayla' ? 'onaylandı' : 'reddedildi'));
      hikayeIptal();
      return r.ok ? json(res, 200, { ok: true, durum: oge.durum }) : json(res, 502, { hata: 'Kaydedilemedi.' });
    }
    return json(res, 400, { hata: 'Geçersiz karar.' });
  }
  if (url.pathname === '/api/hikaye-yayinla' && req.method === 'POST') {
    const simdi = Date.now();
    while (hikayeTetikler.length && simdi - hikayeTetikler[0] > 3600e3) hikayeTetikler.shift();
    if (hikayeTetikler.length >= 6) return json(res, 429, { hata: 'Saatte en fazla 6 elle hikaye yayını.' });
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${AKIS_HIKAYE}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: { hemen: 'EVET' } }) });
    if (r.status !== 204) return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').' });
    hikayeTetikler.push(simdi);
    return json(res, 200, { ok: true });
  }
  if ((url.pathname === '/api/direktif' || url.pathname === '/api/icerik-uret') && req.method === 'POST') {
    const simdi = Date.now();
    while (direktifler.length && simdi - direktifler[0] > 3600e3) direktifler.shift();
    if (direktifler.length >= 12) return json(res, 429, { hata: 'Saatte en fazla 12 direktif.' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    const metin = String(b.metin || '').replace(/\s+/g, ' ').trim().slice(0, 500);
    if (url.pathname === '/api/direktif' && metin.length < 3) return json(res, 400, { hata: 'Direktif çok kısa.' });
    const format = ['reels', 'carousel', 'otomatik'].includes(b.format) ? b.format : 'reels';
    const { r } = await direktifBaslat(metin, format);
    if (r.status !== 204) { const t = await r.text(); return json(res, 502, { hata: 'GitHub kabul etmedi (' + r.status + ').', ayrinti: t.slice(0, 200) }); }
    direktifler.push(simdi);
    return json(res, 200, { ok: true, baslangic: new Date(simdi - 5000).toISOString() });
  }

  if (url.pathname === '/api/video-yukle' && req.method === 'POST') {
    if (+req.headers['content-length'] > MAX_VIDEO) return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' });
    let tampon; try { tampon = await govdeIkili(req, MAX_VIDEO); } catch (e) { return json(res, 413, { hata: 'Video 30 MB’tan büyük olamaz.' }); }
    if (tampon.length < 1024 || tampon.slice(4, 8).toString('latin1') !== 'ftyp') return json(res, 400, { hata: 'Bu bir MP4 video dosyası gibi görünmüyor.' });
    const ozet = crypto.createHash('sha256').update(tampon).digest('hex');
    const dal = await varsayilanDal();
    const yol = `videolar/yukleme_${damga()}.mp4`;
    try { await dosyaYaz(yol, tampon, 'Panelden video yüklendi', dal); } catch (e) { return json(res, 502, { hata: e.kullanici ? e.message : 'Video kaydedilemedi.' }); }
    videoIzi.set(yol, ozet); if (videoIzi.size > 300) videoIzi.delete(videoIzi.keys().next().value);
    const icerik = url.searchParams.get('icerik') || '';
    let bagli = false;
    if (icerik) bagli = await kayitGuncelle(icerik, v => { v.video = { yol, tarih: new Date().toISOString() }; if (v.durum === 'senaryo') v.durum = 'video'; }, 'Zincir: video yüklendi');
    return json(res, 200, { ok: true, yol, boyut: tampon.length, bagli });
  }

  if (url.pathname === '/api/yayinla' && req.method === 'POST') {
    const simdi = Date.now();
    while (yayinlar.length && simdi - yayinlar[0] > 3600e3) yayinlar.shift();
    if (yayinlar.length >= 6) return json(res, 429, { hata: 'Saatte en fazla 6 yayın başlatılabilir.' });
    let b; try { b = await govde(req); } catch (e) { return json(res, 400, { hata: 'Geçersiz istek.' }); }
    if (b.onay !== true) return json(res, 400, { hata: 'Onay verilmedi.' });
    if (!/^videolar\/yukleme_\d{14}\.mp4$/.test(String(b.yol || ''))) return json(res, 400, { hata: 'Geçersiz video yolu.' });
    const hedefler = Array.isArray(b.hedefler) ? [...new Set(b.hedefler.filter(h => h === 'instagram' || h === 'youtube' || h === 'hikaye'))] : [];
    if (!hedefler.length) return json(res, 400, { hata: 'En az bir platform seç.' });
    const metinGerek = hedefler.includes('instagram') || hedefler.includes('youtube');   // hikaye yazı almaz
    const baslik = temiz(b.baslik, 100), aciklama = temiz(b.aciklama, 2000);
    if (metinGerek && baslik.length < 3) return json(res, 400, { hata: 'Başlık çok kısa.' });
    if (metinGerek && aciklama.length < 3) return json(res, 400, { hata: 'Açıklama çok kısa.' });
    // Aynı video (içerik olarak) 24 saat içinde aynı platforma zaten gönderildiyse engelle; panel onay alıp 'tekrar' ile yeniden dener
    const izAnahtari = videoIzi.get(b.yol) || b.yol, onceki = sonYayinlar.get(izAnahtari) || {};
    const cakisan = hedefler.filter(h => h !== 'hikaye' && onceki[h] && simdi - onceki[h] < 24 * 3600e3);
    if (cakisan.length && b.tekrar !== true) {
      const ad2 = { youtube: 'YouTube', instagram: 'Instagram' };
      const dk = Math.max(1, Math.round((simdi - Math.max(...cakisan.map(h => onceki[h]))) / 60e3));
      return json(res, 409, { hata: `Bu video ${dk} dk önce ${cakisan.map(h => ad2[h]).join(' ve ')} için zaten gönderilmiş.` });
    }
    const dal = await varsayilanDal();
    const ad = b.yol.slice('videolar/'.length, -4);
    const metin = metinGerek ? yzEkle(aciklama) : '';
    const igDosya = `yayin/${ad}_instagram.txt`, ytDosya = `yayin/${ad}_youtube.txt`;
    try {
      if (hedefler.includes('instagram')) await dosyaYaz(igDosya, metin + '\n', 'Panelden Instagram metni', dal);
      if (hedefler.includes('youtube')) await dosyaYaz(ytDosya, baslik + '\n' + (/#shorts/i.test(metin) ? metin : metin + '\n\n#Shorts') + '\n', 'Panelden YouTube metni', dal);
    } catch (e) { return json(res, 502, { hata: e.kullanici ? e.message : 'Metin kaydedilemedi.' }); }
    // Aynı video Instagram hikayesi olarak da gidecekse kuyruğa o videoyu işaret eden bir kayıt aç (dosya kopyalanmaz)
    let hikayeKimligi = '';
    if (hedefler.includes('hikaye')) {
      const dam = damga();
      hikayeKimligi = 'h' + dam.slice(0, 8) + '-' + dam.slice(8, 14) + '-' + crypto.randomBytes(2).toString('hex').slice(0, 3);
      const oge = { id: hikayeKimligi, kaynak: 'yayin', tur: 'video', durum: 'planli', olusturma: new Date().toISOString(), gorsel: b.yol, baslik: baslik || 'Video hikayesi', atif: null, yayin: null, hata: '', deneme: 0 };
      const rk = await depoYaz(`hikaye/kuyruk/${hikayeKimligi}.json`, JSON.stringify(oge, null, 2), null, 'Panel: video hikaye (aynı anda yayın)');
      if (!rk.ok) return json(res, 502, { hata: 'Hikaye kaydı yazılamadı (' + rk.status + ').' });
      hikayeIptal();
    }
    await new Promise(r => setTimeout(r, 2500));
    const baslangic = new Date(Date.now() - 5000).toISOString();
    const sonuc = {};
    for (const h of hedefler) {
      const ak = h === 'instagram' ? AKIS_IG : (h === 'youtube' ? AKIS_YT : AKIS_HIKAYE);
      const inputs = h === 'instagram' ? { video: b.yol, aciklama: igDosya, onay: 'EVET' }
        : (h === 'youtube' ? { video: b.yol, metin: ytDosya, gizlilik: 'public', onay: 'EVET' } : { hemen: 'EVET', kimlik: hikayeKimligi });
      const r = await gh(`/repos/${REPO}/actions/workflows/${ak}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs }) });
      sonuc[h] = r.status === 204 ? 'basladi' : 'GitHub kabul etmedi (' + r.status + ')';
    }
    yayinlar.push(simdi);
    for (const h of hedefler) if (sonuc[h] === 'basladi') { onceki[h] = simdi; sonYayinlar.set(izAnahtari, onceki); }
    if (sonYayinlar.size > 300) sonYayinlar.delete(sonYayinlar.keys().next().value);
    // Zincir kaydı: seçili içeriğe ya da yeni bağımsız kayda yayın girişi ekle
    let icerik = KAYIT_RE.test(String(b.icerik || '')) ? b.icerik : '';
    const girisler = hedefler.filter(h => sonuc[h] === 'basladi').map(h => ({ hedef: h, platform: h === 'youtube' ? 'youtube' : 'instagram', tur: h === 'instagram' ? 'reels' : (h === 'youtube' ? 'shorts' : 'hikaye'), durum: 'basladi', baslangic, video: b.yol }));
    try {
      if (icerik) {
        if (!await kayitGuncelle(icerik, v => { v.video = v.video || { yol: b.yol, tarih: baslangic }; v.yayinlar = (v.yayinlar || []).concat(girisler); }, 'Zincir: yayın başladı')) icerik = '';
      }
      if (!icerik) {
        icerik = 'y' + damga().slice(0, 8) + '-' + damga().slice(8, 14);
        const yeni = { kimlik: icerik, olusturma: new Date().toISOString(), durum: 'video', kaynak: 'bagimsiz', direktif: '', konu: baslik || 'Video hikayesi', format: 'reels', seri: '', kanca: '',
          video: { yol: b.yol, tarih: baslangic }, yayinlar: girisler, olcumler: [], ogrenildi: false };
        await kayitYaz(icerik, yeni, null, 'Zincir: bağımsız yayın kaydı');
        zincirOnbellek = { t: 0, veri: null };
      }
    } catch (e) { console.error('zincir kaydı yazılamadı:', String(e.message).slice(0, 120)); }
    return json(res, 200, { ok: true, baslangic, sonuc, icerik });
  }

  if (url.pathname === '/api/yayin-durum') {
    const since = Date.parse(url.searchParams.get('since') || '') || 0;
    const cikti = {};
    for (const [ad, ak] of [['instagram', AKIS_IG], ['youtube', AKIS_YT], ['hikaye', AKIS_HIKAYE]]) {
      const r = await gh(`/repos/${REPO}/actions/workflows/${ak}/runs?per_page=5&event=workflow_dispatch`);
      if (!r.ok) { cikti[ad] = { durum: 'okunamadi' }; continue; }
      const run = ((await r.json()).workflow_runs || []).find(x => Date.parse(x.created_at) >= since);
      if (!run) { cikti[ad] = { durum: 'bekliyor' }; continue; }
      const o = { durum: run.status, sonuc: run.conclusion, adres: run.html_url };
      const kimlik = url.searchParams.get('icerik') || '';
      if (run.status === 'completed' && run.conclusion === 'success') {
        const l = await calismaLinki(run); o.link = l ? l.link : '';
        if (kimlik && !guncellenenler.has(`${kimlik}:${ad}:${run.id}`)) {
          guncellenenler.add(`${kimlik}:${ad}:${run.id}`);
          await kayitGuncelle(kimlik, v => {
            const g = (v.yayinlar || []).find(x => (x.hedef === ad || (!x.hedef && x.platform === ad)) && x.durum === 'basladi');
            if (g) { g.durum = 'yayinda'; g.tarih = run.updated_at; g.link = o.link; g.medya_kimligi = l ? l.medya : ''; g.adres = run.html_url; }
            if ((v.yayinlar || []).some(x => x.durum === 'yayinda')) v.durum = 'yayinda';
          }, 'Zincir: yayın tamamlandı').catch(() => {});
        }
      } else if (run.status === 'completed' && kimlik && !guncellenenler.has(`${kimlik}:${ad}:${run.id}`)) {
        guncellenenler.add(`${kimlik}:${ad}:${run.id}`);
        await kayitGuncelle(kimlik, v => { const g = (v.yayinlar || []).find(x => (x.hedef === ad || (!x.hedef && x.platform === ad)) && x.durum === 'basladi'); if (g) { g.durum = 'hata'; g.adres = run.html_url; } }, 'Zincir: yayın başarısız').catch(() => {});
      }
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
    let adimlar = [];
    try {
      const jr = await gh(`/repos/${REPO}/actions/runs/${run.id}/jobs`);
      const job = ((await jr.json()).jobs || [])[0];
      adimlar = ((job && job.steps) || []).filter(a => ZINCIR_ADIMLARI.includes(a.name)).map(a => ({ ad: a.name, durum: a.status, sonuc: a.conclusion }));
    } catch (e) { /* adım bilgisi isteğe bağlı */ }
    return json(res, 200, { durum: run.status, sonuc: run.conclusion, adres: run.html_url, baslangic: run.created_at, adimlar });
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

// ---- Zamanlayıcı: GitHub'ın zamanlayıcısı çalışmaları atlayabildiği için tetikleri sunucu kendisi verir ----
// Türkiye saati (UTC+3). Saat başı :05'te hikaye yayın kontrolü (10:05-22:05), her gün 08:20'de görsel üretimi, pazartesi/perşembe 06:30'da trend ajanı.
// İş akışları kendi kararını verir (slot, günlük sınır); çift tetik zararsızdır (ortak kilit + "önce talep et" mantığı).
const ZAM_KAPALI = process.env.ZAMANLAYICI === 'kapali';
const zamSon = { yayin: null, uretim: null, trend: null, akademi: null, kisa: null, viral: null, istatistik: null, hata: null };
const zamYapilan = new Set();
function zamSimdiTR() { const z = process.env.ZAM_ZAMAN ? new Date(process.env.ZAM_ZAMAN) : new Date(); return new Date(z.getTime() + 3 * 3600e3); }
async function zamTetikle(akis, girdi, ad) {
  try {
    const dal = await varsayilanDal();
    const r = await gh(`/repos/${REPO}/actions/workflows/${akis}/dispatches`, { method: 'POST', body: JSON.stringify({ ref: dal, inputs: girdi || {} }) });
    if (r.status === 204) { zamSon[ad] = new Date().toISOString(); console.log('Zamanlayıcı tetikledi: ' + akis); return true; }
    zamSon.hata = `${akis}: GitHub ${r.status}`; console.log('Zamanlayıcı tetiklenemedi: ' + zamSon.hata);
  } catch (e) { zamSon.hata = `${akis}: ${e.name}`; console.log('Zamanlayıcı hatası: ' + e.name); }
  return false;
}
async function zamKontrol() {
  if (ZAM_KAPALI || !TOKEN) return;
  const t = zamSimdiTR(), gun = t.toISOString().slice(0, 10), saat = t.getUTCHours(), dk = t.getUTCMinutes(), haftaGunu = t.getUTCDay();
  // hikaye yayın kontrolü: 10:05-22:35, yarım saatte bir (:05 ve :35; kaçırıldıysa o yarım saat içinde bir kez).
  // Her kontrol en çok bir hikaye yayınlar; yarım saatlik kontrol, günde 12-20 hikayeye ulaşmayı mümkün kılar.
  if (saat >= 10 && saat <= 22 && dk >= 5) {
    const anahtar = `y${gun}-${saat}-${dk >= 35 ? 'b' : 'a'}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_HIKAYE, {}, 'yayin'); }
  }
  // görsel üretimi: her gün 08:20'den sonra bir kez (pazar dahil)
  if (saat > 8 || (saat === 8 && dk >= 20)) {
    const anahtar = `u${gun}`;
    if (saat < 12 && !zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_URETIM, {}, 'uretim'); }
  }
  // trend ajanı: pazartesi ve perşembe 06:30'dan sonra bir kez
  if ((haftaGunu === 1 || haftaGunu === 4) && (saat > 6 || (saat === 6 && dk >= 30)) && saat < 12) {
    const anahtar = `t${gun}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle('trend.yml', {}, 'trend'); }
  }
  // kısa video (Shorts/Reels) taslağı: salı ve cuma 17:00'den sonra bir kez
  if ((haftaGunu === 2 || haftaGunu === 5) && saat >= 17 && saat < 22) {
    const anahtar = `k${gun}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_KISA, {}, 'kisa'); }
  }
  // viral 3D video (Türkçe seslendirmeli Shorts/Reels taslağı): pazartesi, çarşamba ve cumartesi 14:00'ten sonra bir kez
  if ([1, 3, 6].includes(haftaGunu) && saat >= 14 && saat < 21) {
    const anahtar = `v${gun}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_VIRAL, {}, 'viral'); }
  }
  // istatistikçi: günde 5 izlenme raporu (TR 09, 12, 15, 18, 21; kaçırıldıysa o saat içinde bir kez)
  if ([9, 12, 15, 18, 21].includes(saat)) {
    const anahtar = `i${gun}-${saat}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_ISTATISTIK, {}, 'istatistik'); }
  }
  // akademi ajanı: pazar 18:00'den sonra bir kez
  if (haftaGunu === 0 && saat >= 18 && saat < 23) {
    const anahtar = `a${gun}`;
    if (!zamYapilan.has(anahtar)) { zamYapilan.add(anahtar); await zamTetikle(AKIS_AKADEMI, {}, 'akademi'); }
  }
  if (zamYapilan.size > 200) { const eski = [...zamYapilan].slice(0, 100); eski.forEach(k => zamYapilan.delete(k)); }
}
if (!ZAM_KAPALI) { setInterval(() => { zamKontrol().catch(() => {}); }, 60e3); setTimeout(() => { zamKontrol().catch(() => {}); }, 20e3); }
