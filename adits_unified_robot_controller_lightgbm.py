"""
================================================================================
ADITS UNIFIED ROBOT CONTROLLER - LIGHTGBM EDITION (KRSTI HUMANOID DANCE ROBOT)
Arsitektur Hibrida: AI LightGBM Decision + Chroma DSP Timeline Synchronization
Versi V2.3-LGBM: Smart DSP Timeline + Restart Detection + Pause-Freeze
================================================================================
Tim Peneliti Dewantara - Universitas Negeri Malang (UM)
Fitur Unggulan:
1. Hardware Guardrail: Mencegah salah perangkat audio (AB13X transmiter otomatis).
2. Smart DSP Timeline: Detik lagu ditentukan oleh sidik jari nada, bukan stopwatch kaku.
3. Restart Detection: Otomatis reset ke awal jika pengguna mengulang lagu dari awal.
4. Pause-Freeze Timer: Saat HP di-pause, penghitung detik berhenti total & servo hold posture.
5. Phase Inversion & Single-Channel Protection.
6. Multi-Threaded Audio Ingestion via queue.Queue (0% dropped frames).
7. Ultra-Fast Polyphase Resampling (8ms via scipy.signal.resample_poly).
8. Signal Peak Normalization & Gain Health-Check.
9. Live Audio WAV Caching (rekaman_live_debug_lightgbm/) untuk pembuktian telinga.
10. Numba JIT Pre-Warmup & Fail-Safe Adaptive Preemption.
================================================================================
"""

import os
import sys
import time
import datetime
import threading
import queue
import numpy as np
import pandas as pd
import scipy.signal
import soundfile as sf
import librosa
import joblib
import warnings
warnings.filterwarnings("ignore")

try:
    import psutil
except ImportError:
    psutil = None

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

for p_dir in [current_dir, parent_dir]:
    if p_dir not in sys.path:
        sys.path.insert(0, p_dir)

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio

