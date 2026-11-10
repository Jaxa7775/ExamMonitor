# Imtihon nazorati dasturi — qo'llanma

**Siz (o'qituvchi) kompyuteringiz = server.** Alohida server kerak emas.

## Fayllar
| Fayl | Nima |
|------|------|
| `teacher_server.py` | O'qituvchi serveri + boshqaruv oynasi |
| `student_client.py` | Talaba kompyuterida ishlaydigan klient |
| `config.ini` | Barcha sozlamalar (kod tahrirlanmaydi) |
| `run_server.bat` | Serverni ishga tushirish (2 marta bosing) |
| `build_client.bat` | Klientni `.exe` ga aylantirish |
| `install_client.bat` | Talaba kompyuteriga o'rnatish + avtomatik ishga tushirish |
| `uninstall_client.bat` | Talaba kompyuteridan olib tashlash |

## Imkoniyatlar
- **Avtomatik topish** — talaba klienti serverni o'zi topadi, IP yozish shart emas.
- **Live ekran ko'rish** — "Ekranlar" bo'limida talaba ekranlari real vaqtda; bosib kattalashtiriladi.
- **Oyna nazorati** — ruxsatsiz oyna ochilsa, qizil rang + ovoz + jurnalga yozuv.
- **Sayt / URL nazorati** — brauzer manzil satridagi URL o'qiladi; ruxsatsiz yoki bloklangan sayt ochilsa ogohlantiradi.
- **Xabar yuborish** — talaba ekraniga popup xabar (tanlangan yoki hammaga).
- **Masofadan boshqarish** — tanlangan talaba kompyuterini sichqoncha/klaviatura bilan boshqarish. Boshqaruv paytida talaba ekranida DOIM "⌨ Kompyuteringiz boshqarilyapti" yozuvi chiqadi (bu `show_banner` dan mustaqil).
- **Ekran ulashish** — o'qituvchi ekrani tanlangan yoki hamma talabaga to'liq ekranda ko'rinadi (prezentatsiya/namoyish uchun).
- **Mikrofon** — o'qituvchi ovozi barcha ulangan talabalarga real vaqtda eshitiladi.
- **Bloklash / ochish** va **ish stoliga fon qo'yish**.
- **Imtihon jurnali** — barcha hodisalar `logs\` papkasiga CSV (Excel'da ochiladi) qilib yoziladi.
- **Avtomatik ishga tushish** — `.exe` o'rnatilgach, kompyuter har yonganda klient o'zi ishga tushadi.

---

## 1-qadam. Sozlash (`config.ini`)
Repo'dan yuklab olgan bo'lsangiz, avval `config.example.ini` ni `config.ini` deb nusxalang.

`config.ini` ni oching va kamida `token` ni o'zgartiring. **Server va talaba kompyuterida token bir xil bo'lsin:**
```ini
[common]
token = sinf-7a-maxfiy     # o'zingizning maxfiy so'zingiz
port = 50200
discovery_port = 50201

[client]
server = auto              # auto = avtomatik topish (tavsiya etiladi)
screenshot_interval = 3.0  # ekran rasmini necha soniyada yangilash
screenshot_width = 480
```

## 2-qadam. Serverni ishga tushirish (o'qituvchi kompyuteri)
`run_server.bat` ni 2 marta bosing (yoki `py teacher_server.py`).
Oyna ochiladi — yuqorida server manzili ko'rinadi.

**Firewall (Administrator PowerShell):**
```powershell
New-NetFirewallRule -DisplayName "ExamMonitor TCP" -Direction Inbound -Protocol TCP -LocalPort 50200 -Action Allow
New-NetFirewallRule -DisplayName "ExamMonitor UDP" -Direction Inbound -Protocol UDP -LocalPort 50201 -Action Allow
New-NetFirewallRule -DisplayName "ExamMonitor Audio" -Direction Inbound -Protocol TCP -LocalPort 50202 -Action Allow
```
(UDP 50201 — avtomatik topish; TCP 50202 — mikrofon ovozi uchun.)

## 3-qadam. Klientni `.exe` qilish (bir marta, o'qituvchi kompyuterida)
`build_client.bat` ni ishga tushiring. Natija: `dist\student_client.exe`.
(Pillow .exe ichiga paketlanadi — talaba kompyuteriga Python o'rnatish shart emas.)

## 4-qadam. Talaba kompyuteriga o'rnatish
Bitta papkaga 4 ta faylni qo'ying va talaba kompyuteriga ko'chiring:
```
student_client.exe
config.ini
install_client.bat
uninstall_client.bat
```
Talaba kompyuterida **`install_client.bat`** ni ishga tushiring. U:
1. Fayllarni `C:\ExamMonitor\` ga ko'chiradi;
2. Avtomatik ishga tushishni yoqadi (har login qilinganda);
3. Dasturni darhol ishga tushiradi.

Ekran yuqorisida qizil **"● Imtihon nazorati faol"** belgisi chiqadi, serverda esa talaba ro'yxatda paydo bo'ladi.

Olib tashlash: `uninstall_client.bat`.

---

## Foydalanish
- **Ruxsat etilgan** maydoniga kalit so'z yozing (masalan `moodle, exam`). Talaba boshqa oyna/sayt ochsa — qatori qizarib, ovoz chiqadi, jurnalga yoziladi. Bo'sh qoldirsangiz — faqat kuzatuv.
- **Bloklangan saytlar** maydoni — bu yerdagi kalit so'z (masalan `youtube, telegram, chatgpt`) uchrasa, doim ogohlantiriladi (ruxsat ro'yxati bo'sh bo'lsa ham).
- **URL / sayt** ustuni — talaba brauzerda qaysi saytda ekanini ko'rsatadi (Chrome, Edge, Firefox, ...).
- **Ekranlar** bo'limi — barcha ekranlar; rasm ustiga 2 marta bosib kattalashtiring.
- **✉ Xabar** — tanlangan yoki hamma talabaga ekranda popup xabar yuborish.
- **🖱 Boshqarish** — ro'yxatdan BITTA talabani tanlab bosing; ochilган oynada uning ekrani ko'rinadi va sichqoncha/klaviatura bilan boshqarasiz (yozish uchun avval rasm ustiga bosing). Oynani yopsangiz — boshqaruv to'xtaydi. Talaba ekranida boshqaruv davomida "⌨ Kompyuteringiz boshqarilyapti" yozuvi turadi.
- **📺 Ekran ulash** — o'z ekraningizni tanlangan yoki hamma talabaga ko'rsatish; **⏹ Ulashni to'xtatish** — tugatish.
- **🎤 Mikrofon** — bosganda ovozingiz talabalarga eshitila boshlaydi; yana bossangiz — to'xtaydi.
- **🔒 / 🔓** — bloklash / ochish (tanlangan yoki hamma).
- **🖼 Fon** — rasm tanlab, talaba ish stoliga qo'yish.
- **🗒 Yangi jurnal** — yangi imtihon uchun yangi CSV fayl boshlaydi (`logs\` papkasida).
- Ko'p talabani tanlash: `Ctrl` yoki `Shift` bilan bosing.

### Sayt/URL nazorati haqida
- URL o'qish uchun `uiautomation` kutubxonasi ishlatiladi — u `build_client.bat` orqali `.exe` ichiga avtomatik paketlanadi (talaba kompyuteriga alohida o'rnatish shart emas).
- Agar biror brauzerda URL o'qilmasa (ba'zi versiyalarda manzil satri boshqacha), oyna nomi va dastur nomi bo'yicha nazorat baribir ishlayveradi.
- Tekshirish: klientni bir kompyuterda ishga tushirib, brauzerda sayt oching — serverdagi "URL / sayt" ustunida ko'rinishi kerak.

---

## "Serverga joylash" — muhim ko'nikmalar
- **Server = o'qituvchi kompyuteri.** Boshqa texnika shart emas.
- **IP muammosi yo'q:** `server = auto` tufayli talaba klienti serverni tarmoqdan o'zi topadi.
  (Agar bir nechta tarmoq adapteri bo'lsa ham, klient to'g'risini topadi.)
- **Faqat LAN.** Internetga ochmang / port-forward qilmang. Masofadan kerak bo'lsa — **VPN** ishlating
  (hamma bir virtual LAN'da bo'ladi), keyin `server` maydoniga VPN'dagi IP yozing.
- **Xavfsizlik:** `token` ni albatta o'zgartiring. Trafik LAN ichida shifrlanmagan — ochiq/ishonchsiz
  tarmoqda ishlatmang.

## Halollik
- Dastur **ochiq** ishlaydi: talaba ekranida nazorat belgisi doim turadi. Bu — qonuniy imtihon
  nazorati bilan yashirin josuslikni ajratadigan asosiy chiziq.
- Faqat o'z sinf kompyuterlaringizda, talabalar xabardor holatda ishlating.
- Blok vaqtinchalik va qaytariladigan; dastur hech narsani o'chirmaydi/buzmaydi.

## Cheklovlar
- Blok to'liq "kiosk" emas: ilg'or talaba Task Manager orqali jarayonni to'xtatishi mumkin.
  To'liq himoya uchun Windows Group Policy / kiosk rejim kerak.
- Mustahkam tayyor yechim: ochiq kodli **Veyon** (https://veyon.io) — xuddi shu ishni qiladi.
