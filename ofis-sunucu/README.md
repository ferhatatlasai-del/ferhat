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
- `hikaye-yayinla.yml` yarım saatte bir çalışır, :05 ve :35 (GitHub geciktirebilir); `ajan/hikaye.py` slot hesabını yapar. Çift yayını önlemek için önce "yayınlanıyor" işaretini depoya yazar, yazamazsa yayınlamaz. Ardışık 3 hatada kendini duraklatır.
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
GitHub'ın zamanlayıcısı çalışmaları atlayabildiği için sunucu tetikleri kendisi verir (Türkiye saati): yarım saatte bir (:05 ve :35) hikaye yayın kontrolü (10:05–22:35), her gün 08:20'de görsel üretimi, pazartesi/perşembe 06:30'da trend ajanı.
Sunucunun sürekli açık olması gerekir (`fly.toml`: `auto_stop_machines = "off"`, `min_machines_running = 1`). Durum: `/api/zamanlayici`. Kapatmak için `ZAMANLAYICI=kapali` ortam değişkeni.
GitHub'ın kendi zamanlayıcısı yedek olarak durur; çift tetik zararsızdır (yayın: ortak kilit + slot mantığı; üretim: günde bir kez).

### Akademi ajanı (V1)
Haftada bir (pazar 18:00 TR; sunucu zamanlayıcısı ve GitHub iş akışı) `ajan/akademi.py` çalışır:
- **Rapor (ücretsiz, yapay zekâsız):** hikaye üretimi, denetim sonuçları ve en sık sorunlar, elenen lisanslar, harcama, içerik zinciri ve trend özeti, iş akışı başarısızlıkları. `akademi/rapor-son.json` ve `akademi/rapor-<hafta>.md`.
- **Ders önerileri:** yapay zekâya yalnızca toplu sayılar gider (tasarım adı, trend konusu gibi internetten gelen metinler gitmez; haftada birkaç sent). En çok 3 öneri, her biri somut bir sayıya dayanmalı; talimat/URL içeren ya da kanıtsız öneriler elenir. `akademi/oneriler.json`.
- **Onay şart:** öneriler "onay bekliyor" olarak panelde (Akademi kartı) görünür. Yalnızca senin ONAYLADIĞIN dersler ajanların istemine eklenir (hikaye, trend, içerik); istediğin zaman "Kaldır"ırsın. Akademi ajanların kodunu ve ayarlarını değiştirmez.
- Hikaye üretici, öğrenebilmesi için `hikaye/olaylar.jsonl` dosyasına kısa olay kayıtları yazar (neden elendi, denetim sorunları).

### Shorts / Reels üretici
`ajan/kisa_video.py` (iş akışı `kisa-video.yml`, salı ve cuma 17:00 TR sunucu zamanlayıcısıyla ya da panelden "Şimdi bir taslak üret"):
- Hikaye ajanının zaten ürettiği, atıflı yapay zekâ görsellerinden 4 sahneli, müzikli (stil dönüşümlü), dikey 9:16 kısa video **taslağı** hazırlar. Yeni görsel üretmez (görsel maliyeti yok). Başlık, ekran kancası ve açıklama için yapay zekâya yalnızca temizlenmiş tasarım adları gider (birkaç sentten az); anahtar yoksa sabit şablon.
- Açıklamaya her tasarımın adı, tasarımcısı, lisansı ve bağlantısı (CC BY atfı) ile "yapay zekâ görseli" notu yazılır.
- **Hiçbir şeyi yayınlamaz.** Video `videolar/yukleme_<tarih>.mp4`, taslak `shorts/<kimlik>.json` (durum `onay_bekliyor`). Panelde (Shorts / Reels üretici kartı) videoyu izler, başlık ve açıklamayı düzenler, "YouTube Shorts + Reels olarak yayınla" dersin; mevcut yayın akışı (`/api/yayinla`) çalışır.
- Aynı anda en çok 3 onay bekleyen taslak tutulur; kullanılmamış hikaye görseli 3'ten azsa üretim beklemeye geçer. YouTube yükleme kotası: yükleme başına 1600 birim (günlük 10.000).

