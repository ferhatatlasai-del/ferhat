#!/usr/bin/env node
/* Plan dosyasından kareleri çizip ffmpeg'e aktarır (video sessiz çıkar; ses ayrıca eklenir).
 *   node video/render.js plan.json --cikti sessiz.mp4 [--olcek 1] [--bas 0 --son 10]
 *   node video/render.js plan.json --kareler 1.5,12,30 --dizin dizin [--olcek .5]   (önizleme JPEG'leri)
 */
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
let pw; try { pw = require('playwright'); } catch (e) { pw = require('playwright-core'); }

const arg = (ad, v) => { const i = process.argv.indexOf('--' + ad); return i < 0 ? v : process.argv[i + 1]; };
const planYol = process.argv[2];
if (!planYol || planYol.startsWith('--')) { console.error('Kullanım: node render.js plan.json --cikti video.mp4'); process.exit(2); }
const plan = JSON.parse(fs.readFileSync(planYol, 'utf8'));
const olcek = parseFloat(arg('olcek', '1')), kalite = parseFloat(arg('kalite', '0.9'));

const TARAYICI_ARG = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-dev-shm-usage', '--no-sandbox', '--allow-file-access-from-files'];

async function sayfaAc() {
  const b = await pw.chromium.launch({ executablePath: process.env.CHROME_YOLU || undefined, args: TARAYICI_ARG });
  const sayfa = await b.newPage({ viewport: { width: Math.round(plan.genislik * olcek), height: Math.round(plan.yukseklik * olcek) } });
  const hatalar = []; sayfa.on('pageerror', e => hatalar.push(e.message)); sayfa.on('console', m => { if (m.type() === 'error') hatalar.push(m.text()); });
  await sayfa.goto('file://' + path.join(__dirname, 'sahne.html'), { waitUntil: 'load' });
  await sayfa.evaluate(async ([p, o]) => window.hazirla(p, o), [plan, olcek]);
  if (hatalar.length) throw new Error('Sayfa hatası: ' + hatalar.slice(0, 3).join(' | '));
  return { b, sayfa, hatalar };
}

function kodlayici(cikti, fps) {
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-maxrate', '9M', '-bufsize', '18M', '-pix_fmt', 'yuv420p', '-vf', `scale=${plan.genislik}:${plan.yukseklik}:flags=lanczos`,
    '-g', String(fps * 2), '-movflags', '+faststart', cikti], { stdio: ['pipe', 'inherit', 'inherit'] });
  return { ff, bitti: new Promise(r => ff.on('close', r)) };
}

(async () => {
  const kareler = arg('kareler', null);
  if (kareler) {
    const { b, sayfa, hatalar } = await sayfaAc();
    const dizin = arg('dizin', '.'); fs.mkdirSync(dizin, { recursive: true });
    for (const t of kareler.split(',').map(Number)) {
      const d = await sayfa.evaluate(([t, k]) => window.kare(t, k), [t, kalite]);
      fs.writeFileSync(path.join(dizin, `k_${String(t).replace('.', '_')}.jpg`), Buffer.from(d, 'base64'));
    }
    if (hatalar.length) console.error('Sayfa hatası:', hatalar.slice(0, 3).join(' | '));
    await b.close(); return;
  }
  const cikti = arg('cikti'); const fps = plan.fps || 30;
  const bas = Math.round(parseFloat(arg('bas', '0')) * fps), son = Math.min(Math.round(plan.sure * fps), Math.round(parseFloat(arg('son', String(plan.sure))) * fps));
  // Paralel çizim: her işçi ayrı tarayıcıda ardışık bir kare aralığını çizer ve kendi parçasını kodlar; sonunda parçalar kayıpsız birleştirilir.
  const isci = Math.max(1, Math.min(parseInt(arg('paralel', process.env.CIZIM_PARALEL || '1'), 10) || 1, 8));
  const toplam = son - bas, t0 = Date.now(); let biten = 0, sonYazi = -1;
  const gecici = fs.mkdtempSync(path.join(require('os').tmpdir(), 'cizim-'));
  const araliklar = [...Array(isci)].map((_, k) => [bas + Math.floor(toplam * k / isci), bas + Math.floor(toplam * (k + 1) / isci)]).filter(a => a[1] > a[0]);
  const ilerle = () => { biten++; const adim = Math.floor(biten / 150); if (adim !== sonYazi) { sonYazi = adim; console.log(`Kare ${biten}/${toplam} (${((Date.now() - t0) / 1000).toFixed(0)} sn)`); } };
  const parcalar = await Promise.all(araliklar.map(async ([a, z], k) => {
    const { b, sayfa, hatalar } = await sayfaAc();
    const yol = path.join(gecici, `p${k}.mp4`), { ff, bitti } = kodlayici(yol, fps);
    for (let i = a; i < z; i++) {
      const d = await sayfa.evaluate(([t, q]) => window.kare(t, q), [i / fps, kalite]);
      if (!ff.stdin.write(Buffer.from(d, 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
      ilerle();
    }
    ff.stdin.end(); const kod = await bitti; await b.close();
    if (hatalar.length) console.error('Sayfa hatası:', hatalar.slice(0, 3).join(' | '));
    if (kod !== 0) throw new Error('ffmpeg hata kodu ' + kod);
    return yol;
  }));
  const liste = path.join(gecici, 'liste.txt'); fs.writeFileSync(liste, parcalar.map(p => `file '${p}'`).join('\n'));
  const birlestir = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste, '-c', 'copy', '-movflags', '+faststart', cikti], { stdio: 'inherit' });
  const kod = await new Promise(r => birlestir.on('close', r));
  fs.rmSync(gecici, { recursive: true, force: true });
  if (kod !== 0) { console.error('birleştirme hata kodu', kod); process.exit(1); }
  console.log(`Kare ${toplam}/${toplam}`);
  console.log('Tamam:', cikti, ((Date.now() - t0) / 1000).toFixed(0), 'sn,', araliklar.length, 'işçi');
})().catch(e => { console.error(e); process.exit(1); });
