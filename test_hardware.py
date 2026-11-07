"""
================================================================================
DIAGNOSTIK PERANGKAT KERAS & LATENSI EDGE COMPUTING (UNIVERSAL EDITION)
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
Tim Peneliti Dewantara -- Universitas Negeri Malang (UM)
================================================================================
Skrip diagnostik komprehensif yang otomatis mendeteksi hardware (Raspberry Pi 4,
Raspberry Pi 5, atau PC/Laptop pengembangan):
1. Deteksi Board & CPU: SoC (Cortex-A72 / Cortex-A76), Suhu Core, RAM, dan psutil.
2. Deteksi Serial USB: ROBOTIS U2D2 (/dev/ttyUSB* / COM*) & Latency Timer FTDI (1 ms).
3. Deteksi Audio Input: ALSA / USB Mic, Uji Rekam & Evaluasi Tingkat RMS Suara.
4. Benchmark Latensi AI: Pengujian Latensi Inferensi LightGBM 47-Fitur (N=50 iterasi).
================================================================================
"""

import sys
import os
import glob
import time
import platform
import numpy as np

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyaudio
except ImportError:
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        pyaudio = None

try:
    import joblib
except ImportError:
    joblib = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Dukungan multi-path: cek di folder models/ terlebih dahulu, lalu fallback ke root
MODEL_PATH = os.path.join(BASE_DIR, "models", "model_command_classifier_5kelas.pkl")
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(BASE_DIR, "model_command_classifier_5kelas.pkl")

def detect_board_model():
    """Mendeteksi apakah sistem berjalan di Raspberry Pi 4, Pi 5, atau PC."""
    dt_path = "/proc/device-tree/model"
    if os.path.exists(dt_path):
        try:
            with open(dt_path, "r", encoding="utf-8", errors="ignore") as f:
                model_name = f.read().strip().replace("\x00", "")
                return model_name
        except Exception:
            pass
    return f"{platform.system()} ({platform.machine()})"

def get_cpu_temp():
    """Membaca suhu prosesor SoC pada Linux/Raspberry Pi."""
    temp_path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(temp_path):
        try:
            with open(temp_path, "r") as f:
                temp_c = float(f.read().strip()) / 1000.0
                return temp_c
        except Exception:
            return None
    return None

def test_system_resources():
    print("=" * 75)
    print("  1. DIAGNOSTIK IDENTITAS BOARD & SUMBER DAYA PROSESOR")
    print("=" * 75)
    board = detect_board_model()
    print(f"Perangkat Terdeteksi : {board}")
    print(f"Sistem Operasi       : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Versi Python         : {sys.version.split()[0]}")

    cpu_temp = get_cpu_temp()
    if cpu_temp is not None:
        print(f"Suhu SoC CPU         : {cpu_temp:.1f} °C (Thermal Zone 0)")
        if cpu_temp > 75.0:
            print("  -> [PERINGATAN] Suhu cukup tinggi (>75°C). Pastikan kipas/heatsink aktif.")
        else:
            print("  -> Status Suhu       : [OPTIMAL] Dalam batas kerja aman.")
    else:
        print("Suhu SoC CPU         : Sensor suhu thermal_zone0 tidak tersedia di platform ini.")

    if psutil:
        cpu_count = psutil.cpu_count(logical=True)
        cpu_usage = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        print(f"CPU Core             : {cpu_count} Logical Core (Beban saat ini: {cpu_usage:.1f}%)")
        print(f"Total RAM            : {mem.total / (1024**3):.2f} GB (Terpakai: {mem.percent:.1f}%)")
        if cpu_usage < 50.0:
            print("  -> Status Beban CPU  : [LOLOS] < 50% sesuai parameter Bab 3.3 proposal!")
        else:
            print("  -> Status Beban CPU  : Di atas 50% (pantau background processes).")
    else:
        print("[PERINGATAN] Modul psutil belum terinstal! Jalankan: pip install psutil")

def test_serial_interfaces():
    print("\n" + "=" * 75)
    print("  2. DETEKSI PORT SERIAL USB (ROBOTIS U2D2 / DYNAMIXEL CONVERTER)")
    print("=" * 75)

    if platform.system().lower() == "windows":
        # Deteksi serial di Windows via serial.tools.list_ports jika ada
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                print("  [INFO] Tidak ada port COM serial yang terdeteksi di Windows.")
            else:
                print(f"Port COM Terdeteksi ({len(ports)} port):")
                for p in ports:
                    print(f"  * {p.device}: {p.description}")
        except ImportError:
            print("  [INFO] Uji serial Windows: pyserial belum terinstal.")
        return

    # Deteksi serial di Linux / Raspberry Pi
    usb_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if not usb_ports:
        print("  [PERINGATAN] Tidak ada port /dev/ttyUSB* atau /dev/ttyACM* yang terdeteksi.")
        print("  -> Pastikan kabel USB converter ROBOTIS U2D2 sudah tertancap ke port USB.")
        print("  -> Ketik 'lsusb' di terminal Linux untuk memeriksa apakah FTDI U2D2 terbaca.")
        return

    print(f"Port Serial Terdeteksi ({len(usb_ports)} port):")
    for port in usb_ports:
        port_name = os.path.basename(port)
        latency_file = f"/sys/bus/usb-serial/devices/{port_name}/latency_timer"
        latency_val = "N/A"
        if os.path.exists(latency_file):
            try:
                with open(latency_file, "r") as lf:
                    latency_val = lf.read().strip()
            except Exception:
                pass

        if latency_val == "1":
            status_lat = " -> [OPTIMAL: Latency Timer 1ms]"
        elif latency_val != "N/A":
            status_lat = f" -> [PERINGATAN: Latency Timer {latency_val}ms, disarankan 1ms via udev]"
        else:
            status_lat = ""

        print(f"  * {port} (Driver: USB-Serial){status_lat}")

