# Kapatma Listesi – Xiaomi TV Box S (2. nesil)

Kaynak: [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv) (MIT lisansı),
`examples/xiaomi-mi-box-s-2nd-gen/debloat.txt`. Bu liste, aynı kutuda (MiTV-AFKR0, kod adı "jaws",
Google TV 11, 2 GB RAM) birkaç kişi tarafından denenmiş. Kutunun etiketindeki MDZ-28-AA, aynı cihazın
resmî model numarası. 5. adımda `getprop` ile kutunuzun gerçekten MiTV-AFKR0 olduğunu doğrulayacağız.

Yöntem: her paket `pm disable-user --user 0 <paket>` ile **kapatılır, silinmez**.
Geri almak için: `pm enable <paket>`.

## Grup 1 – Takip ve veri gönderme (önerilen: kapat)
| Paket | Ne işe yarıyor |
|---|---|
| `com.miui.tv.analytics` | Xiaomi kullanım analitiği |
| `com.xiaomi.statistic` | Xiaomi kullanım istatistiği gönderici |
| `com.google.android.feedback` | Google geri bildirim gönderici |
| `com.google.android.partnersetup` | Google reklam/iş ortağı takip sinyalleri |

## Grup 2 – Reklam satırları ve otomatik kurulumlar (önerilen: kapat)
| Paket | Ne işe yarıyor |
|---|---|
| `com.mitv.tvhome.oemtab` | Xiaomi reklam satırı |
| `com.mitv.tvhome.michannel` | Mi içerik satırları |
| `com.mitv.tvhome.mitvplus` | Mi TV+ reklamlı kanallar |
| `com.mitv.tvhome.atv` | PatchWall (Xiaomi içerik ekranı) |
| `com.xm.webcontent` | Xiaomi web tanıtımları |
| `android.autoinstalls.config.xioami.mibox3` | İş ortağı uygulamalarının otomatik kurulumu (paket adındaki yazım hatası orijinal) |

## Grup 3 – Hazır gelen uygulamalar (size sorulacak)
| Paket | Ne işe yarıyor | Not |
|---|---|---|
| `com.amazon.amazonvideo.livingroom` | Prime Video | Kullanmıyorsanız kapatılır. Yeniden başlatınca kendiliğinden geri açılabiliyor |
| `com.google.android.videos` | Google TV film mağazası | |
| `com.google.android.play.games` | Play Oyunlar | |
| `com.android.printspooler` | Yazdırma servisi | |
| `com.google.android.youtube.tv` | YouTube | Sadece SmartTube kurarsanız |
| `com.netflix.ninja` | Netflix | Sadece kullanmıyorsanız |

## KAPATMAYACAĞIZ (bizim kararımız)
| Paket | Neden |
|---|---|
| `com.xiaomi.mitv.updateservice` | Orijinal listede kapatılıyor, ama kutunun **güncel kalmasını** istiyoruz |
| `com.xiaomi.tvqs.overseas` | Kapatıldığında ne olacağı denenmemiş |
| `com.xiaomi.android.tvsetup.partnercustomizer` | Kumandadaki Netflix/YouTube tuşları |

## Dokunulmayacaklar (orijinal listede de bilerek bırakılmış)
- Google Asistan (`com.google.android.katniss`), Chromecast (`mediashell`), telefondan kumanda (`tv.remote.service`)
- USB medya uygulamaları (`mimusic2`, `mitv.gallery`, `mediaexplorer`, `mitv.videoplayer`): USB diskten film ve fotoğraf için gerekli
- Ekran yansıtma (`smartshare`, `wfdsinkhelperservice`)
- `mitv.service`, `com.mi.bluetooth`, `com.droidlogic*` (işlemcinin sistem servisleri), `com.xiaomi.gtv.settings`
- Play Store, Play Hizmetleri, klavye, `com.android.location.fused`

## Ana ekranı değiştirmek (isteğe bağlı, en sona bırakıldı)
Bu kutuda deneyen kişiler şunları yaşamış:
- Google TV ana ekranını (`launcherx`) kapatmak tek başına yetmiyor. Kurulum sihirbazı
  (`setupwraith`) ana ekranı ele geçiriyor, onun da kapatılması gerekiyor.
- Sihirbaz kapatılınca **Wi-Fi yaklaşık 20 saniye kopuyor** ve şifreyi bir kez yeniden girmek gerekiyor.
  Bazı kutularda ilk kurulumdan kalma gizli bir ağ kaydını da silmek gerekmiş.
- Kumandadaki **Netflix, YouTube ve Prime tuşları çalışmaz hale geliyor**. Bunlar ancak ek bir
  tuş eşleme uygulamasıyla geri getirilebiliyor.

Önerimiz: Önce Grup 1–3'ü kapatıp **"Yalnızca uygulamalar" modunu** kullanmak. Bu, reklamların çoğunu
riske girmeden kaldırır. Ana ekranı değiştirmek gerekirse ayrıca karar veririz.
