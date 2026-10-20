/* Çekirdekle (Rust) konuşan ince katman. Arayüzün geri kalanı Tauri'yi doğrudan çağırmaz. */
(function(){
'use strict';
var T = window.__TAURI__;
if (!T || !T.core) { document.body.textContent = 'Bu sayfa yalnız uygulamanın içinde çalışır.'; throw new Error('Tauri yok'); }
function c(komut, arg){ return T.core.invoke(komut, arg || {}); }
function pencere(){ return T.window.getCurrentWindow(); }

window.addEventListener('error', function(e){ c('gunluk', { metin: 'HATA ' + (e.message || '') + ' @ ' + String(e.filename || '').split('/').pop() + ':' + (e.lineno || 0) }).catch(function(){ }); });
window.addEventListener('unhandledrejection', function(e){ c('gunluk', { metin: 'HATA (söz) ' + String((e.reason && e.reason.message) || e.reason) }).catch(function(){ }); });

window.Kopru = {
  dosyaOku: function(ad){ return c('dosya_oku', { ad: ad }); },
  dosyaYaz: function(ad, veri){ return c('dosya_yaz', { ad: ad, veri: veri }); },
  sirOku: function(ad){ return c('sir_oku', { ad: ad }); },
  sirYaz: function(ad, deger){ return c('sir_yaz', { ad: ad, deger: deger || '' }); },
  /* { url, yontem, basliklar, govde, sure } → { durum, govde } */
  http: function(istek){ return c('http_istek', istek); },
  baglantiAc: function(url){ return c('baglanti_ac', { url: url }); },
  sistem: function(){ return c('sistem'); },
  konus: function(metin, ses, hiz){ return c('konus', { metin: metin, ses: ses || null, hiz: hiz || null }); },
  sus: function(){ return c('sus'); },
  sesler: function(){ return c('sesler'); },
  /* Cihaz içi yapay zekâ: istek yoksa durum ({ hazir, neden }), varsa { sistem, istem, enCok } → { metin } | { hata, tur } */
  yerelZeka: function(istek){ return c('yerel_zeka', { istek: istek ? JSON.stringify(istek) : null }); },
  otoBaslatOku: function(){ return c('oto_baslat_oku'); },
  otoBaslatYaz: function(acik){ return c('oto_baslat_yaz', { acik: !!acik }); },
  brifingZamani: function(){ return c('brifing_zamani'); },
  acilisSebebi: function(){ return c('acilis_sebebi'); },
  dinle: function(olay, f){ return T.event.listen(olay, function(e){ f(e.payload); }); },
  /* acik verilmezse durum tersine çevrilir; yeni durum (true/false) döner */
  tamEkran: function(acik){ return c('tam_ekran', { acik: acik == null ? null : !!acik }); },
  tamEkranMi: function(){ return c('tam_ekran_mi'); },
  gunluk: function(metin){ return c('gunluk', { metin: String(metin) }).catch(function(){ }); },
  /* bilgisayar komutları (ayrıntı: komut.js) */
  klasorler: function(){ return c('klasorler'); },
  uygulamalar: function(){ return c('uygulamalar'); },
  uygulamaAc: function(yol){ return c('uygulama_ac', { yol: yol }); },
  /* { ad, tur: 'klasor' | 'dosya' | null, uzantilar, kok } → [{ ad, yol, klasor, puan, degisim, boyut, ust }] */
  dosyaAra: function(a){ return c('dosya_ara', { ad: a.ad || '', tur: a.tur || null, uzantilar: a.uzantilar || null, kok: a.kok || null }); },
  yolAc: function(yol, goster){ return c('yol_ac', { yol: yol, goster: !!goster }); },
  copAc: function(){ return c('cop_ac'); },
  /* Silme iki adımlıdır: hazırla → (kullanıcı iki kez onaylar) → onayla. islem: 'cop_bosalt' | 'cope_tasi' */
  silmeHazirla: function(islem, yol){ return c('silme_hazirla', { islem: islem, yol: yol || null }); },
  silmeOnayla: function(kod){ return c('silme_onayla', { kod: kod }); },
  silmeVazgec: function(){ return c('silme_vazgec').catch(function(){ }); },
  /* Güç: 'uyut' | 'kilitle' (kapatma ve yeniden başlatma onaylıdır: silmeHazirla('kapat' | 'yeniden_baslat') → silmeOnayla) */
  guc: function(ne){ return c('guc', { ne: ne }); },
  /* Mikrofon izni verilmediyse: 'sifirla' → kayıtlı kararı siler, sistem yeniden sorar (yalnız Mac; olduysa true) · 'ayar' → sistemin mikrofon ayarını açar */
  mikrofonIzni: function(ne){ return c('mikrofon_izni', { ne: ne }); },
  /* Hatırlatıcılar: { no, metin, zaman (unix sn), caldi }. Vakti gelince çekirdek bildirim gösterir ve pencereyi 'hatirlatma' sebebiyle açar. */
  hatirlaticiKur: function(metin, saniye){ return c('hatirlatici_kur', { metin: metin || '', saniye: Math.round(saniye) }); },
  hatirlaticilar: function(){ return c('hatirlaticilar'); },
  hatirlaticiSil: function(no){ return c('hatirlatici_sil', { no: no }); },
  /* Güncelleme: denetle → null | { surum, simdiki, notlar, tarih } · kur → indirir, kurar, uygulamayı yeniden başlatır
     (indirme sürerken 'guncelleme-ilerleme' olayı: { inen, toplam }) */
  guncellemeDenetle: function(){ return c('guncelleme_denetle'); },
  guncellemeKur: function(){ return c('guncelleme_kur'); },
  surum: function(){ return T.app && T.app.getVersion ? T.app.getVersion() : Promise.resolve(''); },
  kapat: function(){ return pencere().close(); },
  kucult: function(){ return pencere().minimize(); }
};
})();