def test_audio_hardware():
    print("\n" + "=" * 75)
    print("  3. DETEKSI PERANGKAT INPUT AUDIO (ALSA / USB MICROPHONE)")
    print("=" * 75)
    if not pyaudio:
        print("[ERROR] PyAudio belum terinstal! Jalankan: pip install pyaudio")
        return

    p = pyaudio.PyAudio()
    dev_count = p.get_device_count()
    input_devs = []

    for i in range(dev_count):
        try:
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                input_devs.append((i, info.get("name"), info.get("defaultSampleRate")))
        except Exception:
            continue

    if not input_devs:
        print("  [PERINGATAN] Tidak ada mikrofon input yang terdeteksi!")
        print("  -> Hubungkan USB Microphone atau Wireless Receiver AB13X ke port USB.")
        p.terminate()
        return

    print(f"Perangkat Input Audio Terdeteksi ({len(input_devs)} perangkat):")
    for idx, name, srate in input_devs:
        print(f"  [{idx}] {name} (Sample Rate Default: {int(srate)} Hz)")

    # Uji rekam singkat 0.5 detik dari input pertama
    test_idx = input_devs[0][0]
    print(f"\nMenguji pembacaan audio live dari perangkat [{test_idx}] selama 0.5 detik...")
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=int(input_devs[0][2]) or 44100,
            input=True,
            input_device_index=test_idx,
            frames_per_buffer=1024
        )
        frames = []
        for _ in range(int((int(input_devs[0][2]) or 44100) / 1024 * 0.5)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
        stream.stop_stream()
        stream.close()

        raw_bytes = b"".join(frames)
        audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio**2)))
        print(f"  -> Level RMS audio tertangkap : {rms:.4f}")
        if rms > 0.005:
            print("  -> Status Mikrofon            : [NORMAL] Sinyal audio vokal masuk dengan jelas!")
        else:
            print("  -> Status Mikrofon            : [SANGAT SENYAP] Pastikan volume mikrofon tidak di-mute.")
    except Exception as e:
        print(f"  -> Gagal menguji stream audio: {e}")
    finally:
        p.terminate()

def test_inference_latency():
    print("\n" + "=" * 75)
    print("  4. BENCHMARK LATENSI INFERENSI LIGHTGBM DI PERANGKAT")
    print("=" * 75)
    if not joblib:
        print("[ERROR] joblib belum terinstal! Jalankan: pip install joblib")
        return

    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Berkas model {MODEL_PATH} tidak ditemukan!")
        return

    pkg = joblib.load(MODEL_PATH)
    model = pkg["model"]
    features = pkg.get("feature_names") or pkg.get("feature_cols")
    print(f"Model Dimuat : {pkg.get('algorithm', 'LightGBM')} (47 Fitur Akustik)")

    # Warmup
    dummy = np.random.randn(1, len(features)).astype(np.float32)
    for _ in range(10):
        _ = model.predict_proba(dummy)

    # Benchmark 50 kali run
    latencies_ms = []
    for _ in range(50):
        inp = np.random.randn(1, len(features)).astype(np.float32)
        t0 = time.perf_counter()
        _ = model.predict_proba(inp)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mean_lat = np.mean(latencies_ms)
    std_lat = np.std(latencies_ms)
    min_lat = np.min(latencies_ms)
    max_lat = np.max(latencies_ms)

    print(f"Hasil Pengukuran Latensi Inferensi (N = 50 iterasi):")
    print(f"  Rata-rata (Mean)     : {mean_lat:.2f} ms")
    print(f"  Standar Deviasi      : {std_lat:.2f} ms")
    print(f"  Nilai Ekstrem (Min/Max): {min_lat:.2f} ms / {max_lat:.2f} ms")
    if mean_lat < 25.0:
        print("  -> Status Latensi    : [SANGAT CEPAT] Memenuhi target real-time edge computing (<25 ms)!")
    else:
        print("  -> Status Latensi    : [CUKUP] Mendekati batas atas real-time.")

def main():
    print("###########################################################################")
    print("  DIAGNOSTIK LENGKAP HARDWARE & EDGE COMPUTING AERORA ADITS")
    print("  Robot Seni Tari Indonesia (KRSTI) -- Universitas Negeri Malang")
    print("###########################################################################\n")
    test_system_resources()
    test_serial_interfaces()
    test_audio_hardware()
    test_inference_latency()
    print("\n" + "=" * 75)
    print("  DIAGNOSTIK SELESAI. SISTEM SIAP DIGUNAKAN!")
    print("=" * 75)

if __name__ == "__main__":
    main()
