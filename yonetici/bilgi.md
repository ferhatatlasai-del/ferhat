# Yönetici ajan bilgi tabanı (3D baskı doğruluk kontrolü ve video inceleme ölçütleri)

Bu dosya yönetici ajana ve video incelemesine her seferinde verilir. Elle düzenlenebilir. Değerler TİPİK aralıklardır; üretici ve model farkıyla değişir, kesin kural değildir.

## Tipik değerler (aşırı sapma = şüpheli iddia)
- PLA: nozul yaklaşık 190-220 °C, tabla 0-60 °C. Nemden en az etkilenen yaygın filament.
- PETG: nozul yaklaşık 230-250 °C, tabla yaklaşık 70-85 °C. Nem çeker (çıtırtı, ipliklenme).
- ABS/ASA: nozul yaklaşık 240-260 °C, tabla yaklaşık 90-110 °C; kapalı kabin ve havalandırma önerilir, çekme/warping eğilimi yüksek.
- TPU: nozul yaklaşık 210-235 °C, yavaş basılır (düşük hız, düşük geri çekme).
- Yaygın nozul çapı 0,4 mm; tipik katman yüksekliği 0,1-0,3 mm; filament çapı 1,75 mm (tolerans ±0,02-0,05 mm).
- İlk katman genellikle daha yavaş ve biraz daha sıcak/yassı basılır; tabla temizliği (yağ, toz) yapışmayı belirler.
- Dolgu oranı genellikle %10-%30 arası yeterli; %100 dolgu çoğu parça için gereksiz.

## Kavramlar (doğru anlatım için)
- Heat creep: ısının soğuk bölgeye sızıp filamenti yukarıda yumuşatması (soğutma/ısı bariyeri sorunu).
- Retraction (geri çekme): hareket sırasında akışı kesip ipliklenmeyi (stringing) azaltır.
- Soğuk çekme (cold pull): nozulu düşük ısıda filamenti çekerek temizleme yöntemi.
- Warping: köşelerin kalkması; sıcak tabla, kenar genişletme (brim), kabin ile azalır.
- Destek: büyük taşmalarda (overhang) sarkmayı önler; yaklaşık 45-60° üstü taşmalarda gerekli olabilir.
- Bambu Lab A1 / A1 Combo: yatağı hareket eden (bed-slinger) açık kasa yazıcı; A1 Combo'da AMS lite (çok renkli besleme) bulunur; otomatik tabla seviyeleme ve kalibrasyon özellikleri vardır. Menü adı, sürüm ve sayı ayrıntıları modele özeldir: emin değilsen genel anlat, uydurma.

## Video inceleme ölçütleri (REDDET ya da düşük puan)
1. Teknik olarak yanlış ya da şüpheli bilgi (yukarıdaki aralıklara ve yaygın bilgiye aykırı sayı/iddia; kesin ve ölçüsüz vaatler: "kesin çözüm", "%100").
2. Uydurma kişisel deneyim ("ben denedim"), marka karşılaştırması, fiyat, sağlık/güvenlik iddiası.
3. Bozuk, boş ya da neredeyse boş sahne; okunmayan, taşan ya da üst üste binen yazı; konuyla ilgisiz görüntü.
4. Anlatı ile görüntü uyuşmuyor (ör. "nem" anlatılırken tıkanma çiziliyor).
5. Önceki videolarla aynı bilgilerin tekrarı; aynı sahne dizisi.
6. Anlatıda abartı/şişirme sözcükleri ("harika", "mükemmel", "inanılmaz"), saçma ya da anlamsız cümle.
7. Marka/ürünle bağlantı izlenimi (açıklamada "bağımsızdır" notu olmadan Bambu Lab videosu).
Puan 1-10: 8+ sorunsuz, 7 küçük kusur (yayınlanabilir), 6 ve altı reddet.
