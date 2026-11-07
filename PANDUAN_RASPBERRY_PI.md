# 📖 Panduan Lengkap Eksekusi ADITS di Raspberry Pi (Universal Pi 4 & Pi 5)
**ADITS (Audio-Driven IoT Task Scheduler) — Robot Seni Tari Indonesia (KRSTI)**  
**Tim Peneliti Dewantara — Universitas Negeri Malang (UM)**

Panduan ini memandu konfigurasi perangkat keras, instalasi dependensi, diagnostik sistem, dan eksekusi ADITS pada **Raspberry Pi 4 Model B** maupun **Raspberry Pi 5** sebagai *onboard edge computer* robot tari.

---

## 🔌 1. Diagram Pengkabelan & Wiring Hardware

```
+-------------------------------------------------------------+
|               RASPBERRY PI (EDGE COMPUTER)                  |
|  [Port USB-C]       <- Adaptor Daya Resmi 5V (3A - 5A)      |
|  [Port USB 3.0 #1]  <- ROBOTIS U2D2 Converter (Warna Biru)  |
|  [Port USB 2.0 #2]  <- USB Mic / Receiver AB13X (Hitam)     |
+-------------------------------------------------------------+
                               | (Kabel TTL 3-Pin)
                               v
+-------------------------------------------------------------+
|              PCB UNGU AERORA KRSTI 2023                     |
|  [DC Jack 12V]      <- Adaptor DC 12V (2A - 5A) / LiPo 3S   |
|  [Saklar Power]     <- Posisi ON (LED Indikator Menyala)    |
|  [Buck Step-Down]   <- Menghasilkan 7.4V stabil untuk servo |
+-------------------------------------------------------------+
                               | (Kabel JST-ZH 3-Pin)
                               v
+-------------------------------------------------------------+
|              DAISY-CHAIN DYNAMIXEL XL-320 SERVOS            |
|       [ID 1: Kepala] <---> [ID 2..8: Tangan] <---> ...      |
+-------------------------------------------------------------+
```

> [!IMPORTANT]
> **Kelistrikan Wajib Diperhatikan:**
> 1. Raspberry Pi disuplai daya terpisah via port USB-C (5V 3A untuk Pi 4, atau 5V 5A untuk Pi 5).
> 2. Motor servo Dynamixel XL-320 **TIDAK BISA** ditenagai dari port USB Raspberry Pi / U2D2. Motor membutuhkan tegangan **7.4V** dari PCB Ungu AERORA (diberi input adaptor 12V dan saklar posisi **ON**).

---

## ⚡ 2. Instalasi Lingkungan & Library Otomatis (1-Klik)

Buka terminal di Raspberry Pi, masuk ke folder proyek, dan jalankan skrip instalasi universal yang otomatis mengenali tipe board kamu:

```bash
cd ~/UM-Aerora-ADITS

# Beri izin eksekusi
chmod +x setup_raspy.sh

# Jalankan instalasi otomatis
./setup_raspy.sh
```

**Skrip `setup_raspy.sh` otomatis melakukan:**
1. Deteksi model board (`Raspberry Pi 4` atau `Raspberry Pi 5`).
2. Instalasi dependensi sistem C/ALSA PortAudio & build tools.
3. Memasukkan user aktif ke grup `dialout` (akses serial U2D2 tanpa butuh `sudo`) dan grup `audio`.
4. Menyetel aturan kernel Linux agar FTDI latency timer U2D2 otomatis menjadi **1 ms** (wajib agar komunikasi Dynamixel pada kecepatan 1 Mbps responsif dan tidak timeout).
5. Membuat virtual environment Python (`venv`) sesuai aturan PEP 668 Debian 12 Bookworm.
6. Menginstal seluruh pustaka AI (`lightgbm`, `librosa`, `scikit-learn`, `dynamixel-sdk`, dll).

> [!NOTE]
> Setelah instalasi selesai, lakukan *reboot* sekali saja agar izin grup `dialout` aktif sempurna:
> ```bash
> sudo reboot
> ```

---

## 🩺 3. Uji Diagnostik Hardware Mandiri

Masuk kembali ke terminal Raspberry Pi, aktifkan virtual environment, dan jalankan uji diagnostik terpadu:

```bash
cd ~/UM-Aerora-ADITS
source venv/bin/activate

# 1. Diagnostik Lengkap (CPU, Suhu, Audio Mic RMS, Serial U2D2, Latensi AI)
python test_hardware.py

# 2. Pindai Motor Servo Dynamixel (Deteksi ID 1 s.d. 15 & Kedip LED)
python test_dynamixel_xl320_scan.py
```

---

## 🚀 4. Menjalankan Web Telemetry Dashboard & Voice AI Hub

Jalankan server sistem:
```bash
chmod +x run_raspy.sh
./run_raspy.sh
```
*Atau secara manual:*
```bash
python run_web_dashboard.py
```

Buka peramban (browser) di laptop atau ponsel yang berada dalam satu jaringan WiFi dengan Raspberry Pi, lalu akses:
```
http://<IP_RASPBERRY_PI>:5000
```
*(Contoh: `http://192.168.1.15:5000`)*

Dari antarmuka Web Dashboard, kamu dapat:
* Memantau *Live Waveform & Level Volume* mikrofon secara real-time.
* Menguji perintah suara (*Voice Command* 5-Kelas: STOP, MULAI, LANJUT, BERDIRI, DUDUK).
* Memantau latensi respons *preemption* ($< 10\text{ ms}$) dan beban CPU/RAM.
* Mengunduh rekap log eksperimen pengujian dalam format TSV/CSV.
