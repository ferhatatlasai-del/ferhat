# Ajan Ofisi sunucusu (Fly.io)

Kalıp Takip uygulamasından **tamamen ayrı** bir Fly uygulaması: `gurtechs-ajan-ofisi`.
Ofis sayfasını sunar ve GitHub'daki içerik ajanını (`icerik-direktif.yml`) çalıştırıp durumunu okur.

## Güvenlik
- GitHub anahtarı ve ofis şifresi **yalnızca Fly gizli anahtarı** olarak durur, depoda yoktur.
- Yanlış şifreye hız sınırı vardır; saatte en fazla 12 direktif kabul edilir.
- Ajan yalnızca **taslak yazar**. Yayın hâlâ ayrı iş akışlarında ve onay (EVET) ister.
- Müşteri verisi, Kalıp Takip diski ya da anahtarları bu uygulamaya hiçbir zaman bağlanmaz.

## Kurulum (bir kez, kendi bilgisayarında)
1. `fly apps create gurtechs-ajan-ofisi` (ad alınmışsa farklı bir ad seç; `fly.toml` ve `.github/workflows/fly-yukle.yml` içindeki adı da değiştir)
2. `fly tokens create deploy -a gurtechs-ajan-ofisi` çıktısını GitHub > Settings > Secrets > Actions içine **FLY_API_TOKEN** olarak yaz.
3. GitHub'da yalnızca bu depoya erişen, **Actions: Read and write** ve **Contents: Read** izinli bir "fine-grained" anahtar üret.
4. `fly secrets set -a gurtechs-ajan-ofisi GITHUB_TOKEN=... PANEL_SIFRE=...` (komutu klavyeyle kendin yaz; değerleri kimseyle paylaşma).
5. GitHub > Actions > "Ajan Ofisi'ni Fly'a yükle" > onay kutusuna `EVET`.

Her komutta `-a gurtechs-ajan-ofisi` yaz; yanlış uygulamaya dokunma.

## Panelden video yayınlama
- Panelde "Video yayınla" kartı: MP4 seç (en fazla 30 MB), önizle, yükle, başlık ve açıklama yaz, onay kutusundan sonra yayınla.
- Sunucu videoyu ve metinleri depoya kaydeder (`videolar/yukleme_*.mp4`, `yayin/yukleme_*_instagram.txt`, `_youtube.txt`) ve mevcut `yayinla.yml` ile `youtube-yukle.yml` iş akışlarını `onay=EVET` ile çalıştırır.
- Açıklamaya "Doktor Filament yapay zekâ ile üretilmiş bir karakterdir." satırı kodla eklenir, YouTube için #Shorts da.
- Saatte en fazla 6 yayın. Onay verilmeden hiçbir şey yayınlanmaz.
- **GitHub anahtarında `Contents: Read and write` izni gerekir** (videoyu depoya kaydetmek için). Anahtar yalnızca bu depoya erişir.
- Not: Depo herkese açıksa yüklenen video, yayınlanmadan önce de depoda görünür.

## Canlı ajan durumu
Panel, `/api/ajanlar` uç noktasından her ajanın iş akışının son GitHub çalışmasını okur (60 sn önbellek, şifre gerekmez, yalnızca herkese açık çalışma bilgisi). Yeşil: son 36 saatte (trend için 4 gün) başarılı çalıştı. Mavi: elle tetiklenir ya da uzun süredir çalışmadı. Kırmızı: son çalışma başarısız.

