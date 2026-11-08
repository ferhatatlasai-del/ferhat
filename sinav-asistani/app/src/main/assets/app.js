/* Sınav Asistanı — Android TV için çalışma sınavı hazırlayan uygulamanın arayüzü.
 * Android tarafı window.Android köprüsünü sağlar (MainActivity.kt).
 */
"use strict";

const DEFAULT_MODEL = "gpt-5.5";
const POLL_MS = 4000;
const MAX_WAIT_MS = 12 * 60 * 1000;
const STORE_KEY = "sinavlar";

const OPTIONS = {
  grade: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  subject: ["Matematik", "Türkçe", "Fen Bilimleri", "Sosyal Bilgiler", "İngilizce", "Din Kültürü"],
  period: ["1. dönem 1. yazılı", "1. dönem 2. yazılı", "2. dönem 1. yazılı", "2. dönem 2. yazılı"],
  count: [5, 10, 15, 20],
  level: ["Kolay", "Orta", "Zor"],
};

const state = {
  screen: "home",
  form: { grade: 5, subject: "Matematik", period: "1. dönem 2. yazılı", count: 20, level: "Orta", note: "" },
  job: null,          // { startedAt, status, cancelled, responseId }
  error: "",
  examId: null,       // açık olan sınavın kayıt kimliği
  qi: 0,
  answers: [],
  confirmFinish: false,
  keyFrom: "result",
  focusId: null,
};

/* ---------- Yardımcılar ---------- */

const $app = document.getElementById("app");

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function bridge() { return window.Android; }
function hasKey() { return !!(bridge() && bridge().hasKey()); }
function model() { return (bridge() && bridge().getModel()) || DEFAULT_MODEL; }

function schoolYear(d = new Date()) {
  const y = d.getFullYear();
  return d.getMonth() >= 8 ? `${y}-${y + 1}` : `${y - 1}-${y}`;
}

function letter(i) { return "ABCDE"[i] || "?"; }

function fmtDate(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Modelden gelen SVG'yi güvenli şekilde <img> olarak gösterir (img içinde betik çalışmaz). */
function figure(svg) {
  if (!svg || !/^\s*<svg[\s>]/i.test(svg) || /<script|<foreignObject|\son\w+=/i.test(svg)) return "";
  const src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.trim());
  return `<div class="figure"><img alt="Soru görseli" src="${src}"></div>`;
}

/* ---------- Kayıtlar (geçmiş sınavlar) ---------- */

function loadExams() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY) || "[]"); } catch (e) { return []; }
}
function saveExams(list) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(list)); } catch (e) { /* yer yoksa sessiz geç */ }
}
function getExam(id) { return loadExams().find((e) => e.id === id) || null; }
function updateExam(id, fn) {
  const list = loadExams();
  const i = list.findIndex((e) => e.id === id);
  if (i >= 0) { fn(list[i]); saveExams(list); }
}

/* ---------- OpenAI köprüsü ---------- */

const pending = {};
let cbSeq = 0;

window.__bridgeCb = function (id, code, body) {
  const fn = pending[id];
  delete pending[id];
  if (fn) fn({ code, body });
};

function api(method, path, body) {
  return new Promise((resolve) => {
    const id = "cb" + (++cbSeq);
    pending[id] = resolve;
    bridge().request(id, method, path, body ? JSON.stringify(body) : "");
  });
}

