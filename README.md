# Antigravity V4 — Pinch Tabanlı Temassız PC Kontrolü

> **Durum: Tamamlandı / Arşivlendi.** Bu proje, webcam ile el jesti ve yüz ifadesi tabanlı
> bilgisayar kontrolünün ne kadar ileri götürülebileceğini araştıran, dört sürüm boyunca
> evrilen bir deneydi. Vardığımız dürüst sonuç da dahil olmak üzere tüm mimari aşağıda —
> ayrıntılı anlatım için: **[Proje Sayfası (GitHub Pages)](https://safaeren777-collab.github.io/antigravity/)**

Sıradan bir webcam'i; tıklama, kaydırma, pencere yönetimi ve kısayol tetikleme yapabilen
temassız bir giriş cihazına dönüştüren Windows masaüstü uygulaması. Python, PyQt6,
MediaPipe ve Win32 API ile yazıldı.

## Neler Yapıyor?

| Jest | İşlev |
|---|---|
| 🤏 İşaret pinch — **tak** | Onay / Enter |
| 🤏 İşaret pinch — **tut & sürükle** | Sürekli sayfa kaydırma (joystick mantığı, orantılı hız) |
| 🤏 Orta pinch — **yatay sürükle** | **Alt-Tab karuseli**: Alt basılı kalır, el sağa/sola gezdikçe pencere seçilir, bırakınca açılır |
| 🤏 Orta pinch — **dikey sürükle** | Görev Görünümü / Masaüstünü Göster |
| 🤏 Yüzük pinch — **4 yön sürükle** | Geri / İleri / Pencereyi Büyüt / Sekme Kapat |
| 🤏 Orta / Yüzük / Serçe — **tak** | Yeni Sekme / Kopyala / Yapıştır |
| 🙂 **Yüz Modu** (Ctrl+Shift+Space) | Kaş kaldır = Alt-Tab · Ağız aç = Oynat/Duraklat · Göz kırp = Geri/İleri |

Tüm eşlemeler ayarlar panelinden özelleştirilebilir; kısayol alanına `app:` öneki
yazılırsa uygulama başlatır (örn. `app:spotify:`).

## Mimari (Özet)

```
                        ┌─────────────────────────────┐
 Webcam ──► OpenCV ──►  │  GestureEngine (QThread)    │
 1280x720 (16:9 FOV)    │  • MediaPipe HandLandmarker │──► Qt Sinyalleri ──► main.py
 → 640px'e küçült       │  • MediaPipe FaceLandmarker │     (pinch_tap, swipe,      
                        │  • Pinch durum makinesi     │      scroll_delta, carousel,
                        │  • Blendshape durum makinesi│      face_triggered, ...)
                        └─────────────────────────────┘              │
                                                                     ▼
        ┌────────────────────┬───────────────────────┬──────────────────────────┐
        │ ActionExecutor     │ OverlayWindow         │ SettingsWindow (PyQt6)   │
        │ • pyautogui hotkey │ • Click-through HUD   │ • Canlı kamera telemetri │
        │ • Win32 raw scroll │ • Mod pili + toast    │ • Jest eşleme editörü    │
        │ • Alt-Tab keyDown/ │   bildirimleri        │ • Hassasiyet kalibrasyonu│
        │   keyUp yönetimi   │                       │                          │
        └────────────────────┴───────────────────────┴──────────────────────────┘
                 + HotkeyListener (Win32 RegisterHotKey, çoklu global kısayol)
```

**Kritik tasarım kararları:**

1. **Mutlak konum yerine ayrık komutlar.** İmleci parmakla havada konumlandırmak hem
   yorucu (gorilla arm sendromu) hem isabetsizdir. V4 tamamen olay tabanlıdır:
   tap, swipe, karusel.
2. **Pinch + histerezis.** Pinch, parmak ucu mesafesinin el boyutuna (bilek→orta MCP)
   normalize edilmesiyle algılanır. Kapanma eşiği 0.40, açılma eşiği 0.60 — bu fark
   (histerezis), V3'teki "jest titremesi"ni yapısal olarak çözer.
3. **Touchpad metaforu.** Pinch'in kendisi "dokunma anı"dır: pinch yap → sürükle →
   bırak. Jestin başlangıcı/bitişi netleşir, yanlış tetikleme düşer.
4. **Belirsizlik koruması.** En yakın iki parmak da pinch eşiğindeyse (yumruk vb.)
   jest reddedilir.
5. **Yüz modu = MediaPipe blendshapes.** 52 ifade katsayısı; eşik + tutma süresi
   (250ms, normal göz kırpma ~150ms olduğundan elenir) + tek-göz şartıyla wink ayrımı.
6. **Güvenli durum yönetimi.** Alt-Tab karuseli Alt'ı fiziksel olarak basılı tutar;
   el kaybı, mod kapatma ve çıkış dahil her yolda `release_all()` garantisi vardır.
7. **Tam FOV.** 640x480 (4:3) zorlaması 16:9 sensörlerde görüntüyü kırpar; kamera
   MJPG + 1280x720 ile açılır, işleme için 640px'e küçültülür (aynı CPU maliyeti).

## Kurulum

```bash
pip install -r requirements.txt
python main.py
```

- **Gereksinimler:** Windows 10/11, Python 3.10+, herhangi bir webcam.
- `hand_landmarker.task` ve `face_landmarker.task` model dosyaları repoda hazır gelir.
- **Ctrl+Space** → el takibini aç/kapat · **Ctrl+Shift+Space** → yüz modunu aç/kapat.

## Öğrendiklerimiz (Neden Arşivlendi?)

Dört sürümün ardından vardığımız sonuç: sağlıklı bir kullanıcı için laptop'ta webcam
jestleri klavyeyle rekabet edemiyor. Klavye kısayolu her koşulda ~200ms'de biter;
kamera + model gecikmesi + ışık bağımlılığı bu çıtanın altına tutarlı şekilde inemiyor.
Bu teknolojinin gerçek değeri, Google Project Gameface'in de hedeflediği
**erişilebilirlik** alanında — klavyeye alternatif olarak değil, klavye kullanamayanlara
klavye olarak. Proje bu nedenle "başarısız" değil, **sorusu cevaplanmış** bir deney
olarak arşivlendi. Teknik kazanımlar (histerezisli jest durum makineleri, MediaPipe
entegrasyonu, Win32 input simülasyonu, click-through overlay) sonraki projelere taşındı.

## Lisans

MIT — dilediğiniz gibi kullanın.