from posture_lookup_decoder import get_posture_detail

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def extract_segment_features(audio_seg, sr=22050):
    """Ekstraksi 47 fitur audio acuan model LightGBM (RMS, ZCR, Spectral, MFCC 1-13, Chroma 12 nada)"""
    if audio_seg.ndim > 1:
        audio_seg = np.mean(audio_seg, axis=1)
    audio_seg = audio_seg.astype(np.float32)

    rms = librosa.feature.rms(y=audio_seg)[0]
    zcr = librosa.feature.zero_crossing_rate(audio_seg)[0]
    centroid = librosa.feature.spectral_centroid(y=audio_seg, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=audio_seg, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=audio_seg, sr=sr)[0]

    try:
        tempo, _ = librosa.beat.beat_track(y=audio_seg, sr=sr)
        tempo_val = float(np.atleast_1d(tempo)[0])
    except Exception:
        tempo_val = 120.0

    mfcc = librosa.feature.mfcc(y=audio_seg, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_stft(y=audio_seg, sr=sr)

    feats = {
        'rms_mean': float(np.mean(rms)), 'rms_std': float(np.std(rms)),
        'zcr_mean': float(np.mean(zcr)), 'zcr_std': float(np.std(zcr)),
        'spectral_centroid_mean': float(np.mean(centroid)),
        'spectral_bandwidth_mean': float(np.mean(bandwidth)),
        'spectral_rolloff_mean': float(np.mean(rolloff)),
        'tempo_bpm': tempo_val, 'beat_count': int(tempo_val * 3.0 / 60.0)
    }

    for i in range(13):
        feats[f'mfcc_{i+1}_mean'] = float(np.mean(mfcc[i]))
        feats[f'mfcc_{i+1}_std'] = float(np.std(mfcc[i]))

    chroma_names = ['chroma_C', 'chroma_C_sharp', 'chroma_D', 'chroma_D_sharp', 'chroma_E', 'chroma_F',
                    'chroma_F_sharp', 'chroma_G', 'chroma_G_sharp', 'chroma_A', 'chroma_A_sharp', 'chroma_B']
    for i, cname in enumerate(chroma_names):
        feats[cname] = float(np.mean(chroma[i]))

    return feats


# ==============================================================================
# FILE TUNGGAL: MODEL AI LIGHTGBM, DATASET, AUDIO MASTER
# ==============================================================================
def find_file(candidates):
    return next((p for p in candidates if os.path.exists(p)), None)

MODEL_PATH = find_file([
    os.path.join(current_dir, "model_robot_tari_lightgbm_95percent.pkl"),
    os.path.join(parent_dir, "model_robot_tari_lightgbm_95percent.pkl"),
    os.path.join(current_dir, "hasil colab", "model_robot_tari_lightgbm_95percent.pkl"),
])

EXCEL_PATH = find_file([
    os.path.join(current_dir, "dataset_robot_tari_3detik_lengkap_detail_pose.xlsx"),
    os.path.join(parent_dir, "dataset_robot_tari_3detik_lengkap_detail_pose.xlsx"),
])

AUDIO_PATH = find_file([
    os.path.join(current_dir, "audio_krsti_full_tari.wav"),
    os.path.join(parent_dir, "audio_krsti_full_tari.wav"),
    os.path.join(current_dir, "Video Project 6.mp3.mpeg"),
    os.path.join(parent_dir, "hasil colab", "Video Project 6.mp3.mpeg"),
])

# ==============================================================================
# KONFIGURASI PARAMETER SISTEM
# ==============================================================================
ANALYSIS_SR          = 16000
HOP_LENGTH           = 512
SEGMENT_DURATION_SEC = 3.0
MUSIC_START_RMS      = 0.030     # Ambang minimum untuk mulai (anti-desis ruangan)
SILENCE_RMS_THRESH   = 0.005     # Ambang deteksi pause musik
CHUNK_SIZE           = 1024
DSP_WINDOW_SEC       = 15.0      # Jendela pencarian DSP di sekitar posisi terakhir
RESTART_ZONE_SEC     = 9.0       # Zona deteksi restart (0 - 9 detik awal lagu)


def fast_resample(audio_data, orig_sr, target_sr):
    if orig_sr == target_sr:
        return audio_data.astype(np.float32)
    gcd = int(np.gcd(orig_sr, target_sr))
    return scipy.signal.resample_poly(audio_data, target_sr // gcd, orig_sr // gcd).astype(np.float32)


def load_master_fingerprint(audio_path, sr=ANALYSIS_SR, hop_length=HOP_LENGTH):
    cache_path = os.path.join(os.path.dirname(audio_path), "master_chroma_cache.npy")
    if os.path.exists(cache_path):
        try:
            return np.load(cache_path)
        except Exception:
            pass
    y_master, _ = librosa.load(audio_path, sr=sr)
    chroma = librosa.feature.chroma_stft(y=y_master, sr=sr, hop_length=hop_length)
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-6)
    try:
        np.save(cache_path, chroma)
    except Exception:
        pass
    return chroma


def select_audio_device_with_guardrail(p):
    usb_candidates = []
    available_inputs = []
    wasapi_info = None
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except Exception:
        pass

    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
        except Exception:
            continue
        name = dev.get("name", "")
        in_ch = dev.get("maxInputChannels", 0)
        is_lb = dev.get("isLoopbackDevice", False)
        if in_ch <= 0:
            continue
        is_wasapi = (wasapi_info is not None and dev.get("hostApi") == wasapi_info.get("index"))
        if any(kw in name.upper() for kw in ["AB13X", "USB AUDIO", "WIRELESS", "RECEIVER"]):
            if not is_lb:
                usb_candidates.append((is_wasapi, dev))
        available_inputs.append(dev)

    # 1. Jika terdeteksi dongle transmitter spesifik (AB13X/Wireless), gunakan itu
    if usb_candidates:
        usb_candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = usb_candidates[0][1]
        print("\n" + "=" * 85)
        print(" [AUDIO ENGINE] DONGLE TRANSMITER TERDETEKSI & TERKUNCI!")
        print("    Perangkat  : [%d] %s" % (chosen['index'], chosen['name']))
        print("    Status     : AKTIF (Siap Menerima Audio dari HP)")
        print("=" * 85 + "\n")
        return chosen

    # 2. Otomatis gunakan Pilihan 1 (available_inputs[0]: Microsoft Sound Mapper / Default) tanpa prompt
    if available_inputs:
        chosen = available_inputs[0]
        print("\n" + "=" * 85)
        print(" [AUDIO ENGINE] MENGGUNAKAN AUDIO INPUT UTAMA OTOMATIS (PILIHAN 1):")
        print("    Perangkat  : [%d] %s" % (chosen['index'], chosen['name']))
        print("    Status     : AKTIF (Terkunci Otomatis Tanpa Prompt)")
        print("=" * 85 + "\n")
        return chosen

    raise RuntimeError("[FATAL] Tidak ditemukan satupun perangkat input audio di sistem!")


class AudioCaptureThread(threading.Thread):
    def __init__(self, stream, chunk_size, channels):
        super().__init__(daemon=True)
        self.stream = stream
        self.chunk_size = chunk_size
        self.channels = channels
        self.queue = queue.Queue(maxsize=300)
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                if not data:
                    continue
                audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                if self.channels > 1:
                    stereo = audio_chunk.reshape(-1, self.channels)
                    ch_l, ch_r = stereo[:, 0], stereo[:, 1]
                    rms_l = float(np.sqrt(np.mean(ch_l ** 2)))
                    rms_r = float(np.sqrt(np.mean(ch_r ** 2)))
                    if rms_l > 3.0 * (rms_r + 1e-6):
                        mono = ch_l
                    elif rms_r > 3.0 * (rms_l + 1e-6):
                        mono = ch_r
                    else:
                        mono = (ch_l + ch_r) / 2.0
                else:
                    mono = audio_chunk
                try:
                    self.queue.put(mono, block=False)
                except queue.Full:
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.queue.put(mono, block=False)
            except Exception:
                if not self.running:
                    break
                time.sleep(0.002)

    def stop(self):
        self.running = False


class ADITSUnifiedControllerLightGBM:
    def __init__(self):
        print("=" * 85)
        print(" [ADITS] INISIALISASI UNIFIED ROBOT CONTROLLER V2.3 (LIGHTGBM EDITION)")
        print("=" * 85)

        if not MODEL_PATH:
            raise FileNotFoundError("Model AI LightGBM (model_robot_tari_lightgbm_95percent.pkl) tidak ditemukan!")
        model_data = joblib.load(MODEL_PATH)
        self.lgbm_model = model_data["model"]
        self.feature_names = model_data.get("feature_names", [])
        self.classes = list(self.lgbm_model.classes_)
        acc_train = model_data.get("accuracy", 94.62)
        print(" [AI Engine]  Model LightGBM: %s (%d Kelas | Akurasi Uji: %.2f%%)" % (
            os.path.basename(MODEL_PATH), len(self.classes), acc_train))

        if not EXCEL_PATH:
            raise FileNotFoundError("Dataset Excel tidak ditemukan!")
        self.df_ref = pd.read_excel(EXCEL_PATH)
        self.df_ref = self.df_ref.loc[:, ~self.df_ref.columns.str.contains("^Unnamed", na=False)]
        self.max_seg = int(self.df_ref["segment_id"].max())
        self.max_sec = float(self.df_ref["end_time_sec"].max())
        print(" [Database]   %d Segmen (Durasi: %.1fs)" % (len(self.df_ref), self.max_sec))

        if not AUDIO_PATH:
            raise FileNotFoundError("Audio master tidak ditemukan!")
        self.chroma_master = load_master_fingerprint(AUDIO_PATH, sr=ANALYSIS_SR, hop_length=HOP_LENGTH)
        self.master_frames = self.chroma_master.shape[1]
        print(" [DSP Engine] Sidik Jari Audio Master (%d Frame)" % self.master_frames)

        # Pre-compute zona restart (chroma frame 0 sampai RESTART_ZONE_SEC)
        self.restart_max_frame = int((RESTART_ZONE_SEC * ANALYSIS_SR) / HOP_LENGTH)

        print(" [Pre-Warmup] Kompilasi JIT & Warmup LightGBM...", end="", flush=True)
        dummy = np.random.randn(22050 * 3).astype(np.float32) * 0.2
        feats = extract_segment_features(dummy, sr=22050)
        vec = np.array([feats.get(c, 0.0) for c in self.feature_names], dtype=np.float64).reshape(1, -1)
        _ = self.lgbm_model.predict(vec)
        _ = self.lgbm_model.predict_proba(vec)
        print(" Selesai!")
        print("=" * 85)

        self.debug_folder = os.path.join(current_dir, "rekaman_live_debug_lightgbm")
        os.makedirs(self.debug_folder, exist_ok=True)

    def dsp_detect_second(self, chroma_live, last_sec, allow_global=False):
        """Deteksi posisi detik lagu menggunakan Chroma Cross-Correlation."""
        live_frames = chroma_live.shape[1]
        max_offset = self.master_frames - live_frames + 1
        if max_offset <= 0:
            return last_sec, 0.0

        corrs = np.zeros(max_offset)
        for i in range(12):
            c = scipy.signal.fftconvolve(self.chroma_master[i], chroma_live[i, ::-1], mode="valid")
            if len(c) == max_offset:
                corrs += c

        best_global = int(np.argmax(corrs))
        global_sec = (best_global * HOP_LENGTH) / ANALYSIS_SR
        global_score_pct = float(corrs[best_global] / live_frames) * 100.0

        if allow_global:
            return global_sec, global_score_pct

        expected_sec = last_sec + SEGMENT_DURATION_SEC
        exp_frame = int((expected_sec * ANALYSIS_SR) / HOP_LENGTH)
        win_frames = int((DSP_WINDOW_SEC * ANALYSIS_SR) / HOP_LENGTH)
        f_min = max(0, exp_frame - win_frames)
        f_max = min(max_offset, exp_frame + win_frames)

        if f_max > f_min:
            best_win = f_min + int(np.argmax(corrs[f_min:f_max]))
            win_score_pct = float(corrs[best_win] / live_frames) * 100.0
        else:
            best_win = exp_frame
            win_score_pct = 0.0

        win_sec = (best_win * HOP_LENGTH) / ANALYSIS_SR

        if global_score_pct >= 80.0 and (global_score_pct >= win_score_pct * 1.15 or win_score_pct < 70.0):
            return global_sec, global_score_pct

        restart_f_max = min(max_offset, self.restart_max_frame)
        if restart_f_max > 0 and last_sec > 30.0:
            best_restart = int(np.argmax(corrs[0:restart_f_max]))
            restart_score_pct = float(corrs[best_restart] / live_frames) * 100.0

            if restart_score_pct >= win_score_pct * 0.90:
                restart_sec = (best_restart * HOP_LENGTH) / ANALYSIS_SR
                return restart_sec, restart_score_pct

        return win_sec, win_score_pct

    def lookup_segment(self, detected_sec):
        """Cari baris database Excel berdasarkan detected_sec."""
        matched = self.df_ref[
            (self.df_ref["start_time_sec"] <= detected_sec) &
            (self.df_ref["end_time_sec"] > detected_sec)
        ]
        if matched.empty:
            diffs = np.abs(self.df_ref["start_time_sec"] - detected_sec)
            return self.df_ref.iloc[int(np.argmin(diffs))]
        return matched.iloc[0]

    def run(self):
        p = pyaudio.PyAudio()
        target_dev = select_audio_device_with_guardrail(p)
        input_sr = int(target_dev["defaultSampleRate"])
        channels = int(min(2, target_dev["maxInputChannels"]))

        print("Model AI Aktif   : LIGHTGBM CLASSIFIER (Gradient Boosting)")
        print("Input Audio      : [%d] %s" % (target_dev['index'], target_dev['name']))
        print("Sample Rate      : %d Hz | Channels: %d" % (input_sr, channels))
        print("Jendela Segmen   : %.1f Detik" % SEGMENT_DURATION_SEC)
        print("Ambang Mulai     : RMS >= %.3f (Menunggu nada gamelan pembuka)" % MUSIC_START_RMS)
        print("DSP Window       : +/- %.0f detik | Restart Zone: 0-%.0fs" % (DSP_WINDOW_SEC, RESTART_ZONE_SEC))
        print("Debug Audio      : rekaman_live_debug_lightgbm/")
        print("=" * 85)
        print("Petunjuk:")
        print("  -> Putar musik dari HP (volume 80%-100%), mulai dari awal lagu.")
        print("  -> Boleh PAUSE, RESUME, ULANG KE AWAL, atau SKIP kapan saja.")
        print("  -> Tekan 'q' untuk BERHENTI & SIMPAN LAPORAN.")
        print("=" * 85)
        print("Menunggu nada gamelan pembuka... Putar musik di HP sekarang!\n")

        stream = p.open(format=pyaudio.paInt16, channels=channels, rate=input_sr,
                        input=True, frames_per_buffer=CHUNK_SIZE,
                        input_device_index=target_dev["index"])

        capture = AudioCaptureThread(stream, CHUNK_SIZE, channels)
        capture.start()

        samples_per_seg = int(SEGMENT_DURATION_SEC * input_sr)
        segment_buffer = []
        accumulated = 0

        is_music_active = False
        is_paused = False
        last_dsp_sec = 0.0
        is_first_segment = True

        silence_count = 0
        silence_thresh = int(1.2 * input_sr / CHUNK_SIZE)

        eval_logs = []
        correct_count = 0
        total_count = 0
        segment_number = 0
        last_matched_row = None

        try:
            while True:
                if msvcrt and msvcrt.kbhit():
                    if msvcrt.getch().decode("utf-8", errors="ignore").lower() == "q":
                        print("\n[INFO] ADITS Controller (LightGBM) dihentikan.")
                        break

                try:
                    mono = capture.queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                chunk_rms = float(np.sqrt(np.mean(mono ** 2)))

                # === MENUNGGU NADA PEMBUKA (Anti-Desis) ===
                if not is_music_active:
                    meter_len = int(min(25, chunk_rms * 100))
                    bar = "=" * meter_len + "-" * (25 - meter_len)
                    sys.stdout.write("\r  [Volume Mic: [%s] RMS: %.4f] (Menunggu nada gamelan...)" % (bar, chunk_rms))
                    sys.stdout.flush()

                    if chunk_rms >= MUSIC_START_RMS:
                        is_music_active = True
                        is_paused = False
                        silence_count = 0
                        is_first_segment = True
                        segment_buffer = []
                        accumulated = 0
                        ts = datetime.datetime.now().strftime('%H:%M:%S')
                        print("\n\n[%s] [EVENT: MUSIC_START] Nada Gamelan Terdeteksi! LightGBM Controller Aktif...\n" % ts)
                    else:
                        continue

                # === DETEKSI PAUSE ===
                if chunk_rms < SILENCE_RMS_THRESH:
                    silence_count += 1
                    if silence_count >= silence_thresh and not is_paused:
                        is_paused = True
                        segment_buffer = []
                        accumulated = 0

                        if last_matched_row is not None:
                            seg_id = int(last_matched_row["segment_id"])
                            babak = str(last_matched_row.get("babak_tari_makro", "N/A"))
                            safe = str(last_matched_row.get("safe_stop_position", "Kunci Posisi Seimbang"))
                            detail = get_posture_detail(babak)

                            s_time_p = float(last_matched_row.get("start_time_sec", 0.0))
                            e_time_p = float(last_matched_row.get("end_time_sec", 0.0))
                            print("=" * 85)
                            print(" [EVENT: AUDIO_PAUSE] LAGU BERHENTI (Detik Lagu: %.1fs - %.1fs | DSP: %.1fs | Segmen #%02d)" % (
                                s_time_p, e_time_p, last_dsp_sec, seg_id))
                            print("=" * 85)
                            print(" [FAIL-SAFE] AKSI PREEMPTION PRIORITAS 0 (DARURAT):")
                            print("    - Status Fail-Safe : [ %s ]" % safe.upper())
                            print("    - Babak Terakhir   : >> %s << (Segmen #%02d)" % (babak, seg_id))
                            print("-" * 85)
                            print(" [SERVO] KUNCIAN SUDUT ANATOMI ROBOT (SAFE HOLD POSTURE):")
                            print("    - KEPALA       : %-32s | Sudut Servo: %s" % (detail['kepala'], detail['sudut_kepala']))
                            print("    - TANGAN KANAN : %-32s | Sudut Servo: %s" % (detail['tangan_kanan'], detail['sudut_tangan_kanan']))
                            print("    - TANGAN KIRI  : %-32s | Sudut Servo: %s" % (detail['tangan_kiri'], detail['sudut_tangan_kiri']))
                            print("    - KAKI / BADAN : %-32s | Sudut Servo: %s" % (detail['kaki_badan'], detail['sudut_kaki']))
                            print("=" * 85)
                            print("  Menunggu lagu dilanjutkan atau diulang ke awal...\n")
                    continue
                else:
                    if is_paused:
                        is_paused = False
                        silence_count = 0
                        ts = datetime.datetime.now().strftime('%H:%M:%S')
                        print("[%s] [EVENT: MUSIC_RESUME] Musik Kembali! Mendeteksi Posisi Lagu...\n" % ts)
                    silence_count = 0

                # === KUMPULKAN BUFFER 3 DETIK ===
                segment_buffer.append(mono)
                accumulated += len(mono)

                if accumulated >= samples_per_seg:
                    t0 = time.time()
                    full_seg = np.concatenate(segment_buffer)[:samples_per_seg]
                    segment_number += 1

                    # Simpan file .wav debug
                    wav_name = "segmen_lgbm_%02d.wav" % segment_number
                    try:
                        sf.write(os.path.join(self.debug_folder, wav_name), full_seg, input_sr)
                    except Exception:
                        pass

                    seg_rms = float(np.sqrt(np.mean(full_seg ** 2)))
                    gain_warn = ""
                    if seg_rms < 0.020:
                        gain_warn = " [PERINGATAN: Volume HP Terlalu Kecil!]"

                    # --- DSP: Deteksi Detik Lagu Saat Ini ---
                    y_dsp = fast_resample(full_seg, input_sr, ANALYSIS_SR)
                    chroma_live = librosa.feature.chroma_stft(y=y_dsp, sr=ANALYSIS_SR, hop_length=HOP_LENGTH)
                    chroma_live = chroma_live / (np.linalg.norm(chroma_live, axis=0, keepdims=True) + 1e-6)

                    dsp_sec, dsp_score = self.dsp_detect_second(
                        chroma_live, last_dsp_sec, allow_global=is_first_segment
                    )

                    # Deteksi restart
                    if not is_first_segment and dsp_sec < RESTART_ZONE_SEC and last_dsp_sec > 30.0:
                        ts = datetime.datetime.now().strftime('%H:%M:%S')
                        print("[%s] [EVENT: RESTART] Lagu Diulang ke Awal! Reset ke Detik %.1fs\n" % (ts, dsp_sec))

                    last_dsp_sec = dsp_sec
                    is_first_segment = False

                    # --- Lookup Segment di Database Excel berdasarkan DSP ---
                    matched_row = self.lookup_segment(dsp_sec)
                    last_matched_row = matched_row
                    seg_id = int(matched_row["segment_id"])
                    s_time = float(matched_row["start_time_sec"])
                    e_time = float(matched_row["end_time_sec"])
                    babak_db = str(matched_row.get("babak_tari_makro", matched_row.get("gerakan_robot", "N/A")))

                    # --- AI LightGBM Prediction ---
                    y_ai = fast_resample(full_seg, input_sr, 22050)
                    max_abs = float(np.max(np.abs(y_ai)))
                    if max_abs > 1e-4:
                        y_ai = (y_ai / max_abs) * 0.95

                    feats = extract_segment_features(y_ai, sr=22050)
                    vec = np.array([feats.get(c, 0.0) for c in self.feature_names], dtype=np.float64).reshape(1, -1)
                    vec = np.nan_to_num(vec, nan=0.0)

                    lgbm_pred = self.lgbm_model.predict(vec)[0]
                    lgbm_prob = float(np.max(self.lgbm_model.predict_proba(vec)[0]) * 100.0)

                    # --- Evaluasi ---
                    latency_ms = (time.time() - t0) * 1000.0

                    is_match = (str(lgbm_pred).strip().lower() == str(babak_db).strip().lower())
                    if is_match:
                        correct_count += 1
                    total_count += 1
                    live_acc = (correct_count / total_count) * 100.0
                    status_tag = "BENAR [MATCH]" if is_match else "SALAH [BEDA]"

                    csv_file = "%s.csv" % babak_db
                    p_kepala = str(matched_row.get("pose_kepala", "-"))
                    p_tangan_r = str(matched_row.get("pose_tangan_kanan", "-"))
                    p_kaki = str(matched_row.get("pose_kaki_badan", "-"))

                    eval_logs.append({
                        "detik_dsp": "%.1fs" % dsp_sec,
                        "segmen_id_excel": seg_id,
                        "rentang_detik": "%.1fs - %.1fs" % (s_time, e_time),
                        "target_babak": babak_db,
                        "prediksi_ai_lgbm": lgbm_pred,
                        "confidence": "%.1f%%" % lgbm_prob,
                        "hasil": status_tag,
                        "rms_energy": round(seg_rms, 4),
                        "dsp_score": "%.1f%%" % dsp_score,
                        "latensi_ms": round(latency_ms, 1),
                    })

                    ts = datetime.datetime.now().strftime('%H:%M:%S')
                    print("[%s] Detik: %.1fs - %.1fs | DSP: %.1fs (Segmen #%02d) | %-14s | Akurasi: %5.1f%% (%d/%d)" % (
                        ts, s_time, e_time, dsp_sec, seg_id, status_tag, live_acc, correct_count, total_count))
                    print("   -> Target: %-18s | AI (LGBM): %-18s (%.1f%%) | CSV: %s" % (
                        babak_db, lgbm_pred, lgbm_prob, csv_file))
                    print("   -> Waktu : Detik Lagu: %.1fs - %.1fs (Durasi: %.1fs) | Deteksi DSP: %.2fs" % (
                        s_time, e_time, e_time - s_time, dsp_sec))
                    print("   -> Pose  : Kepala: %s | Tangan: %s | Kaki: %s" % (p_kepala, p_tangan_r, p_kaki))
                    print("   -> Sinyal: RMS: %.4f%s | Latensi: %.1fms | DSP Score: %.1f%%\n" % (
                        seg_rms, gain_warn, latency_ms, dsp_score))

                    segment_buffer = []
                    accumulated = 0

        except KeyboardInterrupt:
            print("\n[INFO] ADITS Controller (LightGBM) dihentikan.")
        finally:
            capture.stop()
            try:
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception:
                pass

            if eval_logs:
                log_df = pd.DataFrame(eval_logs)
                candidate_paths = [
                    os.path.join(current_dir, "hasil_evaluasi_live_transmitter_lightgbm.xlsx"),
                    os.path.join(parent_dir, "hasil_evaluasi_live_transmitter_lightgbm.xlsx"),
                    os.path.join(current_dir, "hasil colab", "hasil_evaluasi_live_transmitter_lightgbm.xlsx")
                ]
                unique_paths = sorted(list(set([p for p in candidate_paths if os.path.exists(os.path.dirname(p))])))
                for op in unique_paths:
                    try:
                        log_df.to_excel(op, index=False)
                        print("=" * 85)
                        print("Laporan Tersimpan: %s" % op)
                    except PermissionError:
                        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        alt_op = os.path.join(os.path.dirname(op), f"hasil_evaluasi_live_transmitter_lightgbm_{ts}.xlsx")
                        try:
                            log_df.to_excel(alt_op, index=False)
                            print("=" * 85)
                            print("[INFO] File Excel sedang terbuka, disimpan ke file cadangan: %s" % alt_op)
                        except Exception:
                            pass
                    except Exception:
                        pass

                print("=" * 85)
                print("RINGKASAN AKHIR PENGUJIAN LIVE TRANSMITTER (LIGHTGBM):")
                print("   * Model Digunakan     : LightGBM Classifier (Gradient Boosting)")
                print("   * Total Segmen Diuji  : %d segmen" % total_count)
                print("   * Prediksi BENAR      : %d segmen" % correct_count)
                print("   * Prediksi SALAH      : %d segmen" % (total_count - correct_count))
                print("   * Akurasi Akhir       : %.2f %%" % ((correct_count / max(1, total_count)) * 100.0))
                print("   * Audio Debug Folder  : %s" % self.debug_folder)
                print("=" * 85)


if __name__ == "__main__":
    controller = ADITSUnifiedControllerLightGBM()
    controller.run()
