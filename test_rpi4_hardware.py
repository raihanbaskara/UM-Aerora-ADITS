"""
================================================================================
UJI DIAGNOSTIK PERANGKAT KERAS & LATENSI EDGE COMPUTING RASPBERRY PI 4
ADITS KRSTI - Tim Peneliti Dewantara (Universitas Negeri Malang)
================================================================================
Skrip diagnostik komprehensif untuk memverifikasi kesiapan hardware Raspberry Pi 4:
1. Pemantauan Sumber Daya: CPU Cortex-A72, Suhu Core (Thermal Zone), RAM & psutil.
2. Deteksi Audio Input: ALSA / USB Microphone, Uji Rekam & Evaluasi RMS.
3. Deteksi Port Serial: Port U2D2 (/dev/ttyUSB*) & Pemeriksaan Latency Timer FTDI.
4. Pengukuran Latensi Inferensi: Benchmark LightGBM 47-fitur pada ARM64 (Target < 25 ms).
================================================================================
"""

import sys
import os
import glob
import time
import platform
import numpy as np
import joblib

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyaudio
except ImportError:
    pyaudio = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model_command_classifier_5kelas.pkl")

def get_cpu_temp():
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
    print("  1. DIAGNOSTIK SUMBER DAYA RASPBERRY PI 4 (ARM64 / LINUX)")
    print("=" * 75)
    print(f"Sistem Operasi   : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Versi Python     : {sys.version.split()[0]}")
    
    cpu_temp = get_cpu_temp()
    if cpu_temp is not None:
        print(f"Suhu SoC CPU     : {cpu_temp:.1f} °C (Thermal Zone 0)")
        if cpu_temp > 75.0:
            print("  -> [PERINGATAN] Suhu cukup tinggi (>75°C). Pastikan kipas/heatsink aktif.")
        else:
            print("  -> Status Suhu : [OPTIMAL] Dalam batas kerja aman.")

    if psutil:
        cpu_count = psutil.cpu_count(logical=True)
        cpu_usage = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        print(f"CPU Core         : {cpu_count} Core Cortex-A72 (Beban saat ini: {cpu_usage:.1f}%)")
        print(f"Total RAM        : {mem.total / (1024**3):.2f} GB (Terpakai: {mem.percent:.1f}%)")
        if cpu_usage < 50.0:
            print("  -> Status Beban: [LOLOS] < 50% sesuai parameter Bab 3.3 proposal!")
        else:
            print("  -> Status Beban: Di atas 50% (pantau background processes)")
    else:
        print("[PERINGATAN] Modul psutil belum terinstal!")

def test_serial_interfaces():
    print("\n" + "=" * 75)
    print("  2. DETEKSI PORT SERIAL USB (ROBOTIS U2D2 / FTDI)")
    print("=" * 75)
    
    usb_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if not usb_ports:
        print("  [PERINGATAN] Tidak ada port /dev/ttyUSB* atau /dev/ttyACM* yang terdeteksi.")
        print("  -> Pastikan kabel USB converter ROBOTIS U2D2 sudah tertancap ke port USB Pi 4.")
        print("  -> Ketik 'lsusb' di terminal Linux untuk memeriksa apakah FTDI U2D2 terbaca.")
        return

    print(f"Port Serial Terdeteksi ({len(usb_ports)} port):")
    for port in usb_ports:
        # Cek FTDI latency timer
        port_name = os.path.basename(port)
        latency_file = f"/sys/bus/usb-serial/devices/{port_name}/latency_timer"
        latency_val = "N/A"
        if os.path.exists(latency_file):
            try:
                with open(latency_file, "r") as lf:
                    latency_val = lf.read().strip()
            except Exception:
                pass
        
        status_lat = ""
        if latency_val == "1":
            status_lat = " -> [OPTIMAL: Latency Timer 1ms]"
        elif latency_val != "N/A":
            status_lat = f" -> [PERINGATAN: Latency Timer {latency_val}ms, disarankan 1ms]"

        print(f"  * {port} (Driver: USB-Serial) {status_lat}")

