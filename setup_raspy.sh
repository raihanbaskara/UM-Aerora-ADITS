#!/bin/bash
# ==============================================================================
# SKRIP OTOMATISASI INSTALASI ADITS (UNIVERSAL RASPBERRY PI 4 & 5)
# OS: Raspberry Pi OS 64-bit (Debian 12 Bookworm)
# Hardware: Raspberry Pi 4 Model B (4GB/8GB) & Raspberry Pi 5
# Tim Peneliti Dewantara -- KRSTI Universitas Negeri Malang
# ==============================================================================

set -e

BOARD_MODEL="Linux Perangkat Tertanam"
if [ -f "/proc/device-tree/model" ]; then
    BOARD_MODEL=$(tr -d '\0' < /proc/device-tree/model)
fi

echo "===================================================================="
echo "  [ADITS] SETUP DEPENDENSI & LINGKUNGAN SISTEM ROBOT TARI"
echo "  Perangkat Terdeteksi: $BOARD_MODEL"
echo "===================================================================="

ACTUAL_USER="${SUDO_USER:-$USER}"

# 1. Update & instal library sistem C, ALSA, PortAudio, dan USB Serial
echo -e "\n[1/5] Menginstal dependensi sistem C, ALSA, PortAudio, dan USB Tools..."
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

# Pastikan permission folder kerja dimiliki user aktif
sudo chown -R "$ACTUAL_USER":"$ACTUAL_USER" .
sudo chmod -R u+rwX .

# 3. Buat Virtual Environment Python (Sesuai Aturan PEP 668 Debian 12)
echo -e "\n[4/5] Menyiapkan Virtual Environment Python (venv)..."
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment 'venv' berhasil dibuat."
else
    echo "Virtual environment 'venv' sudah tersedia."
fi

# Aktifkan venv
source venv/bin/activate

# 4. Instal pustaka Python via requirements.txt
echo -e "\n[5/5] Menginstal dependensi pustaka Python untuk Edge AI & Robot Controller..."
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install \
        numpy pandas scipy soundfile librosa scikit-learn lightgbm joblib \
        openpyxl psutil pygame pyaudio matplotlib seaborn dynamixel-sdk \
        fastapi uvicorn websockets
fi

# 5. Uji Verifikasi Akhir
echo -e "\n>>> Menjalankan Verifikasi Diagnostik Hardware Otomatis..."
python3 test_hardware.py

echo ""
echo "===================================================================="
echo "  [SUKSES] INSTALASI ADITS PADA $BOARD_MODEL SELESAI!"
echo "  Catatan: Silakan jalankan 'sudo reboot' sekali agar izin dialout aktif."
echo "===================================================================="
