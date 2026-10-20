/* Hologram çekirdeği: parçacık küresi + HUD halkaları + arka plan parçacıkları + yazının "çözülerek" gelmesi.
   Gurizon Asistan'ın Hologram görünümünden uyarlandı.
     Kure.durum(mod, etiket?, alt?)   idle | conn | think | speak | listen (canlı görüşme)
     Kure.seviye(kullanici, asistan)  canlı görüşmede ses seviyeleri (0-1)
     Kure.vurus('ok'|'err')           kısa halka vuruşu
     Kure.coz(el, kaydirilan?)        el içindeki metin harf harf çözülür
   Yormama: pencere görünmüyorken çizim durur; boşta 30, odak dışında 12 kare/sn. */
(function(){
'use strict';
var $ = function(s){ return document.querySelector(s); };
var core = $('#cekirdek'), cv = $('#kureCv'), bg = $('#arka');
var cx = cv.getContext('2d'), bgx = bg.getContext('2d');
var reduced = false;
try { reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { }

var ETIKET = { idle: 'Sistem hazır', conn: 'Kaynaklar taranıyor', think: 'İşleniyor', speak: 'Konuşuyor', listen: 'Dinliyorum' };
var ALT = { idle: 'komut bekleniyor', conn: 'haber · hava · piyasa', think: 'cevap hazırlanıyor', speak: 'durdurmak için ses düğmesi', listen: 'canlı görüşme' };
var S = { mode: 'idle', tA: 0, lvA: 0, tU: 0, lvU: 0, dU: 0, dA: 0, e: 0, pulse: 0, pulseKind: '', waves: [], lastWave: 0 };

var K = window.Kure = {};
K.durum = function(mod, etiket, alt){
  if (!ETIKET[mod]) mod = 'idle';
  S.mode = mod;
  $('#kureDurum').textContent = etiket || ETIKET[mod];
  $('#kureAlt').textContent = alt || ALT[mod];
  core.className = mod;
  basla();
};
K.seviye = function(u, a){ S.dU = Math.max(0, Math.min(1, u || 0)); S.dA = Math.max(0, Math.min(1, a || 0)); };
K.vurus = function(tur){ S.pulse = 1; S.pulseKind = tur === 'err' ? 'err' : 'ok'; basla(); };

var dpr = Math.min(2, window.devicePixelRatio || 1);
var W = 1, H = 1, BW = 1, BH = 1;
function boyut(){
  var r = core.getBoundingClientRect();
  W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
  cv.width = W * dpr; cv.height = H * dpr; cx.setTransform(dpr, 0, 0, dpr, 0, 0);
  BW = window.innerWidth; BH = window.innerHeight;
  bg.width = BW * dpr; bg.height = BH * dpr; bgx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
boyut();
window.addEventListener('resize', boyut);
if (window.ResizeObserver) new ResizeObserver(boyut).observe(core);

/* Küre: Fibonacci dağılımlı noktalar; bir alt kümesi 3B komşuluğa göre çizgilerle bağlanır */
var N = 340, P = [], i, j;
for (i = 0; i < N; i++) {
  var y = 1 - (i / (N - 1)) * 2, rr = Math.sqrt(Math.max(0, 1 - y * y)), ph = i * 2.399963;
  P.push({ x: Math.cos(ph) * rr, y: y, z: Math.sin(ph) * rr, s: 0.6 + Math.random() * 0.9, o: Math.random() * 6.283 });
}
var ALTK = [], BAG = [];
for (i = 0; i < N; i += 4) ALTK.push(i);
for (i = 0; i < ALTK.length; i++) {
  for (j = i + 1; j < ALTK.length; j++) {
    var a0 = P[ALTK[i]], b0 = P[ALTK[j]], dx = a0.x - b0.x, dy = a0.y - b0.y, dz = a0.z - b0.z;
    if (dx * dx + dy * dy + dz * dz < 0.2) BAG.push([ALTK[i], ALTK[j]]);
  }
}
var PR = new Float32Array(N * 3);
var BN = 90, BP = [], mx = 0, my = 0;
for (i = 0; i < BN; i++) BP.push({ x: Math.random(), y: Math.random(), z: 0.3 + Math.random() * 0.7, o: Math.random() * 6.283, v: 0.004 + Math.random() * 0.012 });
window.addEventListener('mousemove', function(e){ mx = e.clientX / BW - 0.5; my = e.clientY / BH - 0.5; }, { passive: true });

var CAM = [94, 231, 255], BEYAZ = [255, 255, 255], OK = [61, 220, 151], ERR = [255, 77, 61], UYARI = [255, 179, 71];
function kar(a, b, t){ t = Math.max(0, Math.min(1, t)); return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function rgba(c, al){ return 'rgba(' + (c[0] | 0) + ',' + (c[1] | 0) + ',' + (c[2] | 0) + ',' + Math.max(0, Math.min(1, al)).toFixed(3) + ')'; }
function halka(r, a0, a1, w, col, al, dash){
  cx.beginPath(); cx.setLineDash(dash || []); cx.lineWidth = w; cx.strokeStyle = rgba(col, al);
  cx.arc(0, 0, r, a0, a1); cx.stroke(); cx.setLineDash([]);
}

var rot = 0;
function cizKure(t, dt){
  cx.clearRect(0, 0, W, H);
  var m = S.mode, think = m === 'think' ? 1 : 0, conn = m === 'conn';
  // canlı görüşmede gerçek seviyeler gelir; brifing okunurken (sistem sesi) hece ritmine benzer bir zarf üretilir
  S.tA = m === 'listen' ? S.dA : (m === 'speak' ? 0.25 + 0.55 * Math.abs(Math.sin(t * 6.1) * Math.sin(t * 2.3 + 1)) : 0);
  S.tU = m === 'listen' ? S.dU : 0;
  S.lvA += (S.tA - S.lvA) * (S.tA > S.lvA ? 0.5 : 0.1);
  S.lvU += (S.tU - S.lvU) * (S.tU > S.lvU ? 0.55 : 0.09);
  S.e += ((think ? 0.55 : 0) + S.lvA * 0.9 + S.lvU * 0.4 + (conn ? 0.25 : 0) - S.e) * 0.07;
  var e = S.e, col = conn ? kar(CAM, UYARI, 0.6) : CAM;
  if (S.pulse > 0) { S.pulse = Math.max(0, S.pulse - dt * 1.3); col = kar(col, S.pulseKind === 'err' ? ERR : OK, S.pulse * 0.85); }
  // alttaki 40 px durum yazısına ayrılır; halkalar ve ışıma tuvalin içinde kalsın
  var R = Math.min(W, H - 40) * 0.5 * 0.55;
  if (R < 8) return;
  rot += dt * (0.22 + think * 0.9 + S.lvA * 0.7 + (conn ? 0.5 : 0));
  var tx = 0.42 + Math.sin(t * 0.15) * 0.12, cr = Math.cos(rot), sr = Math.sin(rot), ct = Math.cos(tx), st = Math.sin(tx);
  cx.save(); cx.translate(W / 2, (H - 40) / 2 + 2);

  var gr = R * 1.75 * (1 + e * 0.2), g = cx.createRadialGradient(0, 0, R * 0.2, 0, 0, gr);
  g.addColorStop(0, rgba(col, 0.20 + e * 0.16)); g.addColorStop(0.55, rgba(col, 0.06 + e * 0.05)); g.addColorStop(1, rgba(col, 0));
  cx.fillStyle = g; cx.beginPath(); cx.arc(0, 0, gr, 0, 6.2832); cx.fill();

  var Rs = R * (1 + e * 0.06 + (think ? 0.025 * Math.sin(t * 9) : 0)), i;
  for (i = 0; i < N; i++) {
    var p = P[i], x1 = p.x * cr + p.z * sr, z1 = -p.x * sr + p.z * cr, y2 = p.y * ct - z1 * st, z2 = p.y * st + z1 * ct;
    var jit = think ? 1 + Math.sin(t * 7 + p.o) * 0.05 : 1 + Math.sin(t * 1.7 + p.o) * 0.012 + S.lvA * Math.sin(t * 12 + p.o) * 0.06;
    PR[i * 3] = x1 * Rs * jit; PR[i * 3 + 1] = y2 * Rs * jit; PR[i * 3 + 2] = (z2 + 1) / 2;
  }
  cx.lineWidth = 0.7;
  for (i = 0; i < BAG.length; i++) {
    var l = BAG[i], a = l[0] * 3, b = l[1] * 3, d = (PR[a + 2] + PR[b + 2]) / 2;
    cx.strokeStyle = rgba(col, (0.04 + 0.22 * d * d) * (1 + think * 0.8)); cx.beginPath(); cx.moveTo(PR[a], PR[a + 1]); cx.lineTo(PR[b], PR[b + 1]); cx.stroke();
  }
  for (i = 0; i < N; i++) {
    var dpt = PR[i * 3 + 2], sz = (0.5 + 1.5 * dpt) * P[i].s;
    cx.fillStyle = rgba(kar(col, BEYAZ, dpt * 0.5), 0.12 + 0.85 * dpt * dpt);
    cx.beginPath(); cx.arc(PR[i * 3], PR[i * 3 + 1], sz, 0, 6.2832); cx.fill();
  }
  var cR = R * 0.15 * (1 + 0.12 * Math.sin(t * 2.2) + e * 0.35), cg = cx.createRadialGradient(0, 0, 0, 0, 0, cR);
  cg.addColorStop(0, rgba(BEYAZ, 0.95)); cg.addColorStop(0.35, rgba(kar(col, BEYAZ, 0.4), 0.7)); cg.addColorStop(1, rgba(col, 0));
  cx.fillStyle = cg; cx.beginPath(); cx.arc(0, 0, cR, 0, 6.2832); cx.fill();

  // dört yay: kullanıcı konuşunca genişler ve beyazlaşır
  var r1 = R * 1.16 * (1 + S.lvU * 0.14), a1 = t * 0.35, colU = kar(col, BEYAZ, S.lvU * 0.8);
  for (i = 0; i < 4; i++) halka(r1, a1 + i * 1.5708, a1 + i * 1.5708 + 1.15, 1.2, colU, 0.5 + S.lvU * 0.4);
  cx.save(); cx.rotate(-t * 0.12); halka(R * 1.28, 0, 6.2832, 1, col, 0.28, [3, 10]); cx.restore();
  cx.save(); cx.rotate(t * 0.04); cx.lineWidth = 1;
  for (i = 0; i < 72; i++) {
    var ang = i / 72 * 6.2832, L = (i % 6 === 0) ? 9 : 4, r3 = R * 1.40, ca = Math.cos(ang), sa = Math.sin(ang);
    cx.strokeStyle = rgba(col, i % 6 === 0 ? 0.6 : 0.28); cx.beginPath(); cx.moveTo(ca * r3, sa * r3); cx.lineTo(ca * (r3 + L), sa * (r3 + L)); cx.stroke();
  }
  cx.restore();
  if (think || conn) {
    var sw = t * (conn ? 3.4 : 2.6);
    halka(R * 1.28, sw, sw + 1.6, 2, kar(col, BEYAZ, 0.3), 0.9);
    halka(R * 1.28, sw - 0.9, sw, 2, col, 0.35);
    halka(R * 1.16, -sw * 0.7, -sw * 0.7 + 0.8, 1.5, col, 0.6);
  }
  var orb = [[0.6, 0.32, 0.9, 1.55], [-0.95, 0.26, -0.65, 1.62]];
  for (i = 0; i < orb.length; i++) {
    var o = orb[i];
    cx.save(); cx.rotate(o[0]); cx.scale(1, o[1]); halka(R * o[3], 0, 6.2832, 0.8, col, 0.16); cx.restore();
    var oa = t * o[2] + i * 2, ox = Math.cos(oa) * R * o[3], oy = Math.sin(oa) * R * o[3] * o[1];
    var sx = ox * Math.cos(o[0]) - oy * Math.sin(o[0]), sy = ox * Math.sin(o[0]) + oy * Math.cos(o[0]);
    cx.save(); cx.shadowBlur = 12; cx.shadowColor = rgba(col, 0.9); cx.fillStyle = rgba(kar(col, BEYAZ, 0.5), 0.9);
    cx.beginPath(); cx.arc(sx, sy, 2.2, 0, 6.2832); cx.fill(); cx.restore();
  }
  if (S.lvA > 0.08 && t - S.lastWave > 0.3) { S.lastWave = t; S.waves.push({ r: R * 1.05, a: 0.4 + S.lvA * 0.45 }); }
  for (i = S.waves.length - 1; i >= 0; i--) {
    var w = S.waves[i]; w.r += dt * R * 1.3; w.a -= dt * 0.85;
    if (w.a <= 0.01) { S.waves.splice(i, 1); continue; }
    halka(w.r, 0, 6.2832, 1.2, col, w.a);
  }
  if (S.pulse > 0) halka(R * (1.2 + (1 - S.pulse) * 0.55), 0, 6.2832, 2, S.pulseKind === 'err' ? ERR : OK, S.pulse * 0.8);
  cx.restore();
}

function cizArka(t, dt){
  bgx.clearRect(0, 0, BW, BH);
  for (var i = 0; i < BN; i++) {
    var p = BP[i];
    p.y -= p.v * dt * p.z;
    if (p.y < -0.02) { p.y = 1.02; p.x = Math.random(); }
    var tw = 0.5 + 0.5 * Math.sin(t * 1.3 + p.o), x = p.x * BW - mx * 40 * p.z, y = p.y * BH - my * 40 * p.z;
    bgx.fillStyle = 'rgba(160,230,255,' + (0.06 + 0.3 * tw * p.z).toFixed(3) + ')';
    bgx.beginPath(); bgx.arc(x, y, 0.6 + p.z * 1.3, 0, 6.2832); bgx.fill();
  }
}

/* ---- döngü ---- */
var son = performance.now(), raf = 0, odak = true;
function hedefAralik(){ return !odak ? 1000 / 12 : (S.mode === 'idle' && S.pulse <= 0 ? 1000 / 30 : 0); }
function kare(simdi){
  raf = 0;
  if (document.hidden) return;
  var gecen = simdi - son;
  if (gecen >= hedefAralik() - 1) {
    var dt = Math.min(0.1, gecen / 1000); son = simdi;
    if (!reduced) cizArka(simdi / 1000, dt);
    cizKure(simdi / 1000, reduced ? 0.004 : dt);
  }
  raf = requestAnimationFrame(kare);
}
function basla(){ if (!raf && !document.hidden) { son = performance.now(); raf = requestAnimationFrame(kare); } }
document.addEventListener('visibilitychange', basla);
window.addEventListener('focus', function(){ odak = true; });
window.addEventListener('blur', function(){ odak = false; });
basla();

/* ---- yazı: harfler çözülerek gelir ---- */
var GL = '01<>/\\|=+*#%&$@?!;:[]{}()~^ABCDEFGHJKLMNPQRSTUVWXYZ0123456789';
K.coz = function(el, kaydirilan){
  if (reduced || !el) return;
  var dugumler = [], toplam = 0;
  (function gez(n){
    if (n.nodeType === 3) { if (n.nodeValue.trim()) { dugumler.push(n); toplam += n.nodeValue.length; } return; }
    if (n.nodeType !== 1 || n.classList.contains('kn') || n.classList.contains('et') || n.tagName === 'DETAILS') return;
    for (var c = n.firstChild; c; c = c.nextSibling) gez(c);
  })(el);
  if (!dugumler.length || toplam > 2400) return;
  dugumler.forEach(function(n){ n._f = n.nodeValue; n.nodeValue = ''; });
  var t0 = performance.now(), sure = Math.min(1600, 260 + toplam * 3);
  (function adim(simdi){
    var p = Math.min(1, (simdi - t0) / sure), kes = Math.floor(toplam * (1 - Math.pow(1 - p, 2))), acc = 0;
    dugumler.forEach(function(n){
      var s = n._f, st = acc; acc += s.length;
      var k = Math.max(0, Math.min(s.length, kes - st)), out = s.slice(0, k), ex = Math.min(s.length - k, 6);
      for (var i = 0; i < ex; i++) { var ch = s.charAt(k + i); out += (ch === ' ' || ch === '\\n') ? ch : GL.charAt((Math.random() * GL.length) | 0); }
      n.nodeValue = out;
    });
    if (kaydirilan) kaydirilan.scrollTop = kaydirilan.scrollHeight;
    if (p < 1) requestAnimationFrame(adim); else dugumler.forEach(function(n){ n.nodeValue = n._f; });
  })(t0);
};
})();