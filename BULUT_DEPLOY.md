# Imtihon nazorati — BULUTLI versiya (Render'da bepul)

LAN versiyasidan farqi: endi server o'qituvchi kompyuterida emas, **internetdagi
bepul bulutli serverda** ishlaydi. O'qituvchi paneli **brauzerda** ochiladi.
Shu tufayli talabalar istalgan tarmoqdan (uy, boshqa bino) ulana oladi.

```
   Talaba kompyuterlari  ──wss──►  Render'dagi relay server  ◄──wss──  O'qituvchi (brauzer)
      (student_client)                 (cloud/server.py)                  (panel.html)
```

Server faqat xabar uzatuvchi (relay) — hech narsa diskka yozilmaydi, saqlanmaydi.
Render HTTPS/WSS beradi, ya'ni trafik **shifrlangan** (LAN versiyasidan xavfsizroq).

---

## 1-qadam. Render'da bepul server ochish

1. [https://render.com](https://render.com) da ro'yxatdan o'ting (GitHub bilan kirish qulay).
2. **New → Blueprint** tanlang.
3. GitHub repozitoriyangizni (`ExamMonitor`) ulang. Render `render.yaml` ni o'zi topadi.
4. Deploy'dan oldin **Environment** bo'limida `EXAM_TOKEN` ga maxfiy so'z kiriting
   (masalan `sinf-7a-maxfiy`). Shu token mijozlardagi `token` bilan **bir xil** bo'lsin.
5. **Apply / Create** bosing. 1–2 daqiqada tayyor bo'ladi.
6. Render sizga manzil beradi, masalan: `https://exammonitor-xxxx.onrender.com`

> **Bepul tarif eslatmasi:** server 15 daqiqa foydalanilmasa "uxlaydi". Keyingi
> ulanishda ~30 soniya uyg'onadi. Imtihon oldidan panelni bir marta ochib qo'ying.

---

## 2-qadam. O'qituvchi paneli (brauzer)

1. Render bergan manzilni brauzerda oching: `https://exammonitor-xxxx.onrender.com`
2. **Token** va **Sinf kodi** (masalan `7-A`) ni kiriting → **Ulanish**.
3. Talabalar ulanganda ro'yxat va ekranlar paydo bo'ladi.

Panel imkoniyatlari: live ekranlar, oyna/URL nazorati, ruxsat/blok kalit so'zlari,
🔒 bloklash / 🔓 ochish, ✉ xabar, 🖱 masofadan boshqaruv (sichqoncha+klaviatura),
ogohlantirish ovozi.

---

## 3-qadam. Talaba klientini tayyorlash (bir marta, o'qituvchi kompyuterida)

`cloud_client` papkasida:

1. `config.example.ini` ni `config.ini` deb nusxalang va to'ldiring:
   ```ini
   [common]
   token  = sinf-7a-maxfiy          ; Render'dagi EXAM_TOKEN bilan bir xil
   [client]
   server = wss://exammonitor-xxxx.onrender.com   ; Render manzili
   room   = 7-A                     ; paneldagi sinf kodi bilan bir xil
   ```
2. `build_client.bat` ni ishga tushiring → `dist\student_client.exe` hosil bo'ladi.
   (Python mijoz kompyuteriga kerak emas — hammasi .exe ichida.)

---

## 4-qadam. Talaba kompyuteriga o'rnatish

Bir papkaga 4 ta faylni qo'ying: `student_client.exe`, `config.ini`,
`install_client.bat`, `uninstall_client.bat`. Talaba kompyuterida
`install_client.bat` ni ishga tushiring.

- Fayllar `C:\ExamMonitor\` ga ko'chiriladi, har login'da avtomatik ishga tushadi.
- Ekran yuqorisida qizil **"● Imtihon nazorati faol"** belgisi chiqadi.
- Olib tashlash: `uninstall_client.bat`.

---

## Xavfsizlik va halollik

- **token** ni albatta o'zgartiring — bu begona qurilma ulanmasligining asosiy himoyasi.
- Dastur **ochiq** ishlaydi: talaba ekranida nazorat belgisi doim turadi, boshqaruv
  vaqtida "Kompyuteringiz boshqarilyapti" yozuvi chiqadi. Yashirin josuslik emas.
- Faqat o'z sinfingiz kompyuterlarida, talabalar xabardor holatda ishlating.

## Cheklovlar

- Bepul tarifda server uxlab qoladi (yuqoridagi eslatma) va trafik cheklangan —
  juda ko'p talaba + tez-tez yuboriladigan katta rasm sekinlashtirishi mumkin.
  `config.ini` da `screenshot_interval` ni oshiring yoki `screenshot_width` ni kamaytiring.
- Bu versiyada ovoz (mikrofon) va o'qituvchi ekranini ulashish yo'q (LAN versiyasida bor).
- Klient Windows uchun.
