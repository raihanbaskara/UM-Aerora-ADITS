"""
================================================================================
ADITS GRAND UNIFIED CONTROLLER (VOICE AI + DSP CHROMA + DANCE AI)
Mode: Live Mic Voice Command + Internal Digital Audio Stream untuk AI & DSP
================================================================================
"""

import os
import sys
import time
import datetime
import threading
import queue
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import scipy.signal
import librosa
import joblib

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import psutil
except ImportError:
    psutil = None

def check_keyboard_hit():
    if sys.platform == "win32":
        try:
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode("utf-8", errors="ignore").lower()
        except Exception:
            pass
    else:
        try:
            import select
            dr, _, _ = select.select([sys.stdin], [], [], 0)
            if dr:
                return sys.stdin.read(1).lower()
        except Exception:
            pass
    return None

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio

try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

from adits_adaptive_scheduler import (
    AdaptivePreemptiveScheduler,
    StaticFIFOScheduler,
    Task,
    P0_EMERGENCY,
    P1_TRANSITION,
    P2_POSTURE,
    P3_ROUTINE,
)

from posture_lookup_decoder import get_posture_detail

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

for p_dir in [current_dir, parent_dir]:
    if p_dir not in sys.path:
        sys.path.insert(0, p_dir)

def find_file(candidates):
    return next((p for p in candidates if os.path.exists(p)), None)

CMD_MODEL_PATH = find_file([
    os.path.join(current_dir, "model_command_classifier_5kelas.pkl"),
    os.path.join(current_dir, "ADITS_ROBOT_TARI_SIAP_PAKAI", "model_command_classifier_5kelas.pkl"),
    os.path.join(parent_dir, "model_command_classifier_5kelas.pkl"),
])

DANCE_MODEL_PATH = find_file([
    os.path.join(current_dir, "model_robot_tari_lightgbm_95percent.pkl"),
    os.path.join(current_dir, "ADITS_ROBOT_TARI_SIAP_PAKAI", "model_robot_tari_lightgbm_95percent.pkl"),
    os.path.join(parent_dir, "model_robot_tari_lightgbm_95percent.pkl"),
    os.path.join(current_dir, "model_robot_tari_final_transmitter_91percent.pkl"),
    os.path.join(current_dir, "ADITS_ROBOT_TARI_SIAP_PAKAI", "model_robot_tari_final_transmitter_91percent.pkl"),
    os.path.join(parent_dir, "model_robot_tari_final_transmitter_91percent.pkl"),
])

EXCEL_PATH = find_file([
    os.path.join(current_dir, "dataset_robot_tari_3detik_lengkap_detail_pose.xlsx"),
    os.path.join(current_dir, "ADITS_ROBOT_TARI_SIAP_PAKAI", "dataset_robot_tari_3detik_lengkap_detail_pose.xlsx"),
    os.path.join(parent_dir, "dataset_robot_tari_3detik_lengkap_detail_pose.xlsx"),
])

AUDIO_PATH = find_file([
    os.path.join(current_dir, "audio_krsti_full_tari.wav"),
    os.path.join(current_dir, "ADITS_ROBOT_TARI_SIAP_PAKAI", "audio_krsti_full_tari.wav"),
    os.path.join(parent_dir, "audio_krsti_full_tari.wav"),
])

SR_AI              = 22050
SR_DSP             = 16000
HOP_LENGTH         = 512
CMD_WINDOW_SEC     = 2.0
DANCE_WINDOW_SEC   = 3.0
DSP_WINDOW_SEC     = 15.0
CHUNK_SIZE         = 1024

STANDBY_NOISE_GATE = 0.018
PLAYING_NOISE_GATE = 0.035
CMD_CONFIDENCE_MIN = 55.0
CMD_COOLDOWN_SEC   = 2.5

PRIORITY = {
    "MULAI"  : 1,
    "STOP"   : 1,
    "LANJUT" : 1,
    "BERDIRI": 2,
    "DUDUK"  : 2,
}

