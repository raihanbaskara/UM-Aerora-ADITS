#!/bin/bash
# ==============================================================================
# SKRIP OTOMATISASI INSTALASI ADITS PADA RASPBERRY PI 4 (EDGE COMPUTING ROBOT)
# OS Rekomendasi: Raspberry Pi OS 64-bit (Debian 12 Bookworm)
# Hardware: Raspberry Pi 4 Model B (4GB / 8GB RAM)
# ==============================================================================

set -e

echo "===================================================================="
echo "  [ADITS] SETUP DEPENDENSI & ENVIRONMENT PADA RASPBERRY PI 4"
echo "  Tim Peneliti Dewantara - KRSTI Universitas Negeri Malang"
echo "===================================================================="

ACTUAL_USER="${SUDO_USER:-$USER}"

# 1. Update & instal library sistem C/ALSA PortAudio & build tools
echo -e "\n[1/5] Menginstal dependensi sistem C, ALSA, PortAudio, dan USB Serial..."
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    libopenblas-dev \
    libatlas-base-dev \
    alsa-utils \
    usbutils \
    git

# Instal libsdl2-mixer (untuk pygame/audio)
sudo apt install -y libsdl2-mixer-2.0-0 2>/dev/null || sudo apt install -y libsdl2-mixer-dev 2>/dev/null || true

# 2. Konfigurasi Hak Akses Serial (U2D2) & Audio untuk User Biasa
echo -e "\n[2/5] Menambahkan user '$ACTUAL_USER' ke grup 'dialout' dan 'audio'..."
sudo usermod -aG dialout,audio "$ACTUAL_USER"

# Konfigurasi udev rule untuk FTDI U2D2 Latency Timer = 1 ms (Wajib untuk Dynamixel 1 Mbps)
echo -e "\n[3/5] Mengoptimalkan FTDI Latency Timer ke 1 ms untuk ROBOTIS U2D2..."
cat << 'EOF' | sudo tee /etc/udev/rules.d/99-dynamixel-ftdi.rules > /dev/null
ACTION=="add", SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", ATTR{latency_timer}="1"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger || true

# Pastikan permission folder kerja
sudo chown -R "$ACTUAL_USER":"$ACTUAL_USER" .
sudo chmod -R u+rwX .

# 3. Buat Virtual Environment Python (Sesuai PEP 668 Debian 12)
echo -e "\n[4/5] Membuat Virtual Environment Python (venv)..."
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment 'venv' berhasil dibuat."
else
    echo "Virtual environment 'venv' sudah ada."
fi

# Aktifkan venv
source venv/bin/activate

# 4. Instal pustaka Python via pip
echo -e "\n[5/5] Menginstal pustaka Python untuk Edge AI & Dynamixel SDK..."
pip install --upgrade pip
pip install \
    numpy \
    pandas \
    scipy \
    soundfile \
    librosa \
    scikit-learn \
    lightgbm \
    joblib \
    openpyxl \
    psutil \
    pygame \
    pyaudio \
    matplotlib \
    seaborn \
    dynamixel-sdk \
    fastapi \
    uvicorn

# 5. Uji Verifikasi Akhir
echo -e "\n>>> Verifikasi Impor Modul Inti di Raspberry Pi 4..."
python3 -c "
import lightgbm as lgb
import librosa
import pyaudio
import psutil
import joblib
import dynamixel_sdk as dxl
print(' [OK] LightGBM      :', lgb.__version__)
print(' [OK] Librosa       :', librosa.__version__)
print(' [OK] PyAudio       : Terpasang')
print(' [OK] Dynamixel SDK : Terpasang')
print(' [OK] psutil        : CPU Penggunaan saat ini', psutil.cpu_percent(), '%')
print('=== SEMUA DEPENDENSI UTAMA RASPBERRY PI 4 BERHASIL DIKONFIGURASI! ===')
"

echo -e "\n===================================================================="
echo "  SETUP RASPBERRY PI 4 SELESAI DENGAN SUKSES!"
echo "===================================================================="
echo "PENTING: Jika baru pertama kali menambahkan grup dialout/audio, silakan"
echo "reboot Raspberry Pi agar permission USB U2D2 aktif sempurna:"
echo "  sudo reboot"
echo ""
echo "Cara Menjalankan:"
echo "  1. source venv/bin/activate"
echo "  2. python test_rpi4_hardware.py        (Cek CPU, Mic ALSA & Port U2D2)"
echo "  3. python test_dynamixel_xl320_scan.py (Scan & tes kedip LED servo XL-320)"
echo "  4. python adits_unified_voice_dsp_internal.py (Kontroler utama)"
echo "===================================================================="