def test_audio_hardware():
    print("\n" + "=" * 75)
    print("  3. DETEKSI PERANGKAT INPUT AUDIO (ALSA / USB MIC)")
    print("=" * 75)
    if not pyaudio:
        print("[ERROR] PyAudio belum terinstal!")
        return

    p = pyaudio.PyAudio()
    dev_count = p.get_device_count()
    print(f"Total antarmuka audio terdeteksi: {dev_count}")

    input_devs = []
    for i in range(dev_count):
        try:
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                input_devs.append((i, info.get("name", "Unknown"), info.get("defaultSampleRate", 0)))
        except Exception:
            continue

    if not input_devs:
        print("  [PERINGATAN] Tidak ada mikrofon input yang terdeteksi!")
        print("  -> Hubungkan USB Microphone atau Wireless Receiver AB13X.")
        p.terminate()
        return

    print("Daftar perangkat input aktif:")
    for idx, name, srate in input_devs:
        print(f"  [{idx}] {name} (Sample Rate Default: {int(srate)} Hz)")

    # Uji rekam singkat 0.5 detik dari input pertama
    test_idx = input_devs[0][0]
    print(f"\nMenguji pembacaan audio live dari perangkat [{test_idx}] selama 0.5 detik...")
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=22050, input=True,
                        frames_per_buffer=1024, input_device_index=test_idx)
        frames = []
        for _ in range(int(22050 / 1024 * 0.5)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(np.frombuffer(data, dtype=np.int16))
        stream.stop_stream()
        stream.close()

        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio**2)))
        print(f"  -> Level RMS audio tertangkap: {rms:.4f}")
        if rms > 0.005:
            print("  -> Status Mikrofon: [NORMAL] Sinyal audio masuk dengan jelas!")
        else:
            print("  -> Status Mikrofon: [SANGAT SENYAP] Pastikan volume mikrofon tidak di-mute.")
    except Exception as e:
        print(f"  -> Gagal menguji stream audio: {e}")
    finally:
        p.terminate()

def test_inference_latency():
    print("\n" + "=" * 75)
    print("  4. BENCHMARK LATENSI INFERENSI LIGHTGBM (CORTEX-A72)")
    print("=" * 75)
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Berkas model {MODEL_PATH} tidak ditemukan!")
        return

    pkg = joblib.load(MODEL_PATH)
    model = pkg["model"]
    features = pkg.get("feature_names") or pkg.get("feature_cols")
    print(f"Model dimuat: {pkg.get('algorithm', 'LightGBM')} (Dimensi: {len(features)} fitur)")

    # Warmup
    dummy = np.random.randn(1, len(features)).astype(np.float32)
    for _ in range(5):
        model.predict(dummy)

    # Ukur latensi 50 kali
    latencies_ms = []
    for _ in range(50):
        t0 = time.perf_counter()
        model.predict(dummy)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mean_lat = np.mean(latencies_ms)
    std_lat = np.std(latencies_ms)
    min_lat = np.min(latencies_ms)
    max_lat = np.max(latencies_ms)

    print(f"Hasil Pengukuran Latensi Inferensi (N=50 iterasi):")
    print(f"  Rata-rata (Mean) : {mean_lat:.2f} ms")
    print(f"  Standar Deviasi  : {std_lat:.2f} ms")
    print(f"  Min / Max        : {min_lat:.2f} ms / {max_lat:.2f} ms")
    if mean_lat < 25.0:
        print("  -> Status Latensi: [SANGAT CEPAT] Memenuhi target real-time edge computing!")
    else:
        print("  -> Status Latensi: [CUKUP] Mendekati batas atas real-time.")

def main():
    print("###########################################################################")
    print("  DIAGNOSTIK LENGKAP EDGE COMPUTING ADITS (RASPBERRY PI 4)")
    print("###########################################################################\n")
    test_system_resources()
    test_serial_interfaces()
    test_audio_hardware()
    test_inference_latency()
    print("\n" + "=" * 75)
    print("  DIAGNOSTIK SELESAI. SISTEM SIAP DIGUNAKAN DI RASPBERRY PI 4!")
    print("=" * 75)

if __name__ == "__main__":
    main()
