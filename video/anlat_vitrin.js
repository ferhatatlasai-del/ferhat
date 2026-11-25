/* "Ürün vitrini" sahnesi: kullanıcının 3D baskı modelini (STL) gerçekçi ışık ve yumuşak gölgeyle döndürür (three.js, yazılım WebGL).
 * Plan: plan.modeller = { ad: "file:///.../model.stl" }, sahne: { tip: "vitrin", params: { model: ad, kamera: "don|yaklas|detay|ust", renk: "#ff5fa2" } }.
 * Tamamen deterministik: kare(t) yalnızca t'nin fonksiyonudur. */
(function () {
  const A = window.ANLAT, S = A.sahneler, { W, H, cl, sm, lerp } = A.u, T = window.THREE;
  const V = A.vitrin = { gl: null, sahne: {}, geo: {} };

  function indir(url) {
    return new Promise(function (res, rej) { const r = new XMLHttpRequest(); r.open('GET', url); r.responseType = 'arraybuffer'; r.onload = function () { res(r.response); }; r.onerror = function () { rej(new Error('model okunamadı: ' + url)); }; r.send(); });
  }

  /* STL (ikili ya da ASCII) → üçgen köşe konumları (düz Float32Array, üçgen başına 9 sayı) */
  function stlOku(buf) {
    if (buf.byteLength > 84) {
      const dv = new DataView(buf), n = dv.getUint32(80, true);
      if (buf.byteLength === 84 + n * 50) {
        const pos = new Float32Array(n * 9);
        for (let i = 0; i < n; i++) { const off = 84 + i * 50 + 12; for (let k = 0; k < 9; k++) pos[i * 9 + k] = dv.getFloat32(off + k * 4, true); }
        return pos;
      }
    }
    const metin = new TextDecoder().decode(buf), re = /vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)/g, a = []; let m;
    while ((m = re.exec(metin))) a.push(+m[1], +m[2], +m[3]);
    return new Float32Array(a.slice(0, Math.floor(a.length / 9) * 9));
  }

  /* Açıya göre yumuşatılmış normallerle geometri: keskin kenarlar korunur (yüzey normali farkı > aci derece ise paylaşılmaz) */
  function geometri(pos, aci) {
    const n = pos.length / 9, fn = new Float32Array(n * 3);
    let mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30];
    for (let i = 0; i < n; i++) {
      const o = i * 9, ax = pos[o + 3] - pos[o], ay = pos[o + 4] - pos[o + 1], az = pos[o + 5] - pos[o + 2], bx = pos[o + 6] - pos[o], by = pos[o + 7] - pos[o + 1], bz = pos[o + 8] - pos[o + 2];
      let nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx; const l = Math.hypot(nx, ny, nz) || 1; fn[i * 3] = nx / l; fn[i * 3 + 1] = ny / l; fn[i * 3 + 2] = nz / l;
      for (let k = 0; k < 3; k++) for (let c = 0; c < 3; c++) { const v = pos[o + k * 3 + c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
    }
    const boy = Math.max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) || 1, q = 1e5 / boy;
    const norm = new Float32Array(pos.length), cs = Math.cos(aci * Math.PI / 180);
    if (n <= 400000) {
      const harita = new Map(), anahtar = function (o) { return Math.round(pos[o] * q) + ',' + Math.round(pos[o + 1] * q) + ',' + Math.round(pos[o + 2] * q); };
      for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) { const a = anahtar(i * 9 + k * 3); let l = harita.get(a); if (!l) harita.set(a, l = []); l.push(i); }
      for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) {
        const l = harita.get(anahtar(i * 9 + k * 3)); let sx = 0, sy = 0, sz = 0;
        for (let j = 0; j < l.length; j++) { const g = l[j]; if (fn[i * 3] * fn[g * 3] + fn[i * 3 + 1] * fn[g * 3 + 1] + fn[i * 3 + 2] * fn[g * 3 + 2] > cs) { sx += fn[g * 3]; sy += fn[g * 3 + 1]; sz += fn[g * 3 + 2]; } }
        const m = Math.hypot(sx, sy, sz) || 1; norm[i * 9 + k * 3] = sx / m; norm[i * 9 + k * 3 + 1] = sy / m; norm[i * 9 + k * 3 + 2] = sz / m;
      }
    } else for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) { norm[i * 9 + k * 3] = fn[i * 3]; norm[i * 9 + k * 3 + 1] = fn[i * 3 + 1]; norm[i * 9 + k * 3 + 2] = fn[i * 3 + 2]; }
    // STL'de Z yukarıdır; sahnede Y yukarı: (x, y, z) → (x, z, -y). Sonra merkezle, tabanı y=0'a koy, en uzun kenarı 1 birime ölçekle.
    const P = new Float32Array(pos.length), N = new Float32Array(pos.length);
    for (let i = 0; i < pos.length; i += 3) { P[i] = pos[i]; P[i + 1] = pos[i + 2]; P[i + 2] = -pos[i + 1]; N[i] = norm[i]; N[i + 1] = norm[i + 2]; N[i + 2] = -norm[i + 1]; }
    const g = new T.BufferGeometry(); g.setAttribute('position', new T.BufferAttribute(P, 3)); g.setAttribute('normal', new T.BufferAttribute(N, 3));
    g.computeBoundingBox(); const b = g.boundingBox, s = 0.52 / (Math.max(b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z) || 1);   // en uzun kenar 0,52 birim: dikey kadrajda sığar
    g.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2); g.scale(s, s, s); g.computeBoundingBox(); g.computeBoundingSphere();
    return g;
  }

  function kur(p, geo) {
    const sc = new T.Scene(), renk = new T.Color(p.renk || '#ff5fa2');
    sc.add(new T.HemisphereLight(0xdfe6ff, 0x3a2268, 0.35));
    const key = new T.DirectionalLight(0xfff1e0, 1.5); key.position.set(1.6, 3, 1.4); key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = key.shadow.camera.bottom = -1; key.shadow.camera.right = key.shadow.camera.top = 1; key.shadow.camera.near = 0.5; key.shadow.camera.far = 10; key.shadow.bias = -0.0004; key.shadow.radius = 5;
    sc.add(key);
    const dolgu = new T.DirectionalLight(0x9ec8ff, 0.45); dolgu.position.set(-2.2, 1.2, 1.0); sc.add(dolgu);
    const rim = new T.DirectionalLight(0xff7ad9, 1.1); rim.position.set(-0.6, 1.6, -2.6); sc.add(rim);
    const mesh = new T.Mesh(geo, new T.MeshStandardMaterial({ color: renk, roughness: 0.38, metalness: 0.08 })); mesh.castShadow = true; sc.add(mesh);
    const zemin = new T.Mesh(new T.CircleGeometry(5, 64), new T.ShadowMaterial({ opacity: 0.4 })); zemin.rotation.x = -Math.PI / 2; zemin.receiveShadow = true; sc.add(zemin);
    const kam = new T.PerspectiveCamera(30, W / H, 0.05, 60);
    return { sc: sc, kam: kam, boy: geo.boundingBox.max.clone() };
  }

  A.vitrinHazirla = async function (p, ol) {
    const vs = (p.sahneler || []).map(function (s, i) { return [s, i]; }).filter(function (a) { return a[0].tip === 'vitrin' && a[0].params && a[0].params.model; });
    if (!vs.length) return;
    const glc = document.createElement('canvas'); glc.width = Math.round(W * ol); glc.height = Math.round(H * ol);
    const r = V.gl = new T.WebGLRenderer({ canvas: glc, antialias: true, alpha: true, preserveDrawingBuffer: true });
    r.setPixelRatio(1); r.setSize(glc.width, glc.height, false); r.setClearColor(0x000000, 0);
    r.shadowMap.enabled = true; r.shadowMap.type = T.PCFSoftShadowMap; r.toneMapping = T.ACESFilmicToneMapping; r.toneMappingExposure = 0.9; r.outputEncoding = T.sRGBEncoding;
    for (let k = 0; k < vs.length; k++) {
      const s = vs[k][0], i = vs[k][1], ad = s.params.model;
      if (!V.geo[ad]) { const url = (p.modeller || {})[ad]; if (!url) throw new Error('model tanımsız: ' + ad); V.geo[ad] = geometri(stlOku(await indir(url)), 42); }
      V.sahne[i] = kur(s.params, V.geo[ad]);
    }
  };

  /* kamera yolları: lt/d sahnenin ilerlemesi; model 1 birim, tabanı y=0 */
  function kamera(v, mod, lt, d) {
    const u = lt / Math.max(d, 0.1), q = sm(u), h = v.boy.y, hedefY = h * 0.5;
    let R, el, az, ty = hedefY;
    if (mod === 'yaklas') { R = lerp(3.1, 1.9, q); el = lerp(26, 14, q); az = 0.6 + u * 1.5; }
    else if (mod === 'detay') { R = lerp(1.9, 1.3, q); el = lerp(10, 32, q); az = -0.5 + u * 1.7; ty = lerp(h * 0.55, h * 0.8, q); }
    else if (mod === 'ust') { R = lerp(3.0, 2.6, q); el = lerp(62, 48, q); az = 0.3 + u * 2.4; }
    else { R = 2.8; el = 22 + 4 * Math.sin(u * Math.PI); az = 0.4 + u * Math.min(Math.PI * 2, 0.95 * d); }   // don
    const e = el * Math.PI / 180;
    v.kam.position.set(R * Math.cos(e) * Math.sin(az), ty + R * Math.sin(e), R * Math.cos(e) * Math.cos(az));
    v.kam.lookAt(0, ty, 0);
  }

  S.vitrin = function (c) {
    const { x, lt, d, p, i } = c, v = V.sahne[i];
    c.arka(p.tema || 'mor');
    if (!v || !V.gl) return;
    kamera(v, p.kamera || 'don', lt, d);
    V.gl.render(v.sc, v.kam);
    x.drawImage(V.gl.domElement, 0, 0, W, H);
    if (lt < 0.35) { x.fillStyle = 'rgba(0,0,0,' + (0.4 * (1 - cl(lt / 0.35))) + ')'; x.fillRect(0, 0, W, H); }
  };
  A.tipler = Object.keys(S);
})();