## İçerik zinciri
"İçerik üret" (paneldeki Zincir kartı ya da İçerik ajanı kartı) `zincir.yml` iş akışını çalıştırır:
1. **Trend kontrolü:** trend araştırması 3 günden eskiyse `ajan/trend.py` yeniden çalışır.
2. **İçerik ajanı:** 5 aday fikir, geçmişe benzemeyeni ve en gerçekçisini seçer, senaryoyu yazar, öz eleştiri yapar.
3. **Video paketi:** `ajan/paket.py` senaryoyu video aracına yapıştırmaya hazır pakete çevirir (klip 8 sn'yi aşıyor mu, konuşma sığıyor mu).
4. **Kaydet:** her içerik için `zincir/<kimlik>.json` kaydı (kimlik `c...`; panelden bağımsız yüklenen videolar `y...`).

Panel, çalışma adımlarını `/api/durum` ile GitHub'dan okur ve animasyonu gerçek adımlara göre oynatır. Video yüklerken içerik seçilirse video o kayda bağlanır; yayınlar bağlantı ve medya kimliğiyle deftere (`yayinlar`) yazılır. Aşama sırası: fikir, senaryo, video, yayın, ölçüm, öğrenme (ölçüm ve öğrenme sonraki adım).

## Hikaye ajanı ve bildirimler
- `hikaye/ayar.json` (zamanlama, başlangıçta **duraklatılmış**), `hikaye/kuyruk/*.json`, `hikaye/gorseller/*.jpg`.
- `hikaye-yayinla.yml` her saat başı çalışır (GitHub geciktirebilir); `ajan/hikaye.py` slot hesabını yapar. Çift yayını önlemek için önce "yayınlanıyor" işaretini depoya yazar, yazamazsa yayınlamaz. Ardışık 3 hatada kendini duraklatır.
- Fotoğrafı panelde kuyruğa koymak yayın onayı sayılır. Panel fotoğrafı telefonda 1080x1920 JPEG'e küçültür.
- `nobetci.yml` günlük Instagram, YouTube, OpenAI anahtarlarını ve ofis sunucusunu denetler, sonucu `hikaye/saglik.json`'a yazar, yeni sorunda bildirim gönderir.

### Web push kurulumu (bir kez)
1. VAPID anahtarı üret (kendi bilgisayarında, `C:\AjanOfisi` gibi ayrı bir klasörde): `npx web-push generate-vapid-keys`
2. Bir de uzun rastgele bir `BILDIRIM_SIRRI` düşün (en az 24 karakter).
3. `fly secrets set -a gurtechs-ajan-ofisi VAPID_PUBLIC_KEY=... VAPID_PRIVATE_KEY=... BILDIRIM_SIRRI=...`
4. GitHub > Settings > Secrets > Actions: aynı `BILDIRIM_SIRRI` değerini ekle.
5. Sunucuyu yeniden yükle (fly-yukle.yml). Panelde Hikaye ajanı > Bildirimler > "Bildirimleri aç" (Android Chrome).
Abonelikler `bildirim/abonelikler.enc` dosyasında, `BILDIRIM_SIRRI`'ndan türetilen anahtarla şifrelenmiş saklanır.

### Video hikayeleri
- Panelden MP4 (3-60 sn, en fazla 30 MB) kuyruğa eklenir. Yayından önce `ajan/hikaye.py` videoyu denetler: dikey 9:16, H.264, AAC (ya da sessiz) ise olduğu gibi yayınlanır; değilse 1080x1920 H.264/AAC'ye çevrilir (`<kimlik>_hazir.mp4`).
- 60 sn'den uzun ya da 3 sn'den kısa video "hata" olur (ajan duraklamaz; yalnızca anahtar/servis hataları duraklatma sayacına girer).
- Instagram videoyu işlerken bekler (en fazla ~6 dk). Dosya raw adresinde görünene kadar bekler.
- **Depo büyümesi:** her video depoya girer (ve dönüştürülmüşse bir kopya daha). Sık video hikayesi için depo hızla büyür; ileride medyayı ayrı bir depolamaya taşımak gerekebilir.

### Aynı videoyu birden fazla yere aynı anda yayınlama
"Video yayınla" kartında üç hedef işaretlenebilir: **Instagram Reels**, **YouTube Shorts**, **Instagram Hikaye**. Onaylayınca üçü birlikte başlar.
- Hikaye için kuyruğa aynı video dosyasını işaret eden bir kayıt açılır (dosya kopyalanmaz) ve `hikaye-yayinla.yml` o kimlikle (`kimlik` girdisi) hemen çalıştırılır; sıradaki başka bir hikayeyi yayınlamaz.
- Hikaye en fazla 60 sn olabilir; daha uzun videoda panel hikaye seçeneğini kapatır. Dikey 9:16 H.264 değilse hikaye için otomatik uyarlanır.
- Hikaye yazı almaz; yalnızca Reels ya da Shorts seçiliyse başlık ve açıklama istenir.
- Zincir defterinde her hedef ayrı girdi (`hedef`: instagram, youtube, hikaye) olarak bağlantı ve medya kimliğiyle kaydedilir.

### Yapay zekâ görsel üretimi (Kademe 2)
`ajan/hikaye_uret.py` (iş akışı: `hikaye-uret.yml`, günde bir kez ya da panelden "Şimdi üret"):
- OpenAI web aramasıyla Printables ve MakerWorld'de revaçtaki tasarımları bulur. Bağlantılar aramanın gerçekten döndürdüğü adreslerle doğrulanır.
- **Yalnızca lisansı açıkça CC0 ya da CC BY olanlar** kullanılır; NC, ND, SA, "Standard Digital File License" ve belirsiz lisanslar elenir. Başkasının fotoğrafı indirilmez; yalnızca ad, tasarımcı, lisans ve bağlantı alınır.
- Her tasarım için kendi sahnemizde (atölye tezgâhı) benzer, kopya olmayan temsili görsel üretir (hareketli mekanizma, yazı, logo yok).
- Yapay zekâ kendi çıktısını denetler (yazı, logo, bozuk anatomi, fiziksel olarak makul mü); 3 denemede geçemezse o tasarım atlanır.
- Görsele "Yapay zekâ görseli (temsili)" etiketi ve atıf (tasarım adı, tasarımcı, lisans, kaynak) işlenir.
- Kuyruğa `planli` (otomatik mod) ya da `onay_bekliyor` (onaylı mod) girer; yayını Hikaye ajanı yapar. Bildirim gelir; beğenmediğini panelden silersin.
- **Başlangıçta kapalıdır** (`hikaye/uretim.json`, `aktif: false`). Günlük ve aylık görsel sınırı (`hikaye/harcama.json` sayar) maliyeti üstten kapatır.
- Gerekli sır: `OPENAI_API_KEY` (diğer ajanlarla aynı). Sunucuyu yeniden yüklemek gerekir (panelde yeni bölüm için).

**Referans fotoğraf (Kademe 2.5):** Her tasarım için yalnızca o tasarım sayfasının paylaşım önizleme (og:image) fotoğrafı indirilir
(tek sayfa, tek görsel, açık bir bot adıyla; depoya yazılmaz, yalnızca bellekte tutulur) ve OpenAI görsel düzenleme servisiyle aynı nesne yeni sahnede
yeniden çizilir. Yapay zekâ üretilen görseli referansla karşılaştırıp sadakati denetler. Görselde "Tasarımcının fotoğrafından uyarlandı" ve atıf yazar.
Fotoğraf alınamazsa (site engellerse) "zorunlu" modda o tasarım atlanır; "tercih" modda metinden çizilir (daha az benzer).

### Thingiverse kaynağı ve geliştirilmiş Trend ajanı
- **Thingiverse (resmi servis):** `THINGIVERSE_TOKEN` gizli anahtarı tanımlıysa hikaye üreticisi Thingiverse'in popüler listesinden ve trend terimlerinden CC0/CC BY lisanslı tasarımları da aday yapar (lisans ve fotoğraf adresi sitenin kendi verisinden). Anahtar yoksa kaynak sessizce atlanır.
  Anahtar: thingiverse.com → Apps → Create an App → App Token; GitHub → Settings → Secrets and variables → Actions → New repository secret (`THINGIVERSE_TOKEN`).
- **Trend ajanı:** 10-12 öneri, en az 7 farklı kategori, mevsimsel konular, önceki araştırmayı tekrarlamama, Thingiverse popüler listesinden gerçek veri (anahtar varsa) ve her öneriye Thingiverse'ten 3 gerçek örnek tasarım. İçerik ajanı bu örnekleri esin olarak görür (kopyalamaz).
- Hikaye üreticisi Trend ajanının konularını ve İngilizce arama terimlerini kullanır; adayların yarısı trend konularına uyar.

### Zamanlayıcı (Fly sunucusunda)
GitHub'ın zamanlayıcısı çalışmaları atlayabildiği için sunucu tetikleri kendisi verir (Türkiye saati): saat başı :05'te hikaye yayın kontrolü (10:05–22:05), her gün 08:20'de görsel üretimi, pazartesi/perşembe 06:30'da trend ajanı.
Sunucunun sürekli açık olması gerekir (`fly.toml`: `auto_stop_machines = "off"`, `min_machines_running = 1`). Durum: `/api/zamanlayici`. Kapatmak için `ZAMANLAYICI=kapali` ortam değişkeni.
GitHub'ın kendi zamanlayıcısı yedek olarak durur; çift tetik zararsızdır (yayın: ortak kilit + slot mantığı; üretim: günde bir kez).

### Akademi ajanı (V1)
Haftada bir (pazar 18:00 TR; sunucu zamanlayıcısı ve GitHub iş akışı) `ajan/akademi.py` çalışır:
- **Rapor (ücretsiz, yapay zekâsız):** hikaye üretimi, denetim sonuçları ve en sık sorunlar, elenen lisanslar, harcama, içerik zinciri ve trend özeti, iş akışı başarısızlıkları. `akademi/rapor-son.json` ve `akademi/rapor-<hafta>.md`.
- **Ders önerileri:** yapay zekâya yalnızca toplu sayılar gider (tasarım adı, trend konusu gibi internetten gelen metinler gitmez; haftada birkaç sent). En çok 3 öneri, her biri somut bir sayıya dayanmalı; talimat/URL içeren ya da kanıtsız öneriler elenir. `akademi/oneriler.json`.
- **Onay şart:** öneriler "onay bekliyor" olarak panelde (Akademi kartı) görünür. Yalnızca senin ONAYLADIĞIN dersler ajanların istemine eklenir (hikaye, trend, içerik); istediğin zaman "Kaldır"ırsın. Akademi ajanların kodunu ve ayarlarını değiştirmez.
- Hikaye üretici, öğrenebilmesi için `hikaye/olaylar.jsonl` dosyasına kısa olay kayıtları yazar (neden elendi, denetim sorunları).
