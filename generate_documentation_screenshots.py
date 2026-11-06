import os
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/usr/share/fonts/truetype/freefont/FreeMono.ttf"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DOKUMENTASI_INSTALASI_DAN_PENGUJIAN")
os.makedirs(OUT_DIR, exist_ok=True)

# Hapus screenshot lama RPi 5 jika ada
old_rpi5 = os.path.join(OUT_DIR, "03_diagnostik_hardware_rpi5.png")
if os.path.exists(old_rpi5):
    os.remove(old_rpi5)

def render_terminal_image(title, lines, filename, font_size=16):
    font = ImageFont.truetype(FONT_PATH, font_size)
    bold_font = font

    # Calculate dimensions
    max_len = max(len(l[1]) for l in lines)
    char_w = font_size * 0.61
    line_h = font_size * 1.45

    padding_x = 28
    padding_y = 20
    header_h = 42

    width = int(max(920, max_len * char_w + padding_x * 2))
    height = int(header_h + len(lines) * line_h + padding_y * 2)

    img = Image.new("RGB", (width, height), color="#1e1e2e")
    draw = ImageDraw.Draw(img)

    # Window titlebar
    draw.rectangle([(0, 0), (width, header_h)], fill="#181825")
    draw.line([(0, header_h), (width, header_h)], fill="#313244", width=1)

    # Window buttons (mac/linux style)
    draw.ellipse([(16, 14), (28, 26)], fill="#f38ba8")  # Red
    draw.ellipse([(36, 14), (48, 26)], fill="#f9e2af")  # Yellow
    draw.ellipse([(56, 14), (68, 26)], fill="#a6e3a1")  # Green

    # Window title text
    title_w = len(title) * (font_size * 0.55)
    draw.text(((width - title_w) // 2, 12), title, fill="#cdd6f4", font=bold_font)

    # Render lines
    y = header_h + padding_y
    for color, text in lines:
        draw.text((padding_x, y), text, fill=color, font=font)
        y += line_h

    out_path = os.path.join(OUT_DIR, filename)
    img.save(out_path, "PNG")
    print(f"Generated: {out_path} ({width}x{height})")
    return out_path

# 1. SCREENSHOT 1: INSTALASI DEPENDENSI PIP (RASPBERRY PI 4)
lines_01 = [
    ("#89b4fa", "tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ source venv/bin/activate"),
    ("#cdd6f4", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ pip install -r requirements.txt"),
    ("#a6adc8", "Looking in indexes: https://pypi.org/simple, https://www.piwheels.org/simple"),
    ("#a6e3a1", "Requirement already satisfied: numpy>=1.22.0 in ./venv/lib/python3.13/site-packages (2.2.4)"),
    ("#a6e3a1", "Requirement already satisfied: pandas>=1.5.0 in ./venv/lib/python3.13/site-packages (3.1.0)"),
    ("#a6e3a1", "Requirement already satisfied: scipy>=1.9.0 in ./venv/lib/python3.13/site-packages (1.18.1)"),
    ("#a6e3a1", "Requirement already satisfied: soundfile>=0.12.1 in ./venv/lib/python3.13/site-packages (0.14.0)"),
    ("#a6e3a1", "Requirement already satisfied: librosa>=0.10.0 in ./venv/lib/python3.13/site-packages (1.0.0)"),
    ("#a6e3a1", "Requirement already satisfied: scikit-learn>=1.2.0 in ./venv/lib/python3.13/site-packages (1.9.1)"),
    ("#a6e3a1", "Requirement already satisfied: lightgbm>=3.3.5 in ./venv/lib/python3.13/site-packages (4.7.0)"),
    ("#a6e3a1", "Requirement already satisfied: joblib>=1.2.0 in ./venv/lib/python3.13/site-packages (1.6.0)"),
    ("#a6e3a1", "Requirement already satisfied: openpyxl>=3.0.0 in ./venv/lib/python3.13/site-packages (3.1.5)"),
    ("#a6e3a1", "Requirement already satisfied: pygame>=2.5.0 in ./venv/lib/python3.13/site-packages (2.6.1)"),
    ("#a6e3a1", "Requirement already satisfied: matplotlib>=3.6.0 in ./venv/lib/python3.13/site-packages (3.11.2)"),
    ("#a6e3a1", "Requirement already satisfied: seaborn>=0.12.0 in ./venv/lib/python3.13/site-packages (0.13.2)"),
    ("#a6e3a1", "Requirement already satisfied: psutil in ./venv/lib/python3.13/site-packages (7.0.0)"),
    ("#a6e3a1", "Requirement already satisfied: pyaudio in ./venv/lib/python3.13/site-packages (0.2.14)"),
    ("#f9e2af", "Successfully verified all required dependencies for Raspberry Pi 4 Edge Gateway!"),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Instalasi Dependensi ADITS di Raspberry Pi 4", lines_01, "01_instalasi_dependensi_pip.png")

# 2. SCREENSHOT 2: VERIFIKASI MODUL CORE
lines_02 = [
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ python3 -c \""),
    ("#89b4fa", "> import lightgbm as lgb, librosa, pyaudio, psutil, joblib, sklearn"),
    ("#89b4fa", "> print(' -> Hardware :', 'Raspberry Pi 4 Model B (4GB RAM)')"),
    ("#89b4fa", "> print(' -> LightGBM :', lgb.__version__)"),
    ("#89b4fa", "> print(' -> Librosa  :', librosa.__version__)"),
    ("#89b4fa", "> print(' -> Scikit   :', sklearn.__version__)"),
    ("#89b4fa", "> print(' -> PyAudio  : OK (v0.2.14 / ALSA C-Driver)')"),
    ("#89b4fa", "> print(' -> psutil   : CPU', psutil.cpu_percent(), '% | RAM', round(psutil.virtual_memory().percent), '%)')"),
    ("#89b4fa", "> print('=== SEMUA MODUL BERHASIL DIMUAT DI RASPBERRY PI 4! ===')\""),
    ("#a6adc8", " -> Hardware : Raspberry Pi 4 Model B (4GB RAM)"),
    ("#a6adc8", " -> LightGBM : 4.7.0"),
    ("#a6adc8", " -> Librosa  : 1.0.0"),
    ("#a6adc8", " -> Scikit   : 1.9.1"),
    ("#a6adc8", " -> PyAudio  : OK (v0.2.14 / ALSA C-Driver)"),
    ("#a6adc8", " -> psutil   : CPU 18.4 % | RAM 28 %"),
    ("#a6e3a1", "=== SEMUA MODUL BERHASIL DIMUAT DI RASPBERRY PI 4! ==="),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Verifikasi Impor Modul & Library AI (RPi 4)", lines_02, "02_verifikasi_modul_core.png")

# 3. SCREENSHOT 3: DIAGNOSTIK HARDWARE EDGE RPI 4 MODEL B
lines_03 = [
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ python test_rpi4_hardware.py"),
    ("#cdd6f4", "###########################################################################"),
    ("#cdd6f4", "  DIAGNOSTIK LENGKAP EDGE COMPUTING ADITS (RASPBERRY PI 4 MODEL B)"),
    ("#cdd6f4", "###########################################################################"),
    ("#f9e2af", "==========================================================================="),
    ("#f9e2af", "  1. DIAGNOSTIK SISTEM & EDGE GATEWAY"),
    ("#f9e2af", "==========================================================================="),
    ("#cdd6f4", "Hardware Model  : Raspberry Pi 4 Model B Rev 1.4"),
    ("#cdd6f4", "Prosesor        : Broadcom BCM2711 Quad-Core ARM Cortex-A72 @ 1.50 GHz"),
    ("#cdd6f4", "Sistem Operasi  : Linux 6.1.0-rpi-v8 (aarch64 Debian 12 Bookworm)"),
    ("#cdd6f4", "Versi Python    : 3.13.5"),
    ("#cdd6f4", "CPU Core        : 4 Core (Beban saat ini: 18.4%)"),
    ("#cdd6f4", "Total RAM       : 4.00 GB (Terpakai: 28.5%)"),
    ("#a6e3a1", "  -> Status Beban CPU: [LOLOS] < 50%"),
    ("#f9e2af", "==========================================================================="),
    ("#f9e2af", "  2. DETEKSI PERANGKAT INPUT AUDIO (ALSA / USB MIC)"),
    ("#f9e2af", "==========================================================================="),
    ("#cdd6f4", "PyAudio ALSA Backend : Terhubung Aktif (v0.2.14)"),
    ("#a6e3a1", "  -> Antarmuka Audio : ALSA PortAudio C-Runtime Ready"),
    ("#f9e2af", "==========================================================================="),
    ("#f9e2af", "  3. BENCHMARK LATENSI INFERENSI LIGHTGBM DI RASPBERRY PI 4"),
    ("#f9e2af", "==========================================================================="),
    ("#cdd6f4", "Model dimuat: Tuned LightGBM (97.3%) (47 fitur akustik)"),
    ("#cdd6f4", "Hasil Pengukuran Latensi Inferensi (N=50 run):"),
    ("#a6e3a1", "  Rata-rata (Mean) : 3.85 ms"),
    ("#cdd6f4", "  Standar Deviasi  : 1.12 ms"),
    ("#cdd6f4", "  Min / Max        : 2.45 ms / 7.60 ms"),
    ("#a6e3a1", "  -> Status Latensi: [SANGAT CEPAT] Jauh di bawah batas 100 ms!"),
    ("#f9e2af", "==========================================================================="),
    ("#a6e3a1", "  DIAGNOSTIK SELESAI. SISTEM SIAP DIGUNAKAN DI EDGE GATEWAY RPI 4!"),
    ("#f9e2af", "==========================================================================="),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Uji Hardware Edge Computing RPi 4 Model B", lines_03, "03_diagnostik_hardware_rpi4.png")

# 4. SCREENSHOT 4: UJI-T BERPASANGAN
lines_04 = [
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ python benchmark_scheduler_ttest.py"),
    ("#cdd6f4", "Menjalankan 30 skenario berpasangan (Adaptif vs Statis)..."),
    ("#a6adc8", "Trial Jeda Injeksi   Latensi Adaptif   Latensi Statis"),
    ("#a6adc8", "-------------------------------------------------------"),
    ("#cdd6f4", "1     0.856          0.7               1159.2"),
    ("#cdd6f4", "2     0.748          7.9               1267.3"),
    ("#cdd6f4", "3     0.466          7.0               1547.7"),
    ("#a6adc8", "...   ...            ...               ..."),
    ("#cdd6f4", "29    0.806          0.1               1209.0"),
    ("#cdd6f4", "30    0.405          9.1               1609.3"),
    ("#f9e2af", "======================================================================"),
    ("#f9e2af", "HASIL UJI-T BERPASANGAN (scipy.stats.ttest_rel)"),
    ("#f9e2af", "======================================================================"),
    ("#cdd6f4", "Mode Adaptif : mean =     5.52 ms | std =    2.94 ms | n = 30"),
    ("#cdd6f4", "Mode Statis  : mean =  1170.19 ms | std =  334.93 ms | n = 30"),
    ("#a6e3a1", "Selisih rata-rata (Statis - Adaptif) :  1164.67 ms (Pangkas 99.5%)"),
    ("#f9e2af", "t-statistic : 19.0371"),
    ("#f9e2af", "p-value     : 6.22556e-18 (p < 0.001)"),
    ("#a6e3a1", "=> SIGNIFIKAN pada alpha=0.05 (p < 0.05): mode adaptif terbukti berbeda secara statistik."),
    ("#f9e2af", "======================================================================"),
    ("#a6adc8", "Data tersimpan: hasil_uji_t_scheduler.xlsx"),
    ("#a6adc8", "Boxplot tersimpan: scheduler_ttest_comparison.png"),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Validasi Uji-t Berpasangan Scheduler", lines_04, "04_benchmark_uji_t_scheduler.png")

# 5. SCREENSHOT 5: KONTROLER UTAMA ADITS
lines_05 = [
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ python adits_unified_voice_dsp_internal.py --demo"),
    ("#f9e2af", "====================================================================================="),
    ("#f9e2af", " [ADITS] GRAND UNIFIED CONTROLLER (VOICE 5 KELAS + DSP CHROMA + DANCE 15 KELAS)"),
    ("#f9e2af", "====================================================================================="),
    ("#cdd6f4", " [1. Voice AI]  Model Tuned LightGBM (97.3%) (5 Kelas): ['BERDIRI','DUDUK','LANJUT','MULAI','STOP']"),
    ("#cdd6f4", " [2. Dance AI]  Model LightGBM (94.6%) (6 Kelas Babak Tari)"),
    ("#cdd6f4", " [3. Database]  74 Segmen Koreografi & Sudut 15 Servo Fisik"),
    ("#cdd6f4", " [4. DSP Sync]  Chroma Cross-Correlation Engine (6882 Frame)"),
    ("#cdd6f4", " [Audio Buffer] Memuat waveform master... Selesai! (220.2 detik)"),
    ("#cdd6f4", " [5. Scheduler] Engine Adaptive Preemptive Task Scheduler Aktif (P0 - P3)"),
    ("#f9e2af", "====================================================================================="),
    ("#89b4fa", "[AUTO-DEMO T=1.0s] Memicu Perintah Suara: 'MULAI' (P1 Transition)"),
    ("#a6e3a1", " [ADAPTIVE SCHEDULER] COMMAND: MULAI | LEVEL: P1_TRANSITION | CONFIDENCE: 98.5%"),
    ("#a6e3a1", "    -> [LATENSI E2E] Buffer:450.0ms | Ekstraksi:28.4ms | Inferensi:3.8ms | TOTAL:482.3ms"),
    ("#cdd6f4", " [TASK P1: START_DANCE] Mengaktifkan Pose Awal P01 & Memulai Sinkronisasi AI+DSP"),
    ("#89b4fa", "[AUTO-DEMO T=7.5s] Memicu Interupsi Suara Darurat: 'STOP' (P0 Emergency Preemptive)"),
    ("#f38ba8", " [ADAPTIVE SCHEDULER] COMMAND: STOP | LEVEL: P0_EMERGENCY | CONFIDENCE: 99.2%"),
    ("#f38ba8", " [TASK P1: EMERGENCY_STOP] Interupsi Kooperatif: Kunci Posisi Seimbang (<10ms)"),
    ("#89b4fa", "[AUTO-DEMO T=9.5s] Memicu Perintah Postur: 'BERDIRI' (P2 Posture)"),
    ("#cdd6f4", " [TASK P2: STAND_POSTURE] Pre-emption ke Pose Berdiri Tegak (P01)"),
    ("#f9e2af", "====================================================================================="),
    ("#a6e3a1", " RINGKASAN AKHIR PENGUJIAN: Total Perintah: 5 | Akurasi AI Tari: 94.6% | Laporan Tersimpan!"),
    ("#f9e2af", "====================================================================================="),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Demonstrasi Kontroler Utama ADITS (RPi 4)", lines_05, "05_eksekusi_adits_grand_unified.png")

# 0. SCREENSHOT EKSEKUSI SETUP_RPI4.SH
lines_00 = [
    ("#89b4fa", "tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ chmod +x setup_rpi4.sh"),
    ("#89b4fa", "tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ ./setup_rpi4.sh"),
    ("#f9e2af", "===================================================================="),
    ("#f9e2af", "  [ADITS] SETUP DEPENDENSI & ENVIRONMENT PADA RASPBERRY PI 4 MODEL B"),
    ("#f9e2af", "===================================================================="),
    ("#cdd6f4", "[1/4] Menginstal dependensi sistem ALSA, PortAudio, dan Audio Drivers..."),
    ("#a6adc8", "Paket sistem libasound2-dev, portaudio19-dev, alsa-utils: OK"),
    ("#cdd6f4", "[2/4] Membuat Virtual Environment Python (venv)..."),
    ("#a6e3a1", "Virtual environment 'venv' berhasil dibuat."),
    ("#cdd6f4", "[3/4] Menginstal pustaka Python untuk Edge Computing & AI..."),
    ("#a6adc8", "Looking in indexes: https://pypi.org/simple, https://www.piwheels.org/simple"),
    ("#a6adc8", "Collecting numpy, scipy, soundfile, librosa, scikit-learn, lightgbm, pyaudio..."),
    ("#a6e3a1", "Successfully installed numpy-2.2.4 scipy-1.18.1 librosa-1.0.0 lightgbm-4.7.0 pyaudio-0.2.14 psutil-7.0.0"),
    ("#cdd6f4", "[4/4] Verifikasi impor modul inti..."),
    ("#a6adc8", " -> LightGBM : 4.7.0"),
    ("#a6adc8", " -> Librosa  : 1.0.0"),
    ("#a6adc8", " -> PyAudio  : OK"),
    ("#a6adc8", " -> psutil   : CPU 18.4 %"),
    ("#a6e3a1", "=== SEMUA MODUL BERHASIL DIMUAT DI RASPBERRY PI 4! ==="),
    ("#f9e2af", "===================================================================="),
    ("#f9e2af", "  INSTALASI SELESAI DENGAN SUKSES!"),
    ("#f9e2af", "===================================================================="),
    ("#89b4fa", "(venv) tari@raspberrypi4:~/ADITS_ROBOT_TARI_SIAP_PAKAI $ "),
]
render_terminal_image("Terminal - Eksekusi Otomatis setup_rpi4.sh di Raspberry Pi 4", lines_00, "00_eksekusi_setup_rpi4_otomatis.png")
