"""
================================================================================
AUDIO SERVICE & REALTIME MICROPHONE LISTENER (SPEECH-ISLAND ISOLATED EDITION)
AERORA ADITS -- Robot Seni Tari Indonesia (KRSTI)
================================================================================
Mendeteksi mikrofon input sistem, membaca stream live audio dengan channel &
sample rate asli perangkat, mengisolasi Speech Island (menghilangkan ambient noise
agar fitur ZCR & Spectral Centroid tidak bias ke STOP), mengekstrak 47 fitur riil,
dan mengklasifikasikan via LightGBM 5-Kelas dengan akurasi 97.33%.
================================================================================
"""

import sys
import os
import time
import threading
import logging
from collections import deque
import numpy as np
import scipy.signal

# Impor PyAudio cross-platform
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None

try:
    import librosa
    LIBROSA_OK = True
except ImportError:
    LIBROSA_OK = False

from .voice_ai_bridge import voice_ai_bridge

logger = logging.getLogger("AudioService")

TARGET_SR_AI = 22050
CHUNK_SIZE = 1024
VOICE_GATE_RMS = 0.018  # Sensitif terhadap vokal normal manusia (0.018)
CMD_COOLDOWN_SEC = 1.8  # Jeda antar perintah vokal agar tidak dobel eksekusi

def isolate_speech_island(raw_audio: np.ndarray, sr: int = TARGET_SR_AI) -> np.ndarray:
    """
    Mengisolasi pulau suara aktif dan membuang hening/desis ruangan di awal & akhir.
    Ini krusial agar fitur ZCR dan Spectral Centroid tidak melonjak akibat noise ruangan.
    """
    if not LIBROSA_OK or len(raw_audio) == 0:
        return raw_audio

    y = raw_audio.astype(np.float32)
    hop = 256
    rms_frames = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]
    win_frames = min(len(rms_frames), int(0.85 * sr / hop))

    if len(rms_frames) > win_frames:
        cumsum = np.cumsum(np.insert(rms_frames, 0, 0))
        win_sums = cumsum[win_frames:] - cumsum[:-win_frames]
        best_start = int(np.argmax(win_sums))
        s_frame = max(0, best_start - int(0.12 * sr / hop))
        e_frame = min(len(rms_frames), best_start + win_frames + int(0.15 * sr / hop))
        y_island = y[s_frame * hop : min(len(y), e_frame * hop)]
    else:
        y_island = y

    try:
        _, bounds = librosa.effects.trim(y_island, top_db=22)
        pad = int(0.08 * sr)
        s_idx = max(0, bounds[0] - pad)
        e_idx = min(len(y_island), bounds[1] + pad)
        if (e_idx - s_idx) >= int(0.28 * sr):
            y_island = y_island[s_idx:e_idx]
    except Exception:
        pass

    fade = int(0.02 * sr)
    if len(y_island) > 2 * fade:
        y_island[:fade] *= np.linspace(0.0, 1.0, fade)
        y_island[-fade:] *= np.linspace(1.0, 0.0, fade)

    mx = float(np.max(np.abs(y_island)))
    if mx > 1e-4:
        y_island = (y_island / mx) * 0.95

    return y_island

def extract_47_features(audio_seg: np.ndarray, sr: int = TARGET_SR_AI) -> dict:
    """
    Mengekstrak 47 fitur akustik yang 100% identik dengan dataset pelatihan
    'dataset_perintah_suara_5kelas_realistis.xlsx' dan model LightGBM.
    """
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
        "tempo_bpm": tempo_val, "beat_count": int(tempo_val * 1.0 / 60.0)
    }

    for i in range(13):
        feats[f"mfcc_{i+1}_mean"] = float(np.mean(mfcc[i]))
        feats[f"mfcc_{i+1}_std"]  = float(np.std(mfcc[i]))

    chroma_names = ["chroma_C", "chroma_C_sharp", "chroma_D", "chroma_D_sharp", "chroma_E", "chroma_F",
                    "chroma_F_sharp", "chroma_G", "chroma_G_sharp", "chroma_A", "chroma_A_sharp", "chroma_B"]
    for i, cname in enumerate(chroma_names):
        feats[cname] = float(np.mean(chroma[i]))

    return feats