function apiError(res) {
  let msg = "";
  try { msg = (JSON.parse(res.body).error || {}).message || ""; } catch (e) { msg = res.body || ""; }
  if (res.code === 0) return "İnternete bağlanılamadı. Kutunun Wi-Fi bağlantısını kontrol edin.\n" + msg;
  if (res.code === 401) return "API anahtarı geçersiz. Ayarlar ekranından anahtarı kontrol edin.\n" + msg;
  if (res.code === 429) return "OpenAI kullanım sınırına ulaşıldı (kota veya hız sınırı). Biraz bekleyip tekrar deneyin ya da hesabınızdaki bakiyeyi kontrol edin.\n" + msg;
  if (res.code === 404) return "Model bulunamadı. Ayarlar ekranından model adını kontrol edin.\n" + msg;
  return `OpenAI hata verdi (kod ${res.code}).\n${msg}`;
}

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["baslik", "konular", "sorular", "kaynaklar"],
  properties: {
    baslik: { type: "string", description: "Sınavın kısa başlığı" },
    konular: { type: "array", items: { type: "string" }, description: "Sınavın kapsadığı konular" },
    sorular: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["soru", "svg", "secenekler", "dogru", "cozum", "konu"],
        properties: {
          soru: { type: "string" },
          svg: { type: "string", description: "Şekilli soruysa tek parça SVG kodu, değilse boş metin" },
          secenekler: { type: "array", items: { type: "string" }, description: "Tam olarak 4 seçenek, harf olmadan" },
          dogru: { type: "integer", description: "Doğru seçeneğin sırası, 0-3" },
          cozum: { type: "string", description: "Çocuğun anlayacağı kısa adım adım çözüm" },
          konu: { type: "string" },
        },
      },
    },
    kaynaklar: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["baslik", "url"],
        properties: { baslik: { type: "string" }, url: { type: "string" } },
      },
    },
  },
};

function buildInstructions(f) {
  return [
    "Sen Türkiye'de görev yapan deneyimli bir öğretmensin. Evde çalışan bir öğrenci için, okuldaki yazılı sınava hazırlanmasını sağlayacak bir deneme sınavı hazırlıyorsun.",
    `Bugünün tarihi: ${new Date().toLocaleDateString("tr-TR")}. Eğitim-öğretim yılı: ${schoolYear()}.`,
    "Önce web aramasıyla bu sınıf, ders ve sınav dönemi için MEB'in güncel öğretim programını (Türkiye Yüzyılı Maarif Modeli uygulanan sınıflarda o programı) ve bu yazılıda sorumlu olunan konuları doğrula. MEB, ölçme değerlendirme merkezleri ve güvenilir eğitim sitelerini tercih et; örnek yazılı soruları fikir almak için kullanabilirsin ama soruları birebir kopyalama.",
    "Kurallar:",
    "- Tüm metinler Türkçe ve öğrencinin yaşına uygun, açık ve kısa olsun.",
    "- Her soru çoktan seçmeli olsun: tam olarak 4 seçenek, yalnızca biri doğru. Seçeneklerin başına harf yazma.",
    "- Çözümde seçenek harfine (A, B…) atıf yapma; doğru cevabı değeriyle yaz, çünkü seçeneklerin sırası değiştirilecek.",
    "- Soruları konulara dengeli dağıt; işlem, problem, yorum ve görsel soruları karıştır.",
    "- Uygun sorularda (sayı doğrusu, kesir modeli, geometrik şekil, tablo, grafik, saat, örüntü gibi) 'svg' alanına şekli çiz. SVG kuralları: tek <svg> öğesi, viewBox kullan, genişlik en fazla 400 ve yükseklik en fazla 260, beyaz zemin üzerine koyu çizgiler, yazılar Türkçe ve en az 16 punto, betik, bağlantı ve dış kaynak yok. Şekilsiz sorularda 'svg' boş metin olsun.",
    "- Şekil soruyu çözmek için gerekiyorsa soruda 'Şekle göre…' gibi ifade kullan; şekil ile soru metni birbiriyle tutarlı olsun.",
    "- Her sorunun cevabını hesaplayarak kontrol et; cevap anahtarında hata olmasın.",
    "- 'kaynaklar' alanına araştırmada kullandığın sayfaları ekle.",
  ].join("\n");
}

function buildInput(f) {
  let s = `${f.grade}. sınıf ${f.subject} dersi, ${f.period} için ${f.count} soruluk bir deneme sınavı hazırla. Zorluk: ${f.level}.`;
  if (f.note.trim()) s += `\nEk istek: ${f.note.trim()}`;
  return s;
}