### Viral 3D video üretici (Türkçe, seslendirmeli, ~60 sn)
`ajan/viral_video.py` (iş akışı `viral-video.yml`; pazartesi, çarşamba, cumartesi 14:00 TR sunucu zamanlayıcısıyla ya da panelde Video sekmesi → "Şimdi viral video üret", isteğe bağlı konu yazılabilir). **Tamamen kodla** üretilir, harici video/ses hizmeti yoktur:
- **Senaryo:** önce `video/senaryolar/*.json` (elle yazılmış hazır senaryolar; ilki "Tablaya yapışma sorununa pratik çözümler"), sonra `video/konular.json` listesinden sıradaki konu için yapay zekâ (`OPENAI_API_KEY`) merak uyandıran bilgi senaryosu yazar. Doğruluk kuralları isteme yazılıdır (uydurma rakam/deneyim/marka yok, "genellikle/civarı"); senaryo 70-190 kelime, geçerli sahne tipleri, son sahne CTA olmadan kabul edilmez.
- **Seslendirme:** Google Cloud Text-to-Speech (`GOOGLE_TTS_API_KEY`, varsayılan ses `tr-TR-Wavenet-B`). SSML işaretleriyle kelime zamanları alınır; sahne süreleri konuşmaya göre belirlenir, alt yazı kelime kelime vurgulanır. PLA/PETG/ABS gibi kısaltmalar yalnızca sese uygun okunuşla verilir (alt yazıda özgün hali kalır).
- **3D animasyon:** `video/sahne.js` (three.js) 1080×1920, 30 fps kareleri Chromium ile çizer (`video/render.js`, kareler doğrudan ffmpeg'e akar). Sahne tipleri: `baski`, `temizlik`, `ilk_katman`, `sicaklik`, `hiz`, `yapistirici`, `sayi`, `karsilastir`, `ozet`, `cta`. Sahneler tek bir 3D dünyada yan yana durur; geçişlerde kamera uçar (FOV vurgusu, flaş).
- **Ses tasarımı:** `ajan/ses_tasarim.py` müziği (Am-F-C-G pad, bas, vuruş, hi-hat, arpej + eko), 3D yazıcı atmosferini (step motor, fan), geçiş "whoosh" + darbe + yükselişi, vurgu "pop", çan, uyarı, tık ve sprey/silme seslerini numpy ile **sentezler**; konuşma varken müzik yan zincirle kısılır; çıktı −14 LUFS'a normalize edilir.
- **Taslak:** `videolar/yukleme_<tarih>.mp4` + `shorts/<kimlik>.json` (durum `onay_bekliyor`, `tur: "viral"`). **Yayınlamaz**; panelden onaylanınca mevcut YouTube/Instagram akışı yayınlar. Açıklamaya "seslendirme yapay zekâ ile üretilmiştir" notu eklenir.
- Ayarlar `shorts/viral_ayar.json` (isteğe bağlı: `aktif`, `en_cok_bekleyen`, `ses`, `konusma_hizi`, `perde`). Kullanılan konular `shorts/viral_kullanilan.json`. Üretim runner'da ~10-15 dk sürer.
- **Gerekli anahtar (ikisinden biri):** GitHub Secrets → `GEMINI_API_KEY` (aistudio.google.com/apikey, **kart gerekmez**; Gemini TTS, ses `Orus`, kelime zamanları konuşmadaki duraklamalardan çıkarılır, ücretsiz katman dakika sınırında otomatik yeniden dener) ya da `GOOGLE_TTS_API_KEY` (Google Cloud Console → Text-to-Speech API'yi etkinleştir → Kimlik bilgileri → API anahtarı; anahtarı "Cloud Text-to-Speech API" ile kısıtla). Yoksa üretim açık hata mesajıyla durur.
- Yerel deneme: `node` + Chromium (`CHROME_YOLU`), `python3 ajan/viral_video.py --senaryo video/senaryolar/tablaya-yapisma.json --sessiz --olcek 0.5 --cikti onizleme.mp4`.

### Panel düzeni (sekmeler)
Panel yedi sekmeye ayrıldı; alttaki rozetler o sekmede bekleyen karar/uyarı sayısını gösterir.
- **Ofis** (açılış): 3 boyutlu ofis, ajan seçimi, üstte "yapılacaklar" şeridi. Ofis yalnızca bu sekmede görünür ve çizilir; diğer sekmelerde durur.
- **Özet**: bugünkü yayın/üretim kartları, "Yapılacaklar" listesi (tıklayınca ilgili sekmeye gider), hikaye yayını ve sistem durumu, ajan listesi.
- **Hikaye**: ajan durumu, kuyruk (onayla/reddet/sil), kendi fotoğraf ve videonu ekleme.
- **Video**: Shorts / Reels üretici taslakları ve elle video yayınlama.
- **İçerik**: zincir ("İçerik üret") ve trend fikirleri.
- **Akademi**: haftalık rapor ve ders önerileri.
- **Sistem**: hikaye zamanlaması, yapay zekâ üretim ayarları, bildirimler, servis sağlığı, zamanlayıcı.
Adres sonundaki `#hikaye`, `#video` gibi bağlantılar doğrudan sekmeyi açar. Ofis şifresi gerektiren işlemde üstte tek bir şifre çubuğu açılır.

### Ofiste video üretme ve yayınlama (YouTube ve Instagram)
- **Serbest kamera:** sürükle = sınırsız dönüş (7-86° yükseklik), iki parmak = yakınlaştır ve kaydır, sağ tuş / Shift+sürükle = kaydır, "Tüm ofis" = sıfırla.
- **Tam ekran:** "⤢ Tam ekran" düğmesi; telefonu yatay çevirince ofis otomatik tam ekran olur (✕ Küçült ile çıkılır).
- **YouTube ya da Instagram kişisine dokun:** başının altında menü açılır. "Video üret" (Shorts/Reels taslağı hazırlatır) → taslak hazır olunca önizleme ve **"Onayla ve yayınla"** → duvardaki televizyon açılıp logoyu gösterir, yükleme bitince kişi masasından kalkıp televizyona bakarak alkışlar ("Yayında! 🎉").
- Aynı taslak iki platform için de kullanılabilir (`shorts/<id>.json` içinde `yayinlanan` listesi); yalnızca onayladığın platforma gider. Hiçbir şey onaysız yayınlanmaz.

### Ofiste her ajanın kendi menüsü ve Hikaye ajanının telefonu

Paneldeki düğmelerin hepsi ofiste ilgili ajanın avatarına tıklayınca da çıkar:

| Avatar | Menü |
|---|---|
| Hikaye | Hikaye üret ve sıraya koy · Sıradakini şimdi yayınla · Kuyruğu aç |
| Trend | Trend araştır (`/api/trend-calistir`, saatte en fazla 3) · Trend fikirlerini gör |
| İçerik | Reels senaryosu üret · Carousel üret · Direktifle üret |
| Dr. Filament | Akademiyi çalıştır · Dersleri gör |
| YouTube / Instagram | Short/Reel üret, onayla, yayınla |

Hikaye ajanı hikaye üretirken telefonuna bakar; telefonunun üstünde Instagram benzeri bir balon çıkar:
üretilirken "Hikaye hazırlanıyor…", kuyruğa girince "Hikaye üretildi", yayınlanınca "Instagram'da paylaşıldı".

### İstatistikçi ajan: günde 5 izlenme raporu

Her gün Türkiye saatiyle 09, 12, 15, 18 ve 21'de (sunucu zamanlayıcısı `istatistik-rapor.yml` iş akışını tetikler) İstatistikçi ajan tüm paylaşımların izlenmesini toplar ve telefona kısa bir bildirim gönderir:
`Toplam 905 (+86) · Reels 410 · Short 220 · Hikaye 95 (4 bugün) · Takipçi 420 · En iyi Reels: ...`

- **Kaynaklar:** Instagram Reels/video/gönderiler (izlenme, erişim, beğeni, yorum), yayınlanmış hikayeler (kuyruktaki `medya_kimligi` ile), YouTube Shorts ve videolar (izlenme, beğeni, yorum). Yalnızca okur, hiçbir şey yayınlamaz.
- **Hikaye:** Instagram hikaye değerlerini yalnızca yayındayken (yaklaşık 24 saat) verir; bu yüzden her çalışmada okunur ve en yüksek değer `istatistik/hikayeler.json` içinde saklanır.
- **Çıktılar:** `istatistik/son.json` (panel okur), `istatistik/gecmis.jsonl` (artış ve grafik), `istatistik/ayar.json` (`aktif`, `artis_yoksa_atla`).
- **Panel:** Özet sekmesinde "İzlenme raporu" kartı (toplam, Reels, Short, Hikaye, takipçi, grafik, en çok izlenenler, tüm paylaşımlar; duraklat ve "artış yoksa bildirim atla" düğmeleri). Ofiste İstatistik avatarına dokununca: rapor hazırla, raporları gör, günlük raporları duraklat/aç.
- **İzinler:** Instagram izlenmesi için Meta uygulamasında insights izni, YouTube için okuma izni gerekir. Yoksa ilgili kısım "?" görünür, bildirimin sonunda "izin yok" yazar ve rapor kalan verilerle yine çıkar.
- **Elle:** `POST /api/istatistik-calistir` (saatte en fazla 4); elle başlatma duraklatma ve "artış yoksa atla" kurallarını yok sayar. Bildirim gerçek gönderim için `OFIS_ADRES` ve `BILDIRIM_SIRRI` kullanır.

### Ofis müziği

Ofis tam ekran olunca (düğmeyle ya da telefonu yan çevirince otomatik) hafif bir arka plan müziği çalar; tam ekrandan çıkınca, sayfa arka plana geçince ya da 🎵 düğmesiyle kapatınca durur. Tercih tarayıcıda hatırlanır.
Müzik dosya değil, tarayıcıda WebAudio ile üretilir (yumuşak elektrik piyano akorları, bas, fırça ritmi; 76 BPM, iki akor dizisi dönüşümlü): telif sorunu ve ek yükleme yoktur. Ses seviyesi bilerek düşüktür (yaklaşık −30 dBFS); telefonun kendi ses düğmesiyle ayarlanır.
Telefon yan çevrilince tarayıcı sayfada daha önce hiç dokunuş görmediyse sesi başlatmaz; bu durumda "ekrana bir kez dokun" uyarısı çıkar.

### Günlük hikaye sayısı neden ayarın altında kalabilir? (düzeltildi)
Her kontrol en çok bir hikaye yayınlar. Eskiden kontrol saat başıydı ve iki hikaye arası alt sınır 60 dk'ydı; yayın birkaç dakika gecikmeyle çıktığı için bir sonraki saat başında "60 dk dolmadı" denip atlanıyor, günde 12 ayarında 7-9 hikaye çıkıyordu. Artık kontrol yarım saatte bir yapılır ve alt sınır, slot aralığının %40'ını aşamaz (12 hikaye 10:00-20:00 için 20 dk). Simülasyonda 4, 6, 10 ve 12 ayarlarının hepsi tam sayıya ulaşır.

### YouTube Short olması ve çift paylaşım (düzeltildi)
- **Short:** YouTube bir videoyu yalnızca kare ya da dikey (9:16) ve en çok 3 dk ise Short sayar; açıklamadaki `#Shorts` tek başına yetmez. Panelden dışarıdan yüklenen yatay video (ör. 640x480) normal video olarak çıkıyordu. `youtube_yukle.py` artık yatay videoyu, içindeki siyah şeritleri kırparak, bulanık arka planlı 1080x1920 dikey videoya çevirip öyle yükler. Zaten dikey/kare video olduğu gibi gider; 3 dk'dan uzun video çevrilmez (uyarı yazılır). İş akışı ffmpeg'i gerektiğinde kurar.
- **Çift paylaşım:** Aynı video içerik olarak (dosya adı farklı olsa bile) 24 saat içinde aynı platforma gönderildiyse sunucu "zaten gönderilmiş" der; panel "Yine de tekrar yayınlansın mı?" diye sorar, onaylarsan gönderir. Kayıt sunucu belleğinde tutulur (yeniden başlatınca sıfırlanır).

### Biten hikaye kayıtlarının otomatik temizlenmesi
Yayınlanıp biten (yayında, reddedildi, hata) hikayelerden `saklama_gun` (varsayılan 3, `hikaye/ayar.json`) günden eski olanlar, her yayın kontrolünde eskiden yeniye silinir: kayıt dosyası ve `hikaye/gorseller/` altındaki görsel/video. Depo şişmesin diye (günde 12 hikaye ≈ 18 MB). Planlı, onay bekleyen ve yayınlanan kayıtlara, ayrıca `videolar/` klasöründeki ortak dosyalara dokunulmaz.
Silinen her kaydın kısa özeti `hikaye/arsiv.jsonl` dosyasına yazılır; Akademi'nin haftalık sayıları bunu da okur, yani silme istatistiği bozmaz. İstatistikçi hikaye izlenmelerini `istatistik/hikayeler.json` içinde ayrıca saklar. `saklama_gun` 0 yapılırsa temizleme kapanır. Kullanılmış tasarım listesi (`hikaye/kullanilan.json`) silinmez, aynı tasarım yeniden üretilmez.
