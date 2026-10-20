/* Canlı sesli görüşme — OpenAI GPT-Live (gpt-live-1).
   Ses, kullanıcının bilgisayarı ile OpenAI arasında doğrudan WebRTC ile akar; oturum kullanıcının kendi
   OpenAI anahtarıyla açılır (POST /v1/live/sessions, SDP teklifi → SDP cevabı). Olaylar "oai-events" veri
   kanalından gelir. Belge: developers.openai.com/api/docs/guides/live

     Canli.basla({ anahtar, talimat, ses, gecmis, selam, olay, devret })
       olay(tur, veri):  durum {kip, metin} · sure saniye · seviye {u, a} · konusmaBasi tur · konusma tur
                         hata metin · bitti {saniye, turlar}
       devret(soylenen, ara) → sonuç metni (söz)   Sesli asistan bir işi uygulamaya devrettiğinde çağrılır
                         (session.delegation.created); dönen metin session.commentary.append ile ona verilir, o da
                         kendi cümleleriyle söyler. ara(metin): iş sürerken ara bilgi verir.
     Canli.kapat()   Canli.sustur() → yeni durum   Canli.acik()   Canli.destek()   Canli.bilgi(metin, soyle) */
(function(){
'use strict';
var K = window.Kopru;
var MODEL = 'gpt-live-1';
var C = null, son = null, sira = 0;

function destek(){ return !!(window.RTCPeerConnection && navigator.mediaDevices && navigator.mediaDevices.getUserMedia); }
function kimlik(on){ return on + '_' + Date.now().toString(36) + (++sira); }
function gonder(o){ try { if (C && C.dc && C.dc.readyState === 'open') C.dc.send(JSON.stringify(o)); } catch (e) { } }
/* OpenAI tarafı ice-lite: yerel adaylar yeter, toplama bitmezse 2,5 sn sonra beklemeden devam edilir. */
function buzBitti(pc){
  return new Promise(function(r){
    if (pc.iceGatheringState === 'complete') { r(); return; }
    var z = setTimeout(r, 2500);
    pc.addEventListener('icegatheringstatechange', function(){ if (pc.iceGatheringState === 'complete') { clearTimeout(z); r(); } });
  });
}
function httpHatasi(y, j){
  var m = (j && j.error && j.error.message) || '';
  if (y.durum === 401) return 'OpenAI anahtarı kabul edilmedi. Ayarlardan anahtarı kontrol et.';
  if (y.durum === 429) return 'OpenAI hesabında bakiye ya da kota yetersiz. Hesabına bakiye yüklemen gerekebilir.';
  if (y.durum === 403 || y.durum === 404) return 'Bu OpenAI hesabında canlı ses modeli kullanılamıyor. ' + m.slice(0, 160);
  return 'Canlı görüşme başlatılamadı (' + y.durum + '). ' + m.slice(0, 160);
}

/* Ses seviyeleri: küre kullanıcının ve asistanın sesine göre hareket eder. */
function olcer(c, kim, akis){
  try {
    if (!c.actx) return;
    var an = c.actx.createAnalyser(); an.fftSize = 512;
    c.actx.createMediaStreamSource(akis).connect(an);
    c.an[kim] = an;
    if (c.raf) return;
    var tampon = new Uint8Array(512);
    var dongu = function(){
      if (c.bitti) return;
      var lv = { user: 0, asst: 0 };
      ['user', 'asst'].forEach(function(k){
        var a = c.an[k]; if (!a) return;
        a.getByteTimeDomainData(tampon);
        var t = 0; for (var i = 0; i < tampon.length; i++) { var v = (tampon[i] - 128) / 128; t += v * v; }
        lv[k] = Math.min(1, Math.sqrt(t / tampon.length) * 4);
      });
      if (c.sessiz) lv.user = 0;
      c.s.olay('seviye', { u: lv.user, a: lv.asst });
      c.raf = requestAnimationFrame(dongu);
    };
    c.raf = requestAnimationFrame(dongu);
  } catch (e) { }
}

function delta(c, kim, e){
  var d = e.delta || '';
  if (!d || c.bitti) return;
  var t = c.tur[kim];
  // 1,6 saniyeden uzun aradan sonra gelen söz yeni bir satır açar
  if (t && e.start_ms != null && t.sonMs != null && e.start_ms - t.sonMs > 1600) { t.kapali = true; t = null; }
  if (!t || t.kapali) {
    t = c.tur[kim] = { kim: kim, metin: '', kapali: false };
    c.turlar.push(t);
    c.s.olay('konusmaBasi', t);
  }
  t.metin += d;
  if (e.end_ms != null) t.sonMs = e.end_ms;
  c.s.olay('konusma', t);
  clearTimeout(t.z); t.z = setTimeout(function(){ t.kapali = true; }, 1800);
}

function olayIsle(c, e){
  c.gorulen[e.type] = (c.gorulen[e.type] || 0) + 1;   // tanı için: hangi olaydan kaç tane geldi
  if (e.type === 'error') c.sonHata = (e.error && (e.error.message || e.error.code)) || 'bilinmeyen hata';
  switch (e.type) {
    case 'session.started':
      c.basAt = Date.now();
      c.s.olay('durum', { kip: 'listen', metin: 'Dinliyorum' });
      c.sayac = setInterval(function(){ c.s.olay('sure', Math.floor((Date.now() - c.basAt) / 1000)); }, 1000);
      if (c.s.selam) gonder({ type: 'session.instructions.append', event_id: kimlik('selam'), delegation_id: null, content: c.s.selam });
      break;
    case 'session.input_transcript.delta': delta(c, 'user', e); break;
    case 'session.delegation.created':
      if (c.s.devret && e.delegation && e.delegation.target === 'client') {
        c.kuyruk.push(e.delegation.id);
        // olay, kullanıcının son kelimelerinin dökümünden önce gelebiliyor → kısa bekle
        setTimeout(function(){ devretCalis(c); }, 900);
      }
      break;
    case 'session.output_transcript.delta': delta(c, 'asst', e); break;
    case 'session.usage.updated': if (e.usage && e.usage.seconds != null) c.saniye = e.usage.seconds; break;
    case 'session.closed':
      if (e.usage && e.usage.seconds != null) c.saniye = e.usage.seconds;
      bitir(c);
      break;
  }
}

/* Devredilen iş: kullanıcının henüz işlenmemiş sözleri uygulamaya verilir, sonuç sesli asistana döner. */
function devretCalis(c){
  if (c.devrediyor || !c.kuyruk.length || c.bitti) return;
  var id = c.kuyruk.splice(0).pop();   // birikmiş devretmeler aynı sözle tek işte toplanır
  var sozler = c.turlar.filter(function(t){ return t.kim === 'user' && !t.devredildi && t.metin.trim(); });
  sozler.forEach(function(t){ t.devredildi = true; t.kapali = true; });
  var soylenen = sozler.map(function(t){ return t.metin.trim(); }).join(' ');
  var soyle = function(m){ if (!c.bitti && m) gonder({ type: 'session.commentary.append', event_id: kimlik('is'), delegation_id: id, content: String(m).slice(0, 1400) }); };
  c.devrediyor = true;
  c.s.olay('durum', { kip: 'think', metin: 'Çalışıyorum' });
  Promise.resolve().then(function(){ return soylenen ? c.s.devret(soylenen, soyle) : 'Kullanıcının ne istediği duyulamadı; bir kez daha söylemesini iste.'; })
    .then(soyle, function(e){ soyle('İşlem yapılamadı: ' + String((e && e.message) || e)); })
    .then(function(){
      c.devrediyor = false;
      if (c.bitti) return;
      c.s.olay('durum', { kip: 'listen', metin: c.sessiz ? 'Mikrofon kapalı' : 'Dinliyorum' });
      devretCalis(c);
    });
}

function bitir(c, hataMetni){
  if (c.bitti) return;
  c.bitti = true;
  clearInterval(c.sayac); clearTimeout(c.kapatZ);
  if (c.raf) cancelAnimationFrame(c.raf);
  try { if (c.mik) c.mik.getTracks().forEach(function(t){ t.stop(); }); } catch (e) { }
  try { if (c.ses) { c.ses.pause(); c.ses.srcObject = null; } } catch (e) { }
  try { if (c.pc) c.pc.close(); } catch (e) { }
  try { if (c.actx) c.actx.close(); } catch (e) { }
  if (C === c) C = null;
  var saniye = c.saniye || (c.basAt ? Math.round((Date.now() - c.basAt) / 1000) : 0);
  if (hataMetni) c.s.olay('hata', hataMetni);
  c.s.olay('bitti', { saniye: saniye, turlar: c.turlar.filter(function(t){ return t.metin.trim(); }) });
}

function basla(s){
  if (C) return;
  var c = C = { s: s, bitti: false, sessiz: false, basAt: 0, saniye: 0, an: {}, tur: { user: null, asst: null }, turlar: [], gorulen: {}, sonHata: '', kuyruk: [], devrediyor: false };
  son = c;
  // Ses bağlamı kullanıcının tıklaması içinde yaratılmalı (otomatik oynatma kuralı)
  try { c.actx = new (window.AudioContext || window.webkitAudioContext)(); c.actx.resume(); } catch (e) { }
  var pc = c.pc = new RTCPeerConnection();
  c.ses = new Audio(); c.ses.autoplay = true;
  pc.ontrack = function(e){
    var a = new MediaStream([e.track]);
    c.ses.srcObject = a; c.ses.play().catch(function(){ });
    olcer(c, 'asst', a);
  };
  pc.onconnectionstatechange = function(){ if (pc.connectionState === 'failed' && !c.bitti) bitir(c, 'Bağlantı koptu.'); };
  s.olay('durum', { kip: 'conn', metin: 'Mikrofon açılıyor' });
  navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }).then(function(mik){
    if (c.bitti) { mik.getTracks().forEach(function(t){ t.stop(); }); return; }
    c.mik = mik;
    mik.getAudioTracks().forEach(function(t){ pc.addTrack(t, mik); });
    olcer(c, 'user', mik);
    var dc = c.dc = pc.createDataChannel('oai-events');   // olay kanalı SDP teklifinden ÖNCE açılmalı
    dc.onmessage = function(ev){ var e; try { e = JSON.parse(ev.data); } catch (x) { return; } olayIsle(c, e); };
    dc.onclose = function(){ bitir(c); };
    s.olay('durum', { kip: 'conn', metin: 'Bağlanıyor' });
    return pc.createOffer().then(function(o){ return pc.setLocalDescription(o); })
      .then(function(){ return buzBitti(pc); })
      .then(function(){
        var oturum = { model: MODEL, instructions: s.talimat, audio: { output: { voice: s.ses || 'marin' } } };
        if (s.devret) oturum.delegation = { type: 'client' };   // işleri (bilgisayar komutları) uygulama yürütür
        if (s.gecmis && s.gecmis.length) oturum.input = s.gecmis;
        return K.http({ url: 'https://api.openai.com/v1/live/sessions', yontem: 'POST', sure: 30,
          basliklar: { authorization: 'Bearer ' + s.anahtar, 'content-type': 'application/json' },
          govde: JSON.stringify({ session: oturum, transport: { type: 'webrtc', sdp: pc.localDescription.sdp } }) });
      })
      .then(function(y){
        var j = null; try { j = JSON.parse(y.govde); } catch (e) { }
        if ((y.durum !== 200 && y.durum !== 201) || !j || !j.transport || !j.transport.sdp) throw new Error(httpHatasi(y, j));
        if (c.bitti) return;
        return pc.setRemoteDescription({ type: 'answer', sdp: j.transport.sdp });
      });
  }).catch(function(e){
    // İzin reddi düz hata değil: arayüz düzeltme kartı gösterir (izni yeniden sordurur, olmazsa ayar sayfasını açar)
    if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) { bitir(c); c.s.olay('izin'); return; }
    bitir(c, e && e.name === 'NotFoundError' ? 'Mikrofon bulunamadı.' : ((e && e.message) || 'Canlı görüşme başlatılamadı.'));
  });
}

