# 🍓 Panduan Lengkap Migrasi & Eksekusi ADITS di Raspberry Pi 4
**ADITS (Audio-Driven IoT Task Scheduler) — Robot Seni Tari Indonesia (KRSTI)**  
**Tim Peneliti Dewantara — Universitas Negeri Malang**

Panduan ini memandu pemindahan seluruh paket proyek dari laptop/PC Windows ke **Raspberry Pi 4 Model B (4GB / 8GB RAM)** sebagai *onboard edge computer* mandiri pada robot tari.

---

## 📦 1. Cara Memindahkan Folder Proyek ke Raspberry Pi 4

Folder utama yang dipindahkan cukup folder:
`ADITS_ROBOT_TARI_SIAP_PAKAI`

Pilih salah satu metode pemindahan berikut:

### Opsi A: Menggunakan Flashdisk USB (Paling Mudah & Offline)
1. Salin (*copy*) folder `ADITS_ROBOT_TARI_SIAP_PAKAI` ke Flashdisk USB (format FAT32 atau exFAT).
2. Tancapkan Flashdisk ke Raspberry Pi 4.
3. Buka File Manager di Raspberry Pi, salin folder tersebut ke direktori Home (`/home/<username>/` atau `~/`).

### Opsi B: Menggunakan SCP / Jaringan Lokal (WiFi / Hotspot HP)
Buka terminal PowerShell di laptop Windows (pastikan laptop dan Raspberry Pi berada dalam 1 jaringan WiFi yang sama):
```powershell
scp -r "C:\Users\HYPE AMD\OneDrive - Universitas Negeri Malang\Documents\ELEKTRONIKA_DAN_IOT\04_Projek_Robotika_dan_Lainnya\bantu robot tari\ADITS_ROBOT_TARI_SIAP_PAKAI" pi@<IP_RASPBERRY_PI>:~/
```
*(Ganti `<IP_RASPBERRY_PI>` dengan alamat IP Pi 4, misal `192.168.1.15`, dan `pi` dengan username Pi kamu).*

### Opsi C: Menggunakan FileZilla / WinSCP
1. Hubungkan ke Raspberry Pi via protokol SFTP (Port 22) menggunakan IP, username, dan password Pi 4.
2. Drag and drop folder `ADITS_ROBOT_TARI_SIAP_PAKAI` ke folder `~/`.

---

## 🔌 2. Wiring Hardware pada Raspberry Pi 4

```
+-------------------------------------------------------------+
|                     RASPBERRY PI 4                          |
|  [Port USB-C]       <- Adaptor 5V 3A                        |
|  [Port USB 3.0 #1]  <- ROBOTIS U2D2 Converter               |
|  [Port USB 2.0 #2]  <- USB Mic / Receiver Nirkabel AB13X    |
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
> 1. Raspberry Pi 4 disuplai daya terpisah via port USB-C (5V 3A).
> 2. Motor servo Dynamixel XL-320 **TIDAK BISA** ditenagai dari port USB Raspberry Pi 4 / U2D2. Motor membutuhkan tegangan **7.4V** dari PCB Ungu AERORA (diberi input adaptor 12V dan saklar posisi **ON**).

---

## ⚡ 3. Instalasi Lingkungan & Library Otomatis (1-Klik)

Buka terminal di Raspberry Pi 4, masuk ke folder proyek, dan jalankan skrip instalasi yang sudah disiapkan:

```bash
cd ~/ADITS_ROBOT_TARI_SIAP_PAKAI

# Beri izin eksekusi
chmod +x setup_rpi4.sh

# Jalankan instalasi otomatis
./setup_rpi4.sh
```

**Skrip `setup_rpi4.sh` ini otomatis melakukan:**
1. Instalasi dependensi C/ALSA PortAudio & build tools.
2. Memasukkan user aktif ke grup `dialout` (akses serial U2D2 tanpa butuh `sudo`) dan grup `audio`.
3. Menyetel aturan kernel Linux agar FTDI latency timer U2D2 otomatis menjadi **1 ms** (wajib agar komunikasi Dynamixel pada kecepatan 1 Mbps responsif dan tidak timeout).
4. Membuat virtual environment Python (`venv`) sesuai aturan PEP 668 Debian 12 Bookworm.
5. Menginstal `dynamixel-sdk`, `lightgbm`, `librosa`, `scikit-learn`, `pyaudio`, `psutil`, dll.

> [!NOTE]
> Setelah skrip instalasi selesai, **sangat disarankan untuk melakukan reboot** sekali saja agar izin grup `dialout` aktif sempurna:
> ```bash
> sudo reboot
> ```

---

## 🔍 4. Tahapan Verifikasi & Diagnostik Sistem

Masuk kembali ke terminal Pi 4 dan aktifkan virtual environment:
```bash
cd ~/ADITS_ROBOT_TARI_SIAP_PAKAI
source venv/bin/activate
```

### Tahap 1: Diagnostik Hardware Pi 4 (CPU, Suhu, Mic ALSA, Serial Port)
Jalankan skrip diagnostik perangkat keras:
```bash
python test_rpi4_hardware.py
```
*Hasil yang diharapkan:*
- CPU Cortex-A72 & Suhu SoC terdeteksi (< 70°C).
- Port `/dev/ttyUSB0` terdeteksi dengan status `[OPTIMAL: Latency Timer 1ms]`.
- Input mikrofon ALSA menangkap sinyal dengan level RMS normal.
- Latensi inferensi LightGBM rata-rata terukur **< 15 ms** (sangat cepat).

### Tahap 2: Diagnostik Komunikasi Motor Servo Dynamixel XL-320
Pastikan adaptor 12V dicolokkan ke PCB ungu dan saklar ON, lalu jalankan:
```bash
python test_dynamixel_xl320_scan.py
```
*Fitur skrip ini:*
- Memindai ID servo 1 s/d 20 pada port `/dev/ttyUSB0` (Protocol 2.0).
- Membaca tegangan servo secara live (harus berada di rentang **7.0V - 7.5V**).
- Menguji kedip lampu LED pada servo (Merah -> Hijau -> Biru -> Putih) sebagai bukti fisik servo merespons sinyal dari Raspberry Pi 4.

### Tahap 3: Menjalankan Kontroler Utama ADITS
Jalankan program kontroler terpadu:
```bash
python adits_unified_voice_dsp_internal.py
```
Robot kini siap menerima perintah suara (*MULAI, STOP, LANJUT, BERDIRI, DUDUK*) secara live via mikrofon, mengeksekusi penjadwal tugas preemptif P0-P3, dan menyelaraskan gerak tari dengan alunan musik gamelan KRSTI.

### Tahap 4: Menjalankan Web Dashboard & Data Acquisition Hub di Raspberry Pi
Kamu juga bisa menjalankan antarmuka web modern langsung di Raspberry Pi:
```bash
bash run_raspy.sh
# Atau secara manual:
python3 run_web_dashboard.py
```
Setelah server online:
- **Di layar Raspberry Pi**: Buka browser Chromium di `http://localhost:5000`
- **Dari Laptop / HP**: Buka browser (Chrome/Edge/Safari) di `http://<IP_RASPBERRY_PI>:5000` (misal `http://192.168.1.15:5000`).
Semua kontrol vokal, monitoring sinyal mikrofon, dan tabel akuisisi data otomatis dapat diakses dan di-*copy* langsung ke Excel laporan!