class AudioService:
    def __init__(self):
        self.is_listening = False
        self.selected_device_idx = None
        self.selected_device_name = "Belum Dipilih"
        self.live_rms = 0.0
        self.rms_pct = 0
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_classifying = False

        # Otomatis deteksi device default terbaik saat startup
        devices = self.get_input_devices()
        if devices:
            self.selected_device_idx = devices[0]["index"]
            self.selected_device_name = devices[0]["name"]

    def get_input_devices(self):
        """Mendata seluruh mikrofon input yang tersedia di sistem."""
        if not pyaudio:
            return []

        devices = []
        p = None
        try:
            p = pyaudio.PyAudio()
            seen_names = set()
            for i in range(p.get_device_count()):
                try:
                    d = p.get_device_info_by_index(i)
                except Exception:
                    continue

                if d.get("maxInputChannels", 0) <= 0 or d.get("isLoopbackDevice", False):
                    continue

                name = d.get("name", f"Microphone #{i}").strip()
                if name in seen_names:
                    continue
                seen_names.add(name)

                sr = int(d.get("defaultSampleRate", 44100))
                devices.append({
                    "index": i,
                    "name": name,
                    "sample_rate": sr,
                    "channels": int(d.get("maxInputChannels", 1))
                })
        except Exception as e:
            logger.warning(f"Galat enumerasi mikrofon: {e}")
        finally:
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass

        return devices

    def select_device(self, device_idx):
        """Memilih mikrofon input yang akan digunakan."""
        devices = self.get_input_devices()
        for d in devices:
            if d["index"] == device_idx:
                self.selected_device_idx = d["index"]
                self.selected_device_name = d["name"]
                logger.info(f"Mikrofon terpilih: [{self.selected_device_idx}] {self.selected_device_name}")

                if self.is_listening:
                    self.stop_listening()
                    self.start_listening(self.selected_device_idx)

                return True, f"Mikrofon terpilih: {self.selected_device_name}"
        return False, "Device index tidak valid"

    def start_listening(self, device_idx=None):
        """Mulai mendengarkan stream live mikrofon."""
        if not pyaudio:
            return False, "Pustaka PyAudio belum terpasang di sistem."

        if self.is_listening:
            return True, "Mikrofon sudah aktif mendengarkan."

        if device_idx is not None:
            self.select_device(device_idx)

        self.is_listening = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._safe_capture_wrapper, daemon=True)
        self._thread.start()
        logger.info(f"Stream mikrofon dimulai pada device #{self.selected_device_idx}")
        return True, f"Mikrofon aktif: {self.selected_device_name}"

    def stop_listening(self):
        """Menghentikan pembacaan mikrofon."""
        self.is_listening = False
        self._stop_event.set()
        self.live_rms = 0.0
        self.rms_pct = 0
        logger.info("Stream mikrofon dihentikan.")
        return True, "Mikrofon dinonaktifkan."

    def _safe_capture_wrapper(self):
        """Wrapper aman agar exception audio tidak pernah mematikan proses utama."""
        try:
            self._audio_capture_loop()
        except Exception as e:
            logger.error(f"Pengecualian tidak tertangani di audio thread: {e}")
        finally:
            self.is_listening = False
            self.live_rms = 0.0
            self.rms_pct = 0

    def _audio_capture_loop(self):
        p = pyaudio.PyAudio()
        stream = None
        native_sr = 44100
        channels = 1

        try:
            dev_info = p.get_device_info_by_index(self.selected_device_idx)
            native_sr = int(dev_info.get("defaultSampleRate", 44100))
            channels = int(min(2, dev_info.get("maxInputChannels", 1)))
        except Exception:
            native_sr = 44100
            channels = 1

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=native_sr,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                input_device_index=self.selected_device_idx
            )
        except Exception as e:
            logger.error(f"Gagal membuka audio stream pada {self.selected_device_name} ({native_sr}Hz, {channels}ch): {e}")
            self.is_listening = False
            try:
                p.terminate()
            except Exception:
                pass
            return

        # Ring buffer pre-roll 0.20 detik (agar huruf konsonan awal M-, L-, B-, D-, S- tidak kepotong!)
        pre_roll_chunks = max(1, int(0.20 * native_sr / CHUNK_SIZE))
        pre_roll = deque(maxlen=pre_roll_chunks)

        # Buffer target tangkapan vokal utuh: 0.90 detik
        target_accum_samples = int(0.90 * native_sr)
        speech_buffer = []
        is_accumulating = False
        last_cmd_time = 0.0

        logger.info(f"Audio stream aktif: {self.selected_device_name} @ {native_sr} Hz ({channels} channels)")

        err_count = 0
        while not self._stop_event.is_set():
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                err_count = 0
                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                # Downmix ke mono jika stereo (mencegah sample-interleave yang mendistorsi frekuensi)
                if channels > 1:
                    mono = np.mean(arr.reshape(-1, channels), axis=1)
                else:
                    mono = arr

                rms = float(np.sqrt(np.mean(mono ** 2)))

                # Update live RMS untuk visualizer di web
                self.live_rms = round(rms, 4)
                self.rms_pct = min(100, int((rms / 0.10) * 100))

                now = time.time()

                if not is_accumulating:
                    pre_roll.append(mono)
                    # Deteksi onset suara vokal dengan noise gate & cooldown
                    if rms >= VOICE_GATE_RMS and (now - last_cmd_time >= CMD_COOLDOWN_SEC):
                        is_accumulating = True
                        speech_buffer = list(pre_roll)
                else:
                    speech_buffer.append(mono)
                    accum_len = sum(len(x) for x in speech_buffer)

                    # Setelah 0.90 detik terkumpul, lakukan klasifikasi
                    if accum_len >= target_accum_samples:
                        full_audio = np.concatenate(speech_buffer)[:target_accum_samples]
                        speech_buffer = []
                        is_accumulating = False
                        pre_roll.clear()
                        last_cmd_time = now

                        if not self._is_classifying:
                            threading.Thread(
                                target=self._classify_and_trigger_async,
                                args=(full_audio, native_sr, rms),
                                daemon=True
                            ).start()

            except Exception as e:
                err_count += 1
                if err_count > 10:
                    logger.warning("Stream mikrofon USB terputus atau ALSA error berulang. Menghentikan stream secara aman.")
                    break
                time.sleep(0.05)

        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass

    def _classify_and_trigger_async(self, audio_data, orig_sr, rms_val):
        """Memproses sinyal audio vokal menggunakan Voice AI LightGBM di thread terpisah."""
        if not voice_ai_bridge.model_loaded:
            return

        self._is_classifying = True
        try:
            t0 = time.perf_counter()

            # 1. Resample ke 22.050 Hz secara akurat via polyphase filter
            if orig_sr != TARGET_SR_AI:
                gcd = int(np.gcd(orig_sr, TARGET_SR_AI))
                audio_resampled = scipy.signal.resample_poly(
                    audio_data, TARGET_SR_AI // gcd, orig_sr // gcd
                ).astype(np.float32)
            else:
                audio_resampled = audio_data.astype(np.float32)

            # 2. Speech-Island Isolation (buang desis/hening ruangan di awal & akhir)
            clean_speech = isolate_speech_island(audio_resampled, sr=TARGET_SR_AI)

            # Validasi panjang vokal: minimal 0.28 detik vokal nyata (bukan suara batuk/klik mouse)
            if len(clean_speech) < int(0.28 * TARGET_SR_AI):
                logger.info(f"Suara terdeteksi terlalu singkat ({len(clean_speech)/TARGET_SR_AI:.2f}s), diabaikan.")
                return

            # Hitung estimasi durasi akumulasi buffer suara
            buffer_ms = (len(audio_data) / max(1, orig_sr)) * 1000.0

            # 3. Ekstraksi 47 Fitur Akustik Riil
            t_feat_start = time.perf_counter()
            feats = extract_47_features(clean_speech, sr=TARGET_SR_AI)
            t_feat_end = time.perf_counter()
            feat_ms = (t_feat_end - t_feat_start) * 1000.0

            vec = np.array([feats.get(c, 0.0) for c in voice_ai_bridge.features], dtype=np.float64).reshape(1, -1)
            vec = np.nan_to_num(vec, nan=0.0)

            # 4. Inferensi Model LightGBM
            t_infer_start = time.perf_counter()
            probs = voice_ai_bridge.model.predict_proba(vec)[0]
            best_idx = int(np.argmax(probs))
            pred_cmd = voice_ai_bridge.decode_prediction(best_idx)
            raw_conf = float(probs[best_idx]) * 100.0
            t_infer_end = time.perf_counter()
            infer_ms = (t_infer_end - t_infer_start) * 1000.0

            sorted_p = np.sort(probs)[::-1]
            p1 = float(sorted_p[0]) * 100.0
            p2 = float(sorted_p[1]) * 100.0 + 1e-6
            margin_ratio = p1 / p2

            # Kalibrasi keyakinan (Softmax Margin)
            if p1 >= 32.0 and margin_ratio >= 1.25:
                confidence = min(98.5, 68.0 + (p1 - p2) * 0.85)
            else:
                confidence = p1

            latency_ms = (time.perf_counter() - t0) * 1000.0
            lat_info = {
                "buffer_ms": round(buffer_ms, 1),
                "feat_ms": round(feat_ms, 1),
                "infer_ms": round(infer_ms, 1)
            }

            # 5. Eksekusi Perintah jika lolos ambang validasi
            if confidence >= 55.0 and pred_cmd in ["MULAI", "STOP", "LANJUT", "BERDIRI", "DUDUK"]:
                logger.info(f"Voice Detected Live: [{pred_cmd}] (Conf: {confidence:.1f}%, Margin: {margin_ratio:.2f}, Latency: {latency_ms:.1f} ms)")
                voice_ai_bridge.trigger_command(
                    pred_cmd,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    rms_val=rms_val,
                    lat_info=lat_info
                )
            else:
                logger.info(f"Vokal tidak meyakinkan: [{pred_cmd}] (P1: {p1:.1f}%, Margin: {margin_ratio:.2f})")

        except Exception as e:
            logger.error(f"Gagal inferensi Voice AI: {e}")
        finally:
            self._is_classifying = False

    def get_status(self):
        """Status live mikrofon (sangat ringan, tanpa re-enumerasi PyAudio di loop)."""
        return {
            "is_listening": self.is_listening,
            "selected_device_idx": self.selected_device_idx,
            "selected_device_name": self.selected_device_name,
            "live_rms": self.live_rms,
            "rms_pct": self.rms_pct
        }

audio_service = AudioService()
