# Xiaomi TV Box S (2. nesil) – Hızlandırma Yol Haritası

Cihaz: Xiaomi TV Box S (2nd Gen), model MDZ-28-AA, Google TV, 2 GB RAM, 8 GB depolama.
Bilgisayar: Windows (PowerShell).

## Kurallarımız (örnek prompttan öğrendiklerimiz)

1. **Hiçbir şey silinmez.** Sadece `pm disable-user --user 0` ile kapatılır, `pm enable` ile geri açılır. `pm uninstall` yasak.
2. **Root, bootloader açma, özel ROM yok.** Netflix HD (Widevine L1) kaybolabilir; kazancı yok.
3. **Önce yedek ve ölçüm.** Değişiklikten önce paket listesi, ayarlar ve RAM kullanımı `tv-yedek` klasörüne kaydedilir. Sonunda RAM tekrar ölçülür, önce/sonra tablosu çıkarılır.
4. **Geri alma dosyası baştan hazırlanır** (`geri-al.ps1`). Kapatılan her uygulama anında bu dosyaya ve `kapatilanlar.txt` dosyasına yazılır.
5. **Küçük gruplar.** Bir seferde en fazla 10 uygulama, her komut ayrı ayrı çalıştırılır.
6. **Her gruptan sonra kontrol.** Ana ekran açılıyor mu, Wi-Fi bağlı mı, kumanda çalışıyor mu, Netflix ve YouTube açılıyor mu? Bozulursa son grup geri açılır, sonra tek tek denenir.
7. **Dokunulmayacaklar:**
   - Play Store ve Play Hizmetleri: `com.android.vending`, `com.google.android.gms`, `com.google.android.gsf`
   - Konum servisi: `com.android.location.fused` (kapatılırsa kutu açılışta takılı kalır)
   - Ekran klavyesi (`*.inputmethod.*`)
   - Kumanda ve Bluetooth servisleri
   - Wi-Fi ve ağ ayarlarıyla ilgili servisler
   - Mevcut ana ekran (yenisi kurulup varsayılan yapılana kadar)
   - Adı belirsiz bir paket önce `dumpsys package <ad>` ile incelenir; yine belirsizse kapatılmaz.
8. **Size bağlı olanlar sorulur:** Sesli asistan, Chromecast, yayın uygulamaları, sistem güncellemesi. Listeden işaretlemedikleriniz kapatılmaz.
9. **Windows notu:** Ekran görüntüsü için `adb exec-out screencap -p > shot.png` kullanılmaz (PowerShell 5.1'de dosya bozulur). Bunun yerine:
   `adb shell screencap -p /sdcard/shot.png` ve `adb pull /sdcard/shot.png`
10. **USB:** İşlem sırasında kutudaki USB disk çıkarılır. Sorun olursa sonunda USB hata ayıklama kapatılır.

## Adımlar

- [ ] 1. Kutuda Geliştirici seçeneklerini açmak
- [ ] 2. Kutuda USB hata ayıklamayı açmak, IP adresini öğrenmek
- [ ] 3. Bilgisayara ADB (Google Platform Tools) kurmak
- [ ] 4. Bilgisayardan kutuya bağlanmak (`adb connect <IP>:5555`, kutuda "İzin ver")
- [ ] 5. Yedek ve ilk RAM ölçümü, `geri-al.ps1` dosyasını başlatmak
- [ ] 6. Uygulama listesini çıkarıp gruplara ayırmak, onayınızı almak
      (1) takip/reklam ölçümü, (2) reklam ve öneri servisleri, (3) gereksiz arka plan servisleri,
      (4) hazır gelen uygulamalar, (5) size bağlı olanlar, (6) dokunulmayacaklar
- [ ] 7. Grupları sırayla kapatmak, her gruptan sonra kontrol
- [ ] 8. Animasyonları 0,5x yapmak
- [ ] 9. Önbellekleri temizlemek (`pm trim-caches 999G`)
- [ ] 10. FLauncher kurmak, varsayılan ana ekran yapmak, sonra Google TV ana ekranını kapatmak
- [ ] 11. Normal ayarlar: içerik kare hızını eşleştirme, çözünürlük, ekran koruyucu
- [ ] 12. Yeniden başlatma, son kontrol, ikinci RAM ölçümü

## Sonunda elimizde olacaklar

1. Önce/sonra RAM tablosu
2. Kapatılan uygulamalar listesi ve her birinin ne işe yaradığı
3. Her şeyi tek seferde geri alan `geri-al.ps1`
4. Bir şey bozulursa USB hata ayıklamayı kapatma hatırlatması
