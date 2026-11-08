# Son Rapor – Xiaomi TV Box S (2. nesil) Hızlandırma

Tarih: 8 Kasım 2026
Cihaz: MiTV-AFKR0 (MDZ-28-AA), Google TV 11, yazılım `RTT0.211222.001/774`, 2 GB RAM
Yöntem: Windows PowerShell + ADB (ağ üzerinden). Root yok, sistem yazılımı değiştirilmedi.

## 1. Önce / sonra

| | Başlangıç | Son | Fark |
|---|---|---|---|
| Kullanılan RAM | 1.336 MB | 1.208 MB | −128 MB (yaklaşık %10) |
| Boş RAM | 831 MB | 932 MB | +101 MB |
| Boş depolama | 516 MB (%89 dolu) | **1,5 GB** (%63 dolu) | yaklaşık 3 kat |
| Kapalı uygulama | 1 | 13 | |
| Kaldırılan uygulama | – | 11 | |

RAM ölçümleri: başlangıç ve 9. adımdaki yeniden başlatma sonrası. Ayrıntılar `tv-yedek\ram-once.txt` ve `tv-yedek\ram-sonra.txt`.

## 2. Kapatılan sistem uygulamaları (geri açılabilir)

| Paket | Ne işe yarıyordu |
|---|---|
| com.miui.tv.analytics | Xiaomi kullanım analitiği |
| com.xiaomi.statistic | Xiaomi istatistik gönderici |
| com.google.android.feedback | Google geri bildirim gönderici |
| com.google.android.partnersetup | Google reklam ortaklığı takibi |
| com.mitv.tvhome.oemtab | Xiaomi reklam satırı |
| com.mitv.tvhome.michannel | Mi içerik satırları |
| com.mitv.tvhome.mitvplus | Mi TV+ reklamlı kanallar |
| com.mitv.tvhome.atv | PatchWall |
| com.xm.webcontent | Xiaomi tanıtım içerikleri |
| android.autoinstalls.config.xioami.mibox3 | Kendiliğinden uygulama kuran servis |
| com.google.android.marvin.talkback | Sesli ekran okuyucu |
| com.android.printspooler | Yazdırma servisi |
| com.google.android.youtube.tvmusic | YouTube Music (zaten kapalıydı, dokunulmadı) |

## 3. Kaldırılan uygulamalar (Play Store'dan tekrar yüklenebilir)

Exxen, MUBI, Bloomberg TV, GeForce NOW, Steam Link, Rally, Digger, Arçelik Chatbot, TCL Tarayıcı, VLC,
com.apgsolutionsllc.APGSOLUTIONSLLC0007.

## 4. Diğer değişiklikler

- Animasyonlar 0,5x (pencere, geçiş, animatör)
- Önbellekler temizlendi (`pm trim-caches`)
- YouTube kaldırılıp yeniden yüklendi (takılma sorunu çözüldü)
- **TV Bro** tarayıcı kuruldu (v2.1.6, resmî GitHub sürümü, SHA256 doğrulandı)
- **Projectivy Launcher** kuruldu. Home tuşu Projectivy'yi açıyor, Google TV ana ekranı kapatılmadı,
  kumanda kısayol tuşları çalışıyor.

## 5. Bilerek dokunulmayanlar

Play Store, Play Hizmetleri, Google Asistan, Chromecast, Netflix, YouTube, Prime Video, Play Oyunlar,
Xiaomi güncelleme servisi (kutu güncel kalsın diye), klavye, kumanda/Bluetooth, Wi-Fi, konum servisi,
USB medya uygulamaları, Google TV ana ekranı ve kurulum sihirbazı.

## 6. Geri alma

Bilgisayarda yedek klasörü: `C:\Users\ferha\tv-yedek`

Her şeyi eski haline getirmek için (USB hata ayıklama açıkken):

```
cd "$env:USERPROFILE\adb\platform-tools"
.\adb connect 192.168.1.103:5555
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\tv-yedek\geri-al.ps1"
```

Tek bir uygulamayı geri açmak için: `.\adb shell pm enable <paket adı>`

Bilgisayar olmadan: Ayarlar → Uygulamalar → (uygulama) → Etkinleştir.

Projectivy'den vazgeçmek için: Ayarlar → Erişilebilirlik → Projectivy Launcher → Kapat (veya uygulamayı kaldır).

## 7. Hatırlatmalar

- İşlem bitince **USB hata ayıklama kapatıldı** (ağdaki başka cihazların kutuya bağlanmasını önlemek için).
  Tekrar gerekirse: Ayarlar → Sistem → Geliştirici seçenekleri → USB hata ayıklama.
- Kutu "Rastgele MAC" kullandığı için IP adresi ileride değişebilir. Bağlanılamazsa
  Ayarlar → Ağ ve İnternet bölümünden yeni IP'ye bakılmalı.
- Boş depolamayı 1,5 GB civarında tutmak takılmaları önler.

## Sonraya kalanlar

- Televizyon 4K ise çözünürlüğü 4K 60Hz yapmak (şu an 1080p 60Hz)
- Alternatif uygulama marketi (F-Droid / Downloader önerildi)
- USB diskteki fotoğrafları yüzlere göre klasörleyen uygulama