function outputText(resp) {
  let text = "";
  for (const item of resp.output || []) {
    if (item.type !== "message") continue;
    for (const c of item.content || []) {
      if (c.type === "output_text") text += c.text;
      if (c.type === "refusal") throw new Error("Model bu isteği yanıtlamadı: " + (c.refusal || ""));
    }
  }
  return text;
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/** Modelin cevabını doğrular, seçenekleri karıştırır (doğru cevaplar A-D'ye dağılsın). */
function normalizeExam(data) {
  const questions = [];
  for (const q of data.sorular || []) {
    const choices = (q.secenekler || []).map((c) => String(c).trim()).filter(Boolean);
    const correct = Number(q.dogru);
    if (!q.soru || choices.length < 2 || choices.length > 5) continue;
    if (!Number.isInteger(correct) || correct < 0 || correct >= choices.length) continue;
    const order = shuffle(choices.map((_, i) => i));
    questions.push({
      text: String(q.soru),
      svg: String(q.svg || ""),
      choices: order.map((i) => choices[i]),
      correct: order.indexOf(correct),
      explanation: String(q.cozum || ""),
      topic: String(q.konu || ""),
    });
  }
  if (!questions.length) throw new Error("Modelden geçerli soru gelmedi. Lütfen tekrar deneyin.");
  return {
    title: String(data.baslik || ""),
    topics: (data.konular || []).map(String),
    questions,
    sources: (data.kaynaklar || []).filter((s) => s && s.url).map((s) => ({ title: String(s.baslik || s.url), url: String(s.url) })),
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function generateExam(f) {
  const job = state.job;
  const body = {
    model: model(),
    background: true,
    store: true,
    reasoning: { effort: "medium" },
    tools: [{ type: "web_search" }],
    instructions: buildInstructions(f),
    input: buildInput(f),
    max_output_tokens: 40000,
    text: { format: { type: "json_schema", name: "sinav", strict: true, schema: SCHEMA } },
  };

  let res = await api("POST", "/responses", body);
  if (res.code === 400 && /background/i.test(res.body)) {
    // Arka plan modu desteklenmiyorsa bekleyerek (senkron) iste.
    delete body.background;
    delete body.store;
    job.status = "in_progress";
    render();
    res = await api("POST", "/responses", body);
  }
  if (res.code < 200 || res.code > 299) throw new Error(apiError(res));
  let resp = JSON.parse(res.body);
  job.responseId = resp.id;

  while (resp.status === "queued" || resp.status === "in_progress") {
    if (job.cancelled) return null;
    if (Date.now() - job.startedAt > MAX_WAIT_MS) throw new Error("Hazırlık çok uzun sürdü. Lütfen tekrar deneyin.");
    job.status = resp.status;
    render();
    await sleep(POLL_MS);
    if (job.cancelled) return null;
    const r = await api("GET", "/responses/" + encodeURIComponent(resp.id));
    if (r.code < 200 || r.code > 299) {
      if (r.code === 0) continue; // geçici ağ kesintisi: tekrar dene
      throw new Error(apiError(r));
    }
    resp = JSON.parse(r.body);
  }

  if (resp.status === "incomplete") {
    const reason = (resp.incomplete_details || {}).reason || "";
    throw new Error(reason === "max_output_tokens"
      ? "Sınav çok uzun oldu ve yarıda kesildi. Daha az soruyla tekrar deneyin."
      : "Sınav tamamlanamadı (" + reason + "). Lütfen tekrar deneyin.");
  }
  if (resp.status !== "completed") {
    const msg = (resp.error || {}).message || resp.status;
    throw new Error("Sınav hazırlanamadı: " + msg);
  }

  const text = outputText(resp);
  let data;
  try { data = JSON.parse(text); } catch (e) { throw new Error("Modelin cevabı okunamadı. Lütfen tekrar deneyin."); }
  return normalizeExam(data);
}

async function startGeneration() {
  state.error = "";
  state.job = { startedAt: Date.now(), status: "queued", cancelled: false, responseId: null };
  go("loading");
  const job = state.job;
  const ticker = setInterval(() => { if (state.screen === "loading") updateElapsed(); }, 1000);
  try {
    const exam = await generateExam({ ...state.form });
    if (!exam || job.cancelled) return;
    const rec = {
      id: "s" + Date.now(),
      createdAt: Date.now(),
      params: { ...state.form },
      exam,
      attempts: [],
    };
    const list = loadExams();
    list.unshift(rec);
    saveExams(list.slice(0, 50));
    openQuiz(rec.id);
  } catch (e) {
    if (job.cancelled) return;
    state.error = e.message || String(e);
    go("newExam");
  } finally {
    clearInterval(ticker);
  }
}

function cancelGeneration() {
  const job = state.job;
  if (!job) return;
  job.cancelled = true;
  if (job.responseId) api("POST", "/responses/" + encodeURIComponent(job.responseId) + "/cancel", {});
  go("newExam");
}

/* ---------- Sınav akışı ---------- */

function openQuiz(id) {
  const rec = getExam(id);
  if (!rec) return go("history");
  state.examId = id;
  state.qi = 0;
  state.answers = new Array(rec.exam.questions.length).fill(null);
  state.confirmFinish = false;
  go("quiz");
}

function pick(i) {
  state.answers[state.qi] = i;
  const total = state.answers.length;
  state.focusId = state.qi < total - 1 ? "next" : "finish";
  render();
}

function finishQuiz() {
  const rec = getExam(state.examId);
  const qs = rec.exam.questions;
  const correct = qs.reduce((n, q, i) => n + (state.answers[i] === q.correct ? 1 : 0), 0);
  updateExam(state.examId, (r) => {
    r.attempts.push({ date: Date.now(), correct, total: qs.length, answers: state.answers.slice() });
  });
  state.keyFrom = "result";
  go("result");
}

/* ---------- Ekranlar ---------- */

function chips(name, values, current, fmt = (v) => v) {
  return `<div class="chips">${values.map((v) =>
    `<button class="chip ${v === current ? "on" : ""}" id="opt-${name}-${esc(v)}" data-act="opt" data-name="${name}" data-value="${esc(v)}">${esc(fmt(v))}</button>`
  ).join("")}</div>`;
}

const SCREENS = {
  home() {
    const key = hasKey();
    return `
      <div class="top"><div><h1>📚 Sınav Asistanı</h1><p class="muted">Yapay zekâ ile yazılılara hazırlık</p></div></div>
      <div class="menu">
        <button id="m-new" data-act="go" data-to="newExam"><span class="icon">✏️</span>Yeni sınav<span class="sub">Konuyu seç, sorular hazırlansın</span></button>
        <button id="m-hist" data-act="go" data-to="history"><span class="icon">🗂️</span>Geçmiş sınavlar<span class="sub">${loadExams().length} kayıtlı sınav</span></button>
        <button id="m-set" data-act="go" data-to="settings"><span class="icon">⚙️</span>Ayarlar<span class="sub">API anahtarı ve model</span></button>
      </div>
      ${key ? "" : `<div class="notice">OpenAI API anahtarı henüz girilmedi. Sınav hazırlamak için önce <b>Ayarlar</b> ekranından anahtarı girin.</div>`}`;
  },

  newExam() {
    const f = state.form;
    return `
      <div class="top"><h2>✏️ Yeni sınav</h2><span class="muted small">Geri tuşu: ana sayfa</span></div>
      ${state.error ? `<div class="error">${esc(state.error)}</div>` : ""}
      <div class="row"><div class="row-label">Sınıf</div>${chips("grade", OPTIONS.grade, f.grade, (v) => v + ". sınıf")}</div>
      <div class="row"><div class="row-label">Ders</div>${chips("subject", OPTIONS.subject, f.subject)}</div>
      <div class="row"><div class="row-label">Sınav</div>${chips("period", OPTIONS.period, f.period)}</div>
      <div class="row"><div class="row-label">Soru sayısı</div>${chips("count", OPTIONS.count, f.count, (v) => v + " soru")}</div>
      <div class="row"><div class="row-label">Zorluk</div>${chips("level", OPTIONS.level, f.level)}</div>
      <div class="row"><div class="row-label">Ek istek (isteğe bağlı, klavyedeki mikrofonla söyleyebilirsiniz)</div>
        <input type="text" id="note" value="${esc(f.note)}" placeholder="Örn: kesirler ağırlıklı olsun, problem sorusu fazla olsun"></div>
      <div class="actions">
        <button class="primary" id="make" data-act="make">🚀 Sınavı hazırla</button>
        <button id="back-home" data-act="go" data-to="home">Ana sayfa</button>
      </div>
      ${hasKey() ? "" : `<div class="notice">Önce Ayarlar ekranından OpenAI API anahtarını girin.</div>`}`;
  },

  loading() {
    const job = state.job || {};
    const f = state.form;
    const phase = job.status === "queued" ? "Sıraya alındı, birazdan başlayacak…" : "İnternette araştırıyor ve soruları yazıyor…";
    return `
      <div class="center">
        <div class="spinner"></div>
        <h2>Sorular hazırlanıyor</h2>
        <p>${esc(f.grade)}. sınıf ${esc(f.subject)} · ${esc(f.period)} · ${esc(f.count)} soru</p>
        <p class="muted" id="phase">${esc(phase)}</p>
        <p class="muted" id="elapsed">${elapsedText()}</p>
        <p class="muted small">Bu işlem genelde 1–4 dakika sürer.</p>
        <div class="actions" style="justify-content:center"><button id="cancel" data-act="cancel">İptal</button></div>
      </div>`;
  },

  quiz() {
    const rec = getExam(state.examId);
    const qs = rec.exam.questions;
    const q = qs[state.qi];
    const total = qs.length;
    const answered = state.answers.filter((a) => a !== null).length;
    const last = state.qi === total - 1;
    if (state.confirmFinish) {
      const empty = total - answered;
      return `
        <div class="center">
          <h2>Sınavı bitirmek istiyor musun?</h2>
          <p>${empty > 0 ? `<b>${empty}</b> soruyu boş bıraktın.` : "Bütün soruları cevapladın. 👏"}</p>
          <div class="actions" style="justify-content:center">
            <button class="primary" id="yes-finish" data-act="finish-yes">Evet, bitir</button>
            <button id="no-finish" data-act="finish-no">Sorulara dön</button>
          </div>
        </div>`;
    }
    return `
      <div class="top"><h2>${esc(rec.exam.title || "Deneme sınavı")}</h2><span class="muted">Soru ${state.qi + 1} / ${total} · ${answered} cevaplandı</span></div>
      <div class="progress"><div style="width:${((state.qi + 1) / total) * 100}%"></div></div>
      <div class="qtext">${state.qi + 1}. ${esc(q.text)}</div>
      <div class="qbody">
        ${figure(q.svg)}
        <div class="choices">
          ${q.choices.map((c, i) => `<button id="c${i}" class="${state.answers[state.qi] === i ? "picked" : ""}" data-act="pick" data-i="${i}"><span class="letter">${letter(i)})</span>${esc(c)}</button>`).join("")}
        </div>
      </div>
      <div class="nav">
        <button id="prev" data-act="prev" ${state.qi === 0 ? "disabled" : ""}>◀ Önceki</button>
        ${last
          ? `<button class="primary" id="finish" data-act="finish">✅ Sınavı bitir</button>`
          : `<button class="primary" id="next" data-act="next">Sonraki ▶</button>`}
      </div>`;
  },

  result() {
    const rec = getExam(state.examId);
    const at = rec.attempts[rec.attempts.length - 1];
    const ratio = at.correct / at.total;
    const cls = ratio >= 0.85 ? "good" : ratio >= 0.5 ? "mid" : "low";
    const msg = ratio >= 0.85 ? "Harika! Çok iyi hazırlanmışsın. 🌟" : ratio >= 0.5 ? "Güzel! Yanlışlarına bakarak daha da iyi olabilirsin. 💪" : "Üzülme! Cevap anahtarındaki çözümlere birlikte bakalım. 📖";
    const points = Math.round(ratio * 100);
    return `
      <div class="center" style="padding-top:30px">
        <h2>Sınav bitti</h2>
        <div class="score ${cls}">${at.correct} / ${at.total}</div>
        <p>Puan: <b>${points}</b></p>
        <p>${msg}</p>
        <div class="actions" style="justify-content:center">
          <button class="primary" id="see-key" data-act="key">📋 Cevap anahtarı</button>
          <button id="retry" data-act="retry">🔁 Tekrar çöz</button>
          <button id="to-home" data-act="go" data-to="home">Ana sayfa</button>
        </div>
      </div>`;
  },

  key() {
    const rec = getExam(state.examId);
    const at = rec.attempts[rec.attempts.length - 1];
    const answers = at ? at.answers : [];
    const items = rec.exam.questions.map((q, n) => {
      const a = answers[n];
      const badge = a == null ? `<span class="badge empty">boş</span>`
        : a === q.correct ? `<span class="badge ok">doğru</span>` : `<span class="badge no">yanlış</span>`;
      const opts = q.choices.map((c, i) => {
        const cls = i === q.correct ? "correct" : i === a ? "wrong" : "";
        return `<li class="${cls}">${letter(i)}) ${esc(c)}${i === q.correct ? " ✓" : ""}</li>`;
      }).join("");
      return `
        <div class="keyitem focusable" tabindex="0" id="k${n}">
          <div class="qtext">${n + 1}. ${esc(q.text)} ${at ? badge : ""}</div>
          <div class="qbody">${figure(q.svg)}<div><ol>${opts}</ol></div></div>
          <div class="why"><b>Doğru cevap: ${letter(q.correct)}</b> — ${esc(q.explanation)}</div>
        </div>`;
    }).join("");
    const sources = rec.exam.sources.length
      ? `<div class="keyitem focusable sources" tabindex="0" id="ksrc"><b>Kaynaklar</b><br>${rec.exam.sources.map((s) => esc(s.title) + " — " + esc(s.url)).join("<br>")}</div>` : "";
    return `
      <div class="top"><h2>📋 Cevap anahtarı</h2><button id="key-back" data-act="key-back">Geri</button></div>
      ${items}${sources}`;
  },

  history() {
    const list = loadExams();
    const rows = list.map((r) => {
      const best = r.attempts.reduce((m, a) => Math.max(m, a.correct), -1);
      const total = r.exam.questions.length;
      const right = best >= 0 ? `En iyi: ${best}/${total}` : "Henüz çözülmedi";
      return `<button id="h-${r.id}" data-act="open" data-id="${r.id}"><span>${esc(r.params.grade)}. sınıf ${esc(r.params.subject)} · ${esc(r.params.period)}<br><span class="muted small">${fmtDate(r.createdAt)} · ${total} soru · ${esc(r.params.level)}</span></span><span class="muted">${right}</span></button>`;
    }).join("");
    return `
      <div class="top"><h2>🗂️ Geçmiş sınavlar</h2><button id="hist-back" data-act="go" data-to="home">Ana sayfa</button></div>
      ${list.length ? `<div class="list">${rows}</div>` : `<p class="muted">Henüz kayıtlı sınav yok. Ana sayfadan yeni bir sınav hazırlayın.</p>`}`;
  },

  detail() {
    const rec = getExam(state.examId);
    if (!rec) return SCREENS.history();
    const at = rec.attempts;
    return `
      <div class="top"><h2>${esc(rec.exam.title || "Deneme sınavı")}</h2><span class="muted">${fmtDate(rec.createdAt)}</span></div>
      <p>${esc(rec.params.grade)}. sınıf ${esc(rec.params.subject)} · ${esc(rec.params.period)} · ${rec.exam.questions.length} soru · ${esc(rec.params.level)}</p>
      ${rec.exam.topics.length ? `<p class="muted">Konular: ${rec.exam.topics.map(esc).join(", ")}</p>` : ""}
      <p class="muted">${at.length ? "Denemeler: " + at.map((a) => `${a.correct}/${a.total}`).join(", ") : "Henüz çözülmedi."}</p>
      <div class="actions">
        <button class="primary" id="d-solve" data-act="solve">▶ Çöz</button>
        <button id="d-key" data-act="key-detail">📋 Cevap anahtarı</button>
        <button class="danger" id="d-del" data-act="delete">🗑️ Sil</button>
        <button id="d-back" data-act="go" data-to="history">Geri</button>
      </div>`;
  },

  settings() {
    const key = hasKey();
    const hint = bridge() ? bridge().keyHint() : "";
    return `
      <div class="top"><h2>⚙️ Ayarlar</h2><button id="set-back" data-act="go" data-to="home">Ana sayfa</button></div>
      <div class="row"><div class="row-label">OpenAI API anahtarı</div>
        <p>${key ? `Kayıtlı ✅ <span class="muted">(${esc(hint)})</span>` : "Kayıtlı değil ❌"}</p>
        <input type="password" id="key" placeholder="sk-... (kumandayla yazmak yerine bilgisayardan da gönderebilirsiniz)">
        <div class="actions"><button id="save-key" data-act="save-key">Anahtarı kaydet</button></div>
        <p class="muted small" style="margin-top:10px">Bilgisayardan göndermek için: <code>adb shell am start -n com.ferhat.sinavasistani/.MainActivity --es api_key "sk-..."</code></p>
      </div>
      <div class="row"><div class="row-label">Model</div>
        <input type="text" id="model" value="${esc(model())}">
        <div class="actions"><button id="save-model" data-act="save-model">Modeli kaydet</button></div>
        <p class="muted small" style="margin-top:10px">Varsayılan: ${DEFAULT_MODEL}. Web aramasını destekleyen bir OpenAI modeli olmalı.</p>
      </div>
      ${state.error ? `<div class="notice">${esc(state.error)}</div>` : ""}`;
  },
};

function elapsedText() {
  const job = state.job;
  if (!job) return "";
  const s = Math.floor((Date.now() - job.startedAt) / 1000);
  return `Geçen süre: ${Math.floor(s / 60)} dk ${s % 60} sn`;
}
function updateElapsed() {
  const el = document.getElementById("elapsed");
  if (el) el.textContent = elapsedText();
}

/** İlk odaklanacak öğe her ekran için */
const FIRST_FOCUS = {
  home: "m-new", newExam: "make", loading: "cancel", quiz: "c0", result: "see-key",
  key: "k0", history: null, detail: "d-solve", settings: "key",
};

function render() {
  const keepId = state.focusId || (document.activeElement && document.activeElement.id) || null;
  const keepScroll = window.scrollY;
  const sameScreen = $app.dataset.screen === state.screen;
  $app.innerHTML = SCREENS[state.screen]();
  $app.dataset.screen = state.screen;
  let target = keepId && sameScreen ? document.getElementById(keepId) : null;
  if (state.focusId) target = document.getElementById(state.focusId);
  if (!target || target.disabled) {
    const first = FIRST_FOCUS[state.screen];
    target = (first && document.getElementById(first)) || focusables()[0];
  }
  state.focusId = null;
  // Yeni ekranda önce en üste çık, sonra odaklanan öğe görünür olacak şekilde kaydır.
  window.scrollTo(0, sameScreen ? keepScroll : 0);
  if (target) {
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest" });
  }
}

function go(screen) {
  state.screen = screen;
  if (screen !== "quiz") state.confirmFinish = false;
  render();
}

/* ---------- Tıklamalar ---------- */

$app.addEventListener("click", (ev) => {
  const el = ev.target.closest("[data-act]");
  if (!el || el.disabled) return;
  const act = el.dataset.act;
  switch (act) {
    case "go":
      state.error = "";
      go(el.dataset.to);
      break;
    case "opt": {
      const name = el.dataset.name;
      const raw = el.dataset.value;
      state.form[name] = typeof OPTIONS[name][0] === "number" ? Number(raw) : raw;
      state.focusId = el.id;
      render();
      break;
    }
    case "make": {
      state.form.note = (document.getElementById("note") || {}).value || "";
      if (!hasKey()) { state.error = "Önce Ayarlar ekranından OpenAI API anahtarını girin."; render(); break; }
      startGeneration();
      break;
    }
    case "cancel": cancelGeneration(); break;
    case "pick": pick(Number(el.dataset.i)); break;
    case "prev": if (state.qi > 0) { state.qi--; state.focusId = "c0"; render(); } break;
    case "next": state.qi++; state.focusId = "c0"; render(); break;
    case "finish": state.confirmFinish = true; render(); break;
    case "finish-no": state.confirmFinish = false; state.focusId = "finish"; render(); break;
    case "finish-yes": finishQuiz(); break;
    case "key": state.keyFrom = "result"; go("key"); break;
    case "key-detail": state.keyFrom = "detail"; go("key"); break;
    case "key-back": go(state.keyFrom); break;
    case "retry": openQuiz(state.examId); break;
    case "open": state.examId = el.dataset.id; go("detail"); break;
    case "solve": openQuiz(state.examId); break;
    case "delete": {
      saveExams(loadExams().filter((r) => r.id !== state.examId));
      go("history");
      break;
    }
    case "save-key": {
      const v = (document.getElementById("key").value || "").trim();
      state.error = v ? "" : "Anahtar boş olamaz.";
      if (v) bridge().setKey(v);
      render();
      break;
    }
    case "save-model": {
      const v = (document.getElementById("model").value || "").trim();
      bridge().setModel(v || DEFAULT_MODEL);
      state.error = "Model kaydedildi: " + (v || DEFAULT_MODEL);
      render();
      break;
    }
  }
});

/* ---------- Kumanda (yön tuşları) ile gezinme ---------- */

function focusables() {
  return Array.from($app.querySelectorAll("button, input, .focusable"))
    .filter((el) => !el.disabled && el.offsetParent !== null);
}

function moveFocus(dir) {
  const items = focusables();
  const cur = document.activeElement;
  if (!items.length) return;
  if (!cur || !items.includes(cur)) { items[0].focus(); return; }
  const r = cur.getBoundingClientRect();
  // İki dikdörtgen arasındaki boşluk (üst üste biniyorlarsa 0)
  const gap = (a1, a2, b1, b2) => Math.max(0, Math.max(a1, b1) - Math.min(a2, b2));
  let best = null, bestScore = Infinity;
  for (const el of items) {
    if (el === cur) continue;
    const b = el.getBoundingClientRect();
    let main, cross;
    if (dir === "down") { if (b.top < r.bottom - 4) continue; main = b.top - r.bottom; cross = gap(r.left, r.right, b.left, b.right); }
    else if (dir === "up") { if (b.bottom > r.top + 4) continue; main = r.top - b.bottom; cross = gap(r.left, r.right, b.left, b.right); }
    else if (dir === "right") { if (b.left < r.right - 4) continue; main = b.left - r.right; cross = gap(r.top, r.bottom, b.top, b.bottom); }
    else { if (b.right > r.left + 4) continue; main = r.left - b.right; cross = gap(r.top, r.bottom, b.top, b.bottom); }
    if ((dir === "left" || dir === "right") && cross > 0) continue; // yatayda yalnızca aynı satır
    const score = Math.max(main, 0) + cross * 3;
    if (score < bestScore) { bestScore = score; best = el; }
  }
  if (best) {
    best.focus({ preventScroll: true });
    best.scrollIntoView({ block: "nearest", behavior: "smooth" });
  } else if (dir === "down" || dir === "up") {
    window.scrollBy({ top: dir === "down" ? 200 : -200, behavior: "smooth" });
  }
}

document.addEventListener("keydown", (ev) => {
  const map = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };
  const dir = map[ev.key];
  if (!dir) return;
  const a = document.activeElement;
  if (a && a.tagName === "INPUT" && (dir === "left" || dir === "right")) {
    // Metin kutusunda sağ/sol imleci hareket ettirsin; kenardaysa dışarı çıksın.
    const atStart = a.selectionStart === 0 && a.selectionEnd === 0;
    const atEnd = a.selectionStart === a.value.length;
    if (!(dir === "left" && atStart) && !(dir === "right" && atEnd)) return;
  }
  ev.preventDefault();
  moveFocus(dir);
});

/* ---------- Android'den gelen çağrılar ---------- */

/** Geri tuşu: bir önceki ekrana döner. Ana sayfadaysa false döner ve uygulama kapanır. */
window.handleBack = function () {
  const s = state.screen;
  if (s === "home") return false;
  if (s === "loading") { cancelGeneration(); return true; }
  if (s === "quiz" && state.confirmFinish) { state.confirmFinish = false; render(); return true; }
  const back = { newExam: "home", quiz: "home", result: "home", key: state.keyFrom, history: "home", detail: "history", settings: "home" };
  state.error = "";
  go(back[s] || "home");
  return true;
};

window.onSettingsChanged = function () { render(); };

render();
