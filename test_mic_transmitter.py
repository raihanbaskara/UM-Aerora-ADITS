"""
================================================================================
DIAGNOSTIK INPUT AUDIO TRANSMITTER (CEK SEBELUM REKAM)
================================================================================
Jalankan script ini sebelum merekam full lagu untuk memastikan:
1. Dongle AB13X terdeteksi.
2. Suara gamelan dari HP benar-benar MASUK ke PC (bukan cuma desis hening).
3. Level volume (RMS) berada pada batas aman (RMS >= 0.08).
================================================================================
"""

import time
import sys
import numpy as np

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio

def get_recording_device(p):
    # Cari AB13X
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            name = info.get("name", "").lower()
            if "ab13x" in name:
                return info
    # Fallback ke default
    try:
        return p.get_default_input_device_info()
    except Exception:
        return None

def main():
    p = pyaudio.PyAudio()
    dev = get_recording_device(p)
    if not dev:
        print("[ERROR] Perangkat audio input tidak ditemukan!")
        p.terminate()
        return

    sr = int(dev["defaultSampleRate"])
    channels = int(min(2, dev["maxInputChannels"]))
    chunk_size = 1024

    print("=" * 68)
    print("  AUDIO TRANSMITTER LIVE MONITOR (CEK LEVEL SINYAL)")
    print("=" * 68)
    print(f"Perangkat Input : [{dev['index']}] {dev['name']}")
    print(f"Sample Rate     : {sr} Hz | Channels: {channels}")
    print("=" * 68)
    print("PUTAR MUSIK GAMELAN DI HP SEKARANG!")
    print("Perhatikan bar meter dan nilai RMS di bawah:\n")

    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sr,
        input=True,
        frames_per_buffer=chunk_size,
        input_device_index=dev["index"]
    )

    try:
        print(f"{'WAKTU':<10} | {'RMS':<8} | {'PEAK':<8} | {'LEVEL METER':<20} | STATUS")
        print("-" * 68)
        for _ in range(25):  # Pantau selama ~12-13 detik
            frames = []
            for _ in range(int(sr / chunk_size * 0.5)): # 0.5 detik
                data = stream.read(chunk_size, exception_on_overflow=False)
                frames.append(np.frombuffer(data, dtype=np.int16))
            
            audio = np.concatenate(frames).astype(np.float32) / 32768.0
            if channels > 1:
                audio = audio.reshape(-1, channels)
                audio = np.mean(audio, axis=1)

            rms = float(np.sqrt(np.mean(audio ** 2)))
            peak = float(np.max(np.abs(audio)))

            bar_len = int(min(20, rms * 80))
            bar = "#" * bar_len + "-" * (20 - bar_len)

            if rms < 0.025:
                status = "[BAHAYA] SENYAP / DESIS! Cek Bluetooth HP!"
            elif rms < 0.08:
                status = "[LEMAH] Terlalu Pelan (Naikkan Volume HP)"
            elif rms < 0.16:
                status = "[BAGUS] Sinyal Masuk Jelas (Vol 60%-80%)"
            else:
                status = "[KENCANG] Sinyal Sangat Kuat (Vol 80%-100%)"

            timestamp = time.strftime("%H:%M:%S")
            print(f"{timestamp:<10} | {rms:<8.4f} | {peak:<8.4f} | [{bar}] | {status}")

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    print("\n" + "=" * 68)
    print("Pemeriksaan selesai. Jika status [BAGUS] atau [KENCANG], siap rekam!")
    print("=" * 68)

if __name__ == "__main__":
    main()
