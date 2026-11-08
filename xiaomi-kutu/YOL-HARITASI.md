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

- [x] 1. Kutuda Geliştirici seçeneklerini açmak
- [x] 2. Kutuda USB hata ayıklamayı açmak, IP adresini öğrenmek
- [x] 3. Bilgisayara ADB (Google Platform Tools) kurmak
- [x] 4. Bilgisayardan kutuya bağlanmak (`adb connect <IP>:5555`, kutuda "İzin ver")
- [x] 5. Yedek ve ilk RAM ölçümü, `geri-al.ps1` dosyasını başlatmak
- [x] 6. Uygulama listesini çıkarıp gruplara ayırmak, onayınızı almak
      (başlangıç noktası: `KAPATMA-LISTESI.md`, cleanyourtv'nin bu kutu için denenmiş listesi)
      (1) takip/reklam ölçümü, (2) reklam ve öneri servisleri, (3) gereksiz arka plan servisleri,
      (4) hazır gelen uygulamalar, (5) size bağlı olanlar, (6) dokunulmayacaklar
- [ ] 7. Grupları sırayla kapatmak, her gruptan sonra kontrol
- [ ] 8. Animasyonları 0,5x yapmak
- [ ] 9. Önbellekleri temizlemek (`pm trim-caches 999G`)
- [ ] 10. (İsteğe bağlı) Ana ekranı değiştirmek: önce "Yalnızca uygulamalar" modu denenir. Yetmezse
      FLauncher kurulur, sonra hem `launcherx` hem `setupwraith` kapatılır. Wi-Fi şifresi bir kez
      yeniden istenir ve kumandanın Netflix/YouTube tuşları çalışmaz hale gelir.
- [ ] 11. Normal ayarlar: içerik kare hızını eşleştirme, çözünürlük, ekran koruyucu
- [x] 12. Yeniden başlatma, son kontrol, ikinci RAM ölçümü

## Sonunda elimizde olacaklar

1. Önce/sonra RAM tablosu
2. Kapatılan uygulamalar listesi ve her birinin ne işe yaradığı
3. Her şeyi tek seferde geri alan `geri-al.ps1`
4. Bir şey bozulursa USB hata ayıklamayı kapatma hatırlatması

## İlerleme kaydı

- Kutu: MiTV-AFKR0, yazılım `Xiaomi/jaws/jaws:11/RTT0.211222.001/774`, IP 192.168.1.103
- İlk ölçüm (önce): Kullanılan RAM 1.336 MB, boş RAM 831 MB (toplam 2,0 GB)
- Kalacaklar (kullanıcı tercihi): Prime Video, Netflix, YouTube, Google Asistan, Chromecast, Play Oyunlar
- 1. grup kapatıldı (10 paket): com.miui.tv.analytics, com.xiaomi.statistic, com.google.android.feedback,
  com.google.android.partnersetup, com.mitv.tvhome.oemtab, com.mitv.tvhome.michannel,
  com.mitv.tvhome.mitvplus, com.mitv.tvhome.atv, com.xm.webcontent,
  android.autoinstalls.config.xioami.mibox3. TV kontrolü: Home, YouTube, Netflix, Wi-Fi çalışıyor.
- 2. grup adayları: com.google.android.marvin.talkback (onaylandı), com.android.printspooler,
  kullanılmayan üçüncü taraf uygulamalar (kullanıcıya soruldu)
- 2. grup kapatıldı (2 paket): com.google.android.marvin.talkback, com.android.printspooler
- Animasyonlar 0.5x yapıldı (window, transition, animator)
- 3. grup kapatıldı (6 paket, kullanıcının sonradan yüklediği uygulamalar): com.exxen.android, com.mubi,
  com.bloomberg.btva, com.nvidia.geforcenow, com.valvesoftware.steamlink, com.refuelgames.rally
- 4. grup kapatıldı (5 paket): dk.logisoft.digger, com.arcelik.chatbot, com.tcl.browser, org.videolan.vlc,
  com.apgsolutionsllc.APGSOLUTIONSLLC0007
- Toplam kapalı paket: 24 (23 bizim + önceden kapalı YouTube Music). TV kontrolü: Home, YouTube, Netflix,
  Prime Video, Disney+/TOD, sesli arama, Wi-Fi çalışıyor.
- 9. adım: `pm trim-caches` ile boş depolama 516 MB -> 955 MB. Yeniden başlatma sonrası RAM:
  kullanılan 1.336 MB -> 1.208 MB, boş 831 MB -> 932 MB. 24 kapalı paket yerinde.
- YouTube takılması: kullanıcı YouTube'u kaldırıp yeniden yükledi, düzeldi.
- 11.1: Bu yazılımda (Google TV 11) "İçerik kare hızını eşleştir" yok, atlandı.

## Kalan sıra (kullanıcı kararı)

- [x] 12. Tarayıcı: TV Bro (kumandaya uygun, açık kaynak). Play Store'da yoksa resmî GitHub sürümü
      (github.com/truefedex/tv-bro) `adb install` ile.
- [x] 13. Projectivy Launcher (Yol 2): Google TV ana ekranı KAPATILMADAN Home tuşunu yönlendirme
      özelliğiyle. Kumandanın Netflix/YouTube tuşları çalışmaya devam eder.
- [x] 14. Çözünürlük kontrolü, kullanılmayan 11 uygulamayı kaldırıp yer açma (kullanıcıya soruldu)
- [ ] 15. Son: USB hata ayıklamayı kapatmak, son rapor
- 12: TV Bro v2.1.6 (geckoExcluded, 6,5 MB, SHA256 doğrulandı) `adb install` ile kuruldu, çalışıyor.
- 13: Projectivy Launcher (com.spocky.projengmenu) Play Store'dan kuruldu, "Mevcut başlatıcıyı geçersiz kıl"
  + erişilebilirlik izniyle Home tuşu Projectivy'yi açıyor. YouTube, Netflix ve kumanda kısayol tuşları çalışıyor.
  Google TV ana ekranı (launcherx) kapatılmadı.
- 14: Çözünürlük 1080p 60Hz (TV'nin 4K olup olmadığı soruldu). Kullanıcı onayıyla 11 üçüncü taraf uygulama
  `adb uninstall` ile kaldırıldı. Boş depolama 544 MB -> 1,5 GB. Kapalı paket: 13. geri-al.ps1 güncellendi.
- Son rapor: `SON-RAPOR.md`
