# Sınav Asistanı (Android TV)

Evde çalışan öğrenciler için, OpenAI API ile internette araştırma yaparak yazılı sınavlara hazırlık
amaçlı çoktan seçmeli deneme sınavları hazırlayan Android TV uygulaması.

## Nasıl çalışır?

1. **Yeni sınav** ekranında sınıf, ders, sınav dönemi, soru sayısı ve zorluk seçilir.
   İstenirse "Ek istek" kutusuna not yazılır (TV klavyesindeki mikrofonla söylenebilir).
2. Uygulama isteği OpenAI Responses API'ye gönderir (`web_search` aracı, JSON şeması ile yapılandırılmış çıktı,
   arka plan modu). Model, MEB'in güncel programını ve sınav konularını araştırır, soruları yazar.
3. Sorular tek tek ekrana gelir; şekilli sorular SVG olarak çizilir. Cevaplar kumandayla seçilir.
4. Sonda puan ve her soru için çözümlü **cevap anahtarı** gösterilir.
5. Sınavlar cihazda saklanır, **Geçmiş sınavlar** ekranından tekrar çözülebilir.

## Kurulum

APK, her `sinav-asistani/` değişikliğinde GitHub Actions tarafından derlenir ve ilgili iş akışı
çalıştırmasının **Artifacts** bölümüne `SinavAsistani-v1.0.N.apk` olarak eklenir (30 gün saklanır;
indirmek için GitHub hesabıyla giriş gerekir). SHA256 değeri derleme günlüğünde yazar.

```
adb install -r SinavAsistani-v1.0.N.apk
```

## API anahtarı

Anahtar koda yazılmaz, yalnızca cihazda saklanır. Kumandayla yazmak yerine bilgisayardan gönderilebilir:

```
adb shell am start -n com.ferhat.sinavasistani/.MainActivity --es api_key "sk-..."
```

Model varsayılan olarak `gpt-5.5`'tir; Ayarlar ekranından veya `--es model "<model>"` ile değiştirilebilir.

## Yapı

- `app/src/main/assets/` — arayüz (HTML, CSS, JavaScript): ekranlar, kumanda ile gezinme, OpenAI isteği
- `app/src/main/java/.../MainActivity.kt` — WebView, ayarlar ve HTTPS isteği köprüsü
- `app/debug.keystore` — her sürümün eskisinin üzerine kurulabilmesi için sabit imza anahtarı
  (kişisel kullanım içindir, gizli değildir)

## Notlar

- Sorular yapay zekâ tarafından hazırlanır; nadiren hata olabilir. Cevap anahtarındaki çözümler kontrol için gösterilir.
- OpenAI hesabında aylık harcama sınırı belirlenmesi önerilir.
