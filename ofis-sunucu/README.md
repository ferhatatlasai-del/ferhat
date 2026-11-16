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