function kapat(){
  var c = C;
  if (!c) return;
  gonder({ type: 'session.close', event_id: kimlik('kapat') });
  c.kapatZ = setTimeout(function(){ bitir(c); }, c.basAt ? 2500 : 0);   // session.closed gelmezse
}
function sustur(){
  var c = C;
  if (!c || !c.mik) return false;
  c.sessiz = !c.sessiz;
  c.mik.getAudioTracks().forEach(function(t){ t.enabled = !c.sessiz; });
  gonder({ type: c.sessiz ? 'session.input_audio.mute' : 'session.input_audio.unmute', event_id: kimlik('ses') });
  return c.sessiz;
}

/* Görüşme sürerken sesli asistana bilgi verir. 'soyle' yoksa sessizce bağlama eklenir (sorulursa kullanır);
   varsa asistan bunu kendi sözleriyle hemen söyler. */
function bilgi(metin, soyle){
  gonder({ type: soyle ? 'session.commentary.append' : 'session.instructions.append', event_id: kimlik('bilgi'), delegation_id: null, content: String(metin).slice(0, 1400) });
}

window.Canli = { destek: destek, basla: basla, kapat: kapat, sustur: sustur, bilgi: bilgi, acik: function(){ return !!C; },
  /* son oturumda sunucudan gelen olay türleri ve varsa son hata (sorun giderme için) */
  tani: function(){ return son ? { olaylar: son.gorulen, hata: son.sonHata } : null; } };
})();