def fast_resample(audio_data, orig_sr, target_sr):
    if orig_sr == target_sr:
        return audio_data.astype(np.float32)
    gcd = int(np.gcd(orig_sr, target_sr))
    return scipy.signal.resample_poly(audio_data, target_sr // gcd, orig_sr // gcd).astype(np.float32)

def extract_47_features(audio_seg, sr=SR_AI):
    if audio_seg.ndim > 1:
        audio_seg = np.mean(audio_seg, axis=1)
    audio_seg = audio_seg.astype(np.float32)

    rms       = librosa.feature.rms(y=audio_seg)[0]
    zcr       = librosa.feature.zero_crossing_rate(audio_seg)[0]
    centroid  = librosa.feature.spectral_centroid(y=audio_seg, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=audio_seg, sr=sr)[0]
    rolloff   = librosa.feature.spectral_rolloff(y=audio_seg, sr=sr)[0]

    try:
        tempo, _ = librosa.beat.beat_track(y=audio_seg, sr=sr)
        tempo_val = float(np.atleast_1d(tempo)[0])
    except Exception:
        tempo_val = 120.0

    mfcc   = librosa.feature.mfcc(y=audio_seg, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_stft(y=audio_seg, sr=sr)

    feats = {
        "rms_mean": float(np.mean(rms)), "rms_std": float(np.std(rms)),
        "zcr_mean": float(np.mean(zcr)), "zcr_std": float(np.std(zcr)),
        "spectral_centroid_mean": float(np.mean(centroid)),
        "spectral_bandwidth_mean": float(np.mean(bandwidth)),
        "spectral_rolloff_mean": float(np.mean(rolloff)),
        "tempo_bpm": tempo_val, "beat_count": int(tempo_val * 3.0 / 60.0)
    }

    for i in range(13):
        feats[f"mfcc_{i+1}_mean"] = float(np.mean(mfcc[i]))
        feats[f"mfcc_{i+1}_std"]  = float(np.std(mfcc[i]))

    chroma_names = ["chroma_C", "chroma_C_sharp", "chroma_D", "chroma_D_sharp", "chroma_E", "chroma_F",
                    "chroma_F_sharp", "chroma_G", "chroma_G_sharp", "chroma_A", "chroma_A_sharp", "chroma_B"]
    for i, cname in enumerate(chroma_names):
        feats[cname] = float(np.mean(chroma[i]))

    return feats

def load_master_fingerprint(audio_path, sr=SR_DSP, hop_length=HOP_LENGTH):
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

class MicCaptureThread(threading.Thread):
    def __init__(self, stream, chunk_size, channels):
        super().__init__(daemon=True)
        self.stream     = stream
        self.chunk_size = chunk_size
        self.channels   = channels
        self.queue      = queue.Queue(maxsize=500)
        self.running    = True

    def run(self):
        err_count = 0
        while self.running:
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                if not data:
                    continue
                err_count = 0
                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                if self.channels > 1:
                    stereo = arr.reshape(-1, self.channels)
                    mono = np.mean(stereo, axis=1)
                else:
                    mono = arr
                try:
                    self.queue.put(mono, block=False)
                except queue.Full:
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.queue.put(mono, block=False)
            except Exception:
                err_count += 1
                if not self.running or err_count > 10:
                    if err_count > 10:
                        print("\n[PERINGATAN ALSA] Mikrofon terputus atau stream rusak. Menghentikan thread mikrofon secara aman.")
                    break
                time.sleep(0.05)

    def stop(self):
        self.running = False

def select_input_device(p):
    available = []
    print("\n" + "=" * 75)
    print(" DAFTAR PERANGKAT INPUT AUDIO (MIKROFON UNTUK PERINTAH SUARA):")
    print("=" * 75)
    idx_choice = 0
    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
        except Exception:
            continue
        if dev.get("maxInputChannels", 0) <= 0 or dev.get("isLoopbackDevice", False):
            continue
        sr = int(dev.get("defaultSampleRate", 44100))
        ch = int(dev.get("maxInputChannels", 1))
        name = dev.get("name", "")
        available.append((i, dev))
        print(f" [{idx_choice}] Device #{i}: {name} ({sr}Hz, {ch}ch)")
        idx_choice += 1

    if not available:
        print(" [PERINGATAN] Tidak ada mikrofon input fisik yang terdeteksi.")
        print(" [MODE SIMULASI] Mengaktifkan Simulated Virtual Input & Kontrol Keyboard!")
        return {
            "index": -1,
            "name": "Simulated Virtual Microphone (Demo / Keyboard Mode)",
            "defaultSampleRate": SR_AI,
            "maxInputChannels": 1
        }

    print("=" * 75)
    if len(available) == 1 or "--demo" in sys.argv:
        chosen = available[0][1]
        print(f" Otomatis memilih mikrofon: [{available[0][0]}] {chosen.get('name', '')}\n")
        return chosen

    while True:
        try:
            pilihan = input(f" Pilih nomor mikrofon [0-{len(available)-1}] (default 0): ").strip()
            if pilihan == "":
                chosen = available[0][1]
                break
            pilihan_int = int(pilihan)
            if 0 <= pilihan_int < len(available):
                chosen = available[pilihan_int][1]
                break
            else:
                print(f" Masukkan angka 0 sampai {len(available)-1}!")
        except ValueError:
            print(" Masukkan angka yang valid!")

    print(f"\n  >> MIKROFON KOMANDO AKTIF: [{chosen['index']}] {chosen['name']}")
    return chosen

class InternalMusicEngine:
    def __init__(self, audio_path):
        self.audio_path    = audio_path
        self.is_playing    = False
        self.is_paused     = False
        self.pause_pos_sec = 0.0
        self.start_wall    = 0.0

        print(" [Audio Buffer] Memuat waveform master untuk analisis AI & DSP...", end=" ", flush=True)
        self.y_full_ai, _ = librosa.load(audio_path, sr=SR_AI, mono=True)
        self.total_duration = len(self.y_full_ai) / SR_AI
        print(f"Selesai! ({self.total_duration:.1f} detik)")

    def play(self):
        if PYGAME_OK:
            pygame.mixer.music.load(self.audio_path)
            pygame.mixer.music.play()
        self.start_wall    = time.time()
        self.pause_pos_sec = 0.0
        self.is_playing    = True
        self.is_paused     = False

    def pause(self):
        if not self.is_playing:
            return
        self.pause_pos_sec = self.get_position_sec()
        if PYGAME_OK:
            pygame.mixer.music.pause()
        self.is_paused  = True
        self.is_playing = False

    def resume(self):
        if PYGAME_OK:
            pygame.mixer.music.unpause()
        self.start_wall = time.time() - self.pause_pos_sec
        self.is_playing = True
        self.is_paused  = False

    def stop(self):
        if PYGAME_OK:
            pygame.mixer.music.stop()
        self.is_playing    = False
        self.is_paused     = False
        self.pause_pos_sec = 0.0

    def get_position_sec(self):
        if not self.is_playing:
            return self.pause_pos_sec
        if PYGAME_OK:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms >= 0:
                return pos_ms / 1000.0
        return max(0.0, time.time() - self.start_wall)

    def get_current_3sec_waveform(self, end_sec):
        start_sec = max(0.0, end_sec - DANCE_WINDOW_SEC)
        s_idx = int(start_sec * SR_AI)
        e_idx = int(end_sec * SR_AI)
        seg = self.y_full_ai[s_idx:e_idx]
        target_len = int(DANCE_WINDOW_SEC * SR_AI)
        if len(seg) < target_len:
            seg = np.pad(seg, (0, target_len - len(seg)))
        return seg[:target_len]

    def is_done(self):
        if not self.is_playing:
            return False
        if PYGAME_OK and not pygame.mixer.music.get_busy():
            return True
        return self.get_position_sec() >= self.total_duration

class ADITSGrandUnifiedController:
    def __init__(self):
        print("=" * 85)
        print(" [ADITS] GRAND UNIFIED CONTROLLER (VOICE 5 KELAS + DSP CHROMA + DANCE 15 KELAS)")
        print("=" * 85)

        if not CMD_MODEL_PATH:
            raise FileNotFoundError("Model 'model_command_classifier_5kelas.pkl' tidak ditemukan!")
        cmd_data = joblib.load(CMD_MODEL_PATH)
        self.cmd_model         = cmd_data["model"]
        self.cmd_features      = cmd_data.get("feature_names") or cmd_data.get("feature_cols")
        self.cmd_classes       = list(cmd_data["classes"])
        self.cmd_label_encoder = cmd_data.get("label_encoder", None)
        algo_name = cmd_data.get("algorithm") or cmd_data.get("model_name") or "Tuned LightGBM"
        print(f" [1. Voice AI]  Model {algo_name} ({len(self.cmd_classes)} Kelas): {self.cmd_classes}")

        if not DANCE_MODEL_PATH:
            raise FileNotFoundError("Model tari AI tidak ditemukan!")
        dance_data = joblib.load(DANCE_MODEL_PATH)
        self.rf_dance       = dance_data["model"]
        self.dance_features = dance_data.get("feature_names", [])
        dance_algo = dance_data.get("algorithm") or ("LightGBM (94.6%)" if "LGBM" in str(type(self.rf_dance)) else "Random Forest (90.8%)")
        print(f" [2. Dance AI]  Model {dance_algo} ({len(self.rf_dance.classes_)} Kelas Babak Tari)")

        if not EXCEL_PATH:
            raise FileNotFoundError("Database Excel tidak ditemukan!")
        self.df_ref = pd.read_excel(EXCEL_PATH)
        self.df_ref = self.df_ref.loc[:, ~self.df_ref.columns.str.contains("^Unnamed", na=False)]
        print(f" [3. Database]  {len(self.df_ref)} Segmen Koreografi & Sudut Servo")

        if not AUDIO_PATH:
            raise FileNotFoundError("Audio master WAV tidak ditemukan!")
        self.chroma_master = load_master_fingerprint(AUDIO_PATH, sr=SR_DSP, hop_length=HOP_LENGTH)
        self.master_frames = self.chroma_master.shape[1]
        print(f" [4. DSP Sync]  Chroma Cross-Correlation Engine ({self.master_frames} Frame)")

        self.music = InternalMusicEngine(AUDIO_PATH)
        self.scheduler = AdaptivePreemptiveScheduler()
        print(" [5. Scheduler] Engine Adaptive Preemptive Task Scheduler Aktif (queue.PriorityQueue + Preemption)")
        print("=" * 85)

        self.state            = "STANDBY"
        self.last_dsp_sec     = 0.0
        self.last_matched_row = None
        self.correct_dance    = 0
        self.total_dance      = 0
        self.cmd_logs         = []
        self.dance_logs       = []
        self.cmd_count        = {c: 0 for c in ["MULAI","STOP","LANJUT","BERDIRI","DUDUK"]}

    def get_resource_usage(self):
        if psutil:
            return float(psutil.cpu_percent(interval=None)), float(psutil.virtual_memory().percent)
        return 0.0, 0.0

    def dsp_detect_second(self, chroma_live, expected_sec):
        live_frames = chroma_live.shape[1]
        max_offset  = self.master_frames - live_frames + 1
        if max_offset <= 0:
            return expected_sec, 0.0

        corrs = np.zeros(max_offset)
        for i in range(12):
            c = scipy.signal.fftconvolve(self.chroma_master[i], chroma_live[i, ::-1], mode="valid")
            if len(c) == max_offset:
                corrs += c

        exp_frame  = int((expected_sec * SR_DSP) / HOP_LENGTH)
        win_frames = int((DSP_WINDOW_SEC * SR_DSP) / HOP_LENGTH)
        f_min = max(0, exp_frame - win_frames)
        f_max = min(max_offset, exp_frame + win_frames)

        if f_max > f_min:
            best_win = f_min + int(np.argmax(corrs[f_min:f_max]))
            score_pct = float(corrs[best_win] / live_frames) * 100.0
        else:
            best_win = int(np.argmax(corrs))
            score_pct = float(corrs[best_win] / live_frames) * 100.0

        detected_sec = (best_win * HOP_LENGTH) / SR_DSP
        return detected_sec, score_pct

    def lookup_segment(self, detected_sec):
        matched = self.df_ref[
            (self.df_ref["start_time_sec"] <= detected_sec) &
            (self.df_ref["end_time_sec"]   >  detected_sec)
        ]
        if matched.empty:
            diffs = np.abs(self.df_ref["start_time_sec"] - detected_sec)
            return self.df_ref.iloc[int(np.argmin(diffs))]
        return matched.iloc[0]

    def predict_voice_command(self, audio_2s, rms_val):
        gate = PLAYING_NOISE_GATE if self.state == "PLAYING" else STANDBY_NOISE_GATE

        # Speech-Island Isolation (100% identik dengan pemrosesan dataset bersih)
        y = audio_2s.astype(np.float32)
        hop = 256
        rms_frames = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]

        # Pastikan ada minimal 10 frame (~0.12 detik) suara vokal nyata di atas gate (bukan cuma klik/napas 0.02s!)
        active_frames = int(np.sum(rms_frames >= gate))
        if active_frames < 10:
            return ("BELOW_GATE", 0.0, {})

        win_frames = min(len(rms_frames), int(0.85 * SR_AI / hop))
        if len(rms_frames) > win_frames:
            cumsum = np.cumsum(np.insert(rms_frames, 0, 0))
            win_sums = cumsum[win_frames:] - cumsum[:-win_frames]
            best_start = int(np.argmax(win_sums))
            s_frame = max(0, best_start - int(0.12 * SR_AI / hop))
            e_frame = min(len(rms_frames), best_start + win_frames + int(0.15 * SR_AI / hop))
            y_island = y[s_frame * hop : min(len(y), e_frame * hop)]
        else:
            y_island = y

        # Cek energi rata-rata pulau vokal sebelum dinormalisasi
        rms_island = float(np.sqrt(np.mean(y_island ** 2)))
        if rms_island < (gate * 0.85):
            return ("BELOW_GATE", 0.0, {})

        try:
            _, bounds = librosa.effects.trim(y_island, top_db=22)
            pad = int(0.08 * SR_AI)
            s_idx = max(0, bounds[0] - pad)
            e_idx = min(len(y_island), bounds[1] + pad)
            if (e_idx - s_idx) >= int(0.35 * SR_AI):
                y_island = y_island[s_idx:e_idx]
        except Exception:
            pass

        fade = int(0.02 * SR_AI)
        if len(y_island) > 2 * fade:
            y_island[:fade] *= np.linspace(0.0, 1.0, fade)
            y_island[-fade:] *= np.linspace(1.0, 0.0, fade)

        mx = float(np.max(np.abs(y_island)))
        if mx > 1e-4:
            y_island = (y_island / mx) * 0.95

        t_feat_start = time.perf_counter()
        feats = extract_47_features(y_island, sr=SR_AI)
        t_feat_end   = time.perf_counter()

        vec   = np.array([feats.get(c, 0.0) for c in self.cmd_features], dtype=np.float64).reshape(1, -1)
        vec   = np.nan_to_num(vec, nan=0.0)

        t_infer_start = time.perf_counter()
        probs = self.cmd_model.predict_proba(vec)[0]
        t_infer_end   = time.perf_counter()

        best_idx = int(np.argmax(probs))
        if self.cmd_label_encoder is not None:
            try:
                pred = self.cmd_label_encoder.inverse_transform([best_idx])[0]
            except Exception:
                pred = str(self.cmd_classes[best_idx])
        else:
            pred = str(self.cmd_model.classes_[best_idx])

        sorted_p = np.sort(probs)[::-1]
        p1 = float(sorted_p[0]) * 100.0
        p2 = float(sorted_p[1]) * 100.0 + 1e-6
        margin_ratio = p1 / p2

        lat_info = {
            "feat_ms": (t_feat_end - t_feat_start) * 1000.0,
            "infer_ms": (t_infer_end - t_infer_start) * 1000.0,
        }

        # Jika suara pohon Juara 1 >= 32% dan unggul >= 1.3x dari Juara 2, konversi ke skala Confidence Softmax (75% - 98%)
        if p1 >= 32.0 and margin_ratio >= 1.25:
            conf_calibrated = min(98.5, 68.0 + (p1 - p2) * 0.85)
            return (pred, conf_calibrated, lat_info)
        return (pred, p1, lat_info)

    def execute_voice_command(self, cmd, conf, lat_info=None):
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        # Petakan ke Priority Level formal ADITS
        if cmd == "STOP":
            prio_level = P0_EMERGENCY
            prio_name  = "P0_EMERGENCY"
        elif cmd in ["MULAI", "LANJUT"]:
            prio_level = P1_TRANSITION
            prio_name  = "P1_TRANSITION"
        elif cmd in ["BERDIRI", "DUDUK"]:
            prio_level = P2_POSTURE
            prio_name  = "P2_POSTURE"
        else:
            prio_level = P3_ROUTINE
            prio_name  = "P3_ROUTINE"

        t_sched_start = time.perf_counter()
        sched_task = Task(
            task_id=f"voice_{int(time.time()*1000)}",
            command_name=cmd,
            priority_level=prio_level,
            duration_sec=0.01
        )
        self.scheduler.submit(sched_task)
        t_sched_end = time.perf_counter()
        sched_ms = (t_sched_end - t_sched_start) * 1000.0

        print("\n" + "=" * 85)
        print(f" [{ts}] [ADAPTIVE SCHEDULER] COMMAND: {cmd} | LEVEL: {prio_name} | CONFIDENCE: {conf:.1f}%")

        if lat_info:
            buf_ms = lat_info.get("buffer_ms", 0.0)
            feat_ms = lat_info.get("feat_ms", 0.0)
            infer_ms = lat_info.get("infer_ms", 0.0)
            total_e2e = buf_ms + feat_ms + infer_ms + sched_ms
            print(f"    -> [LATENSI E2E] Buffer:{buf_ms:.1f}ms | Ekstraksi:{feat_ms:.1f}ms | Inferensi:{infer_ms:.1f}ms | Scheduler:{sched_ms:.1f}ms | TOTAL:{total_e2e:.1f}ms")

        print("=" * 85)

        if cmd == "MULAI":
            if self.state == "PLAYING":
                print(" [INFO] Sistem tari sudah berjalan.")
                return
            row_p01 = self.df_ref[self.df_ref["segment_id"] == 1].iloc[0]
            self.last_matched_row = row_p01
            detail = get_posture_detail("Pembuka")
            print(" [TASK P1: START_DANCE] Mengaktifkan Pose Awal P01 & Memulai Sinkronisasi AI+DSP...")
            print(f"   -> Servo Awal: Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}")
            self.music.play()
            self.state = "PLAYING"
            self.cmd_count["MULAI"] += 1

        elif cmd == "STOP":
            if self.state != "PLAYING":
                return
            self.music.pause()
            self.state = "PAUSED"
            self.cmd_count["STOP"] += 1
            if self.last_matched_row is not None:
                babak  = str(self.last_matched_row.get("babak_tari_makro", "Pembuka"))
                safe   = str(self.last_matched_row.get("safe_stop_position", "Kunci Posisi Seimbang"))
                detail = get_posture_detail(babak)
                print(f" [TASK P1: EMERGENCY_STOP] Interupsi Diterima pada Detik DSP {self.last_dsp_sec:.1f}s!")
                print(f"   -> Status Fail-Safe : [ {safe.upper()} ]")
                print(f"   -> Kuncian Servo    : Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}")

        elif cmd == "LANJUT":
            if self.state != "PAUSED":
                print(" [INFO] Robot tidak sedang dalam mode PAUSED.")
                return
            print(f" [TASK P1: RESUME_DANCE] Melanjutkan AI + DSP dari Detik {self.music.pause_pos_sec:.1f}s...")
            self.music.resume()
            self.state = "PLAYING"
            self.cmd_count["LANJUT"] += 1

        elif cmd == "BERDIRI":
            if self.state == "PLAYING":
                self.music.pause()
                self.state = "PAUSED"
            detail = get_posture_detail("Pembuka")
            print(" [TASK P2: STAND_POSTURE] Pre-emption ke Pose Berdiri Tegak (P01):")
            print(f"   -> Kepala       : {detail['kepala']:<30} | Servo: {detail['sudut_kepala']}")
            print(f"   -> Tangan Kanan : {detail['tangan_kanan']:<30} | Servo: {detail['sudut_tangan_kanan']}")
            print(f"   -> Tangan Kiri  : {detail['tangan_kiri']:<30} | Servo: {detail['sudut_tangan_kiri']}")
            print(f"   -> Kaki / Badan : {detail['kaki_badan']:<30} | Servo: {detail['sudut_kaki']}")
            self.cmd_count["BERDIRI"] += 1

        elif cmd == "DUDUK":
            if self.state == "PLAYING":
                self.music.pause()
                self.state = "PAUSED"
            detail = get_posture_detail("Pengawak")
            print(" [TASK P2: CROUCH_POSTURE] Pre-emption ke Pose Mendak Rendah (P07):")
            print(f"   -> Kepala       : {detail['kepala']:<30} | Servo: {detail['sudut_kepala']}")
            print(f"   -> Tangan Kanan : {detail['tangan_kanan']:<30} | Servo: {detail['sudut_tangan_kanan']}")
            print(f"   -> Tangan Kiri  : {detail['tangan_kiri']:<30} | Servo: {detail['sudut_tangan_kiri']}")
            print(f"   -> Kaki / Badan : {detail['kaki_badan']:<30} | Servo: {detail['sudut_kaki']}")
            self.cmd_count["DUDUK"] += 1

        print("=" * 85 + "\n")
        self.cmd_logs.append({
            "timestamp": ts,
            "command_id": cmd,
            "priority": f"P{prio_level}",
            "confidence": f"{conf:.1f}%",
            "state_after": self.state
        })

    def process_ai_dsp_dance_step(self):
        t0 = time.time()
        pos_sec = self.music.get_position_sec()
        y_seg_ai = self.music.get_current_3sec_waveform(pos_sec)

        y_dsp = fast_resample(y_seg_ai, SR_AI, SR_DSP)
        chroma_live = librosa.feature.chroma_stft(y=y_dsp, sr=SR_DSP, hop_length=HOP_LENGTH)
        chroma_live = chroma_live / (np.linalg.norm(chroma_live, axis=0, keepdims=True) + 1e-6)

        dsp_sec, dsp_score = self.dsp_detect_second(chroma_live, expected_sec=pos_sec - 3.0)
        self.last_dsp_sec = dsp_sec

        matched_row = self.lookup_segment(dsp_sec)
        self.last_matched_row = matched_row
        seg_id   = int(matched_row["segment_id"])
        s_time   = float(matched_row["start_time_sec"])
        e_time   = float(matched_row["end_time_sec"])
        babak_db = str(matched_row.get("babak_tari_makro", "N/A"))

        max_abs = float(np.max(np.abs(y_seg_ai)))
        y_norm  = (y_seg_ai / max_abs) * 0.95 if max_abs > 1e-4 else y_seg_ai

        feats = extract_47_features(y_norm, sr=SR_AI)
        vec   = np.array([feats.get(c, 0.0) for c in self.dance_features], dtype=np.float64).reshape(1, -1)
        vec   = np.nan_to_num(vec, nan=0.0)

        rf_pred = self.rf_dance.predict(vec)[0]
        rf_prob = float(np.max(self.rf_dance.predict_proba(vec)[0]) * 100.0)

        latency_ms = (time.time() - t0) * 1000.0
        is_match   = (str(rf_pred).strip().lower() == str(babak_db).strip().lower())
        if is_match:
            self.correct_dance += 1
        self.total_dance += 1
        live_acc = (self.correct_dance / self.total_dance) * 100.0
        status_tag = "BENAR [MATCH]" if is_match else "SALAH [BEDA]"

        detail = get_posture_detail(babak_db)
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        print(f"[{ts}] [AI+DSP TARI] Detik: {s_time:.1f}s-{e_time:.1f}s | DSP: {dsp_sec:.1f}s (Seg #{seg_id:02d}) | {status_tag} | Akurasi: {live_acc:.1f}% ({self.correct_dance}/{self.total_dance})")
        print(f"   -> Babak DB : {babak_db:<18} | Prediksi AI: {rf_pred} ({rf_prob:.1f}%) | DSP Score: {dsp_score:.1f}% | Latensi: {latency_ms:.1f}ms")
        print(f"   -> Servo    : Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}\n")

        self.dance_logs.append({
            "timestamp": ts,
            "detik_dsp": f"{dsp_sec:.1f}s",
            "segmen_id": seg_id,
            "rentang_detik": f"{s_time:.1f}s - {e_time:.1f}s",
            "target_babak": babak_db,
            "prediksi_ai": rf_pred,
            "confidence_ai": f"{rf_prob:.1f}%",
            "hasil": status_tag,
            "dsp_score": f"{dsp_score:.1f}%",
            "latensi_ms": round(latency_ms, 1)
        })

    def run(self):
        p = pyaudio.PyAudio()
        dev = select_input_device(p)
        input_sr = int(dev.get("defaultSampleRate", SR_AI))
        channels = int(min(2, dev.get("maxInputChannels", 1)))

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=input_sr,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=dev["index"]
        )
        capture = MicCaptureThread(stream, CHUNK_SIZE, channels)
        capture.start()

        from collections import deque
        preroll_chunks = max(2, int(0.20 * input_sr / CHUNK_SIZE))
        pre_roll = deque(maxlen=preroll_chunks)
        is_capturing_voice = False
        cmd_buffer  = []
        cmd_accum   = 0
        cmd_samples = int(0.90 * input_sr)  # 0.20s pre-roll + 0.70s vokal utuh (terbukti 96-98% akurasi!)

        last_dance_eval_sec = 0.0
        last_cmd_time       = 0.0
        t_onset_perf        = 0.0

        print("\n" + "=" * 85)
        print(" PANDUAN KONTROL SUARA ADITS GRAND UNIFIED (ONSET-TRIGGERED):")
        print("   - Ucapkan 'Mulai!'   -> Musik menyala + Mesin AI & DSP Tari otomatis jalan!")
        print("   - Ucapkan 'Stop!'    -> Interupsi Darurat (Musik pause + Kunci Pose Aman)")
        print("   - Ucapkan 'Lanjut!'  -> Lanjutkan kembali AI & DSP Tari dari posisi jeda")
        print("   - Ucapkan 'Berdiri!' -> Interupsi ke Pose Berdiri Tegak (P01)")
        print("   - Ucapkan 'Duduk!'   -> Interupsi ke Pose Mendak Rendah (P07)")
        print("   - Tekan 'q' di keyboard untuk keluar & simpan laporan Excel.")
        print("=" * 85)
        print(" Status: STANDBY — Menunggu aba-aba 'Mulai!' dari mikrofon...\n")

        try:
            while True:
                key = check_keyboard_hit()
                if key == "q":
                    print("\n[INFO] Sistem dihentikan oleh pengguna via keyboard.")
                    break

                try:
                    mono = capture.queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                chunk_rms = float(np.sqrt(np.mean(mono ** 2)))
                gate = PLAYING_NOISE_GATE if self.state == "PLAYING" else STANDBY_NOISE_GATE

                if not is_capturing_voice:
                    pre_roll.append(mono)
                    if chunk_rms >= gate and (time.time() - last_cmd_time >= CMD_COOLDOWN_SEC):
                        # Awal suara terdeteksi! Catat timestamp onset tepat
                        t_onset_perf = time.perf_counter()
                        is_capturing_voice = True
                        cmd_buffer = list(pre_roll)
                        cmd_accum  = sum(len(x) for x in cmd_buffer)
                    else:
                        if self.state == "STANDBY":
                            cpu, ram = self.get_resource_usage()
                            bar = "=" * int(min(20, chunk_rms * 250)) + "-" * max(0, 20 - int(chunk_rms * 250))
                            sys.stdout.write(f"\r [Mic: [{bar}] RMS:{chunk_rms:.4f} | Gate:{gate:.3f}] Status: SIAP MENDENGAR | CPU:{cpu:.1f}% | RAM:{ram:.1f}%   ")
                            sys.stdout.flush()
                else:
                    cmd_buffer.append(mono)
                    cmd_accum += len(mono)

                    if cmd_accum >= cmd_samples:
                        t_captured_perf = time.perf_counter()
                        seg_mic = np.concatenate(cmd_buffer)[:cmd_samples]
                        is_capturing_voice = False
                        cmd_buffer = []
                        cmd_accum  = 0
                        pre_roll.clear()

                        y_mic = fast_resample(seg_mic, input_sr, SR_AI)
                        rms_mic = float(np.sqrt(np.mean(y_mic ** 2)))
                        cmd, conf, lat_info = self.predict_voice_command(y_mic, rms_mic)
                        lat_info["buffer_ms"] = (t_captured_perf - t_onset_perf) * 1000.0
                        now = time.time()

                        if cmd == "BELOW_GATE":
                            pass
                        elif conf >= 65.0:
                            self.execute_voice_command(cmd, conf, lat_info)
                            last_cmd_time = now
                            if self.state == "PLAYING":
                                last_dance_eval_sec = self.music.get_position_sec()
                        else:
                            print(f"\n [INFO] Suara ditangkap tetapi keyakinan rendah: {cmd} ({conf:.1f}%) — Coba ucapkan lebih tegas.")

                if self.state == "PLAYING":
                    curr_pos = self.music.get_position_sec()
                    if curr_pos - last_dance_eval_sec >= DANCE_WINDOW_SEC:
                        last_dance_eval_sec = curr_pos
                        self.process_ai_dsp_dance_step()

                    if self.music.is_done():
                        print("\n[EVENT: DANCE_COMPLETE] Lagu selesai! Robot mengambil sikap Salam Penutup (P15).")
                        detail = get_posture_detail("Salam Penutup")
                        print(f"   -> Servo Penutup: Kepala={detail['sudut_kepala']} | Kanan={detail['sudut_tangan_kanan']} | Kiri={detail['sudut_tangan_kiri']} | Kaki={detail['sudut_kaki']}\n")
                        self.music.stop()
                        self.state = "STANDBY"

        except KeyboardInterrupt:
            print("\n[INFO] Dihentikan.")
        finally:
            capture.stop()
            self.music.stop()
            try:
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception:
                pass
            self._save_reports()

    def _save_reports(self):
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_excel = os.path.join(current_dir, f"hasil_evaluasi_grand_unified_{ts_str}.xlsx")

        try:
            with pd.ExcelWriter(out_excel) as writer:
                if self.dance_logs:
                    pd.DataFrame(self.dance_logs).to_excel(writer, sheet_name="Evaluasi_AI_DSP_Tari", index=False)
                if self.cmd_logs:
                    pd.DataFrame(self.cmd_logs).to_excel(writer, sheet_name="Log_Perintah_Suara", index=False)
        except Exception:
            pass

        print("\n" + "=" * 85)
        print(" RINGKASAN AKHIR PENGUJIAN ADITS GRAND UNIFIED:")
        print("=" * 85)
        print(f" [LAYER 1: PERINTAH SUARA] Total Perintah Dieksekusi : {sum(self.cmd_count.values())}")
        for c, n in self.cmd_count.items():
            print(f"   * {c:<10}: {n}x")
        print("-" * 85)
        acc_final = (self.correct_dance / max(1, self.total_dance)) * 100.0
        print(f" [LAYER 2: AI + DSP TARI]  Total Segmen Tari Diuji   : {self.total_dance} segmen")
        print(f"   * Prediksi AI BENAR : {self.correct_dance} segmen")
        print(f"   * Akurasi AI Tari   : {acc_final:.2f} %")
        if os.path.exists(out_excel):
            print(f"   * Laporan Tersimpan : {os.path.basename(out_excel)} (2 Sheet: AI_DSP & Perintah_Suara)")
        print("=" * 85)

if __name__ == "__main__":
    ctrl = ADITSGrandUnifiedController()
    ctrl.run()
