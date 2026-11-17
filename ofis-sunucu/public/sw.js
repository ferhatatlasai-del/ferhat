// Ofis bildirimleri (web push). Sunucu yayınlandığında ya da sorun olduğunda bildirim gönderir.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { baslik: 'Ajan ofisi', govde: e.data ? e.data.text() : '' }; }
  const secenek = { body: d.govde || '', tag: (d.etiket || 'ajan') + '-' + Date.now(), data: { adres: d.adres || '/' } };
  if (d.gorsel) secenek.image = d.gorsel;
  e.waitUntil(self.registration.showNotification(d.baslik || 'Ajan ofisi', secenek));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const adres = (e.notification.data && e.notification.data.adres) || '/';
  e.waitUntil(self.clients.openWindow(adres));
});
