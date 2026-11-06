"""
================================================================================
EVALUASI SENSITIVITAS AKURASI TERHADAP PANJANG BUFFER SUARA
ADITS KRSTI - Tim Peneliti Dewantara (Universitas Negeri Malang)
================================================================================
Menguji dampak empiris pemendekan jendela audio (1.3s -> 1.0s -> 0.8s -> 0.6s)
terhadap akurasi klasifikasi 5 kelas perintah suara (model LightGBM 96%).
================================================================================
"""

import os
import glob
import sys
import numpy as np
import pandas as pd
import librosa
import joblib
from sklearn.metrics import accuracy_score, classification_report

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WAV_DIR = os.path.join(BASE_DIR, "dataset_perintah_suara")
if not os.path.exists(WAV_DIR):
    alt_wav = os.path.join(BASE_DIR, "..", "dataset_perintah_suara")
    if os.path.exists(alt_wav):
        WAV_DIR = alt_wav
SR = 22050
DURATIONS = [1.3, 1.0, 0.8, 0.6]

def extract_47_features(audio_seg, sr=SR):
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

def main():
    print("=" * 80)
    print("  EVALUASI EMPIRIS SENSITIVITAS BUFFER SUARA vs AKURASI LIGHTGBM")
    print("=" * 80)

    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Model {MODEL_PATH} tidak ditemukan!")
        return

    pkg = joblib.load(MODEL_PATH)
    model = pkg["model"]
    feature_names = pkg.get("feature_names") or pkg.get("feature_cols")
    label_encoder = pkg.get("label_encoder", None)
    classes = pkg["classes"]

    print(f"Model: {pkg.get('algorithm', 'LightGBM')} | Kelas: {classes}")

    # Kumpulkan semua file WAV
    samples = []
    for cls_name in classes:
        cls_dir = os.path.join(WAV_DIR, cls_name)
        if not os.path.exists(cls_dir):
            continue
        for wav_file in sorted(glob.glob(os.path.join(cls_dir, "*.wav"))):
            samples.append((wav_file, cls_name))

    print(f"Total audio WAV terkumpul: {len(samples)} berkas (50 per kelas)")
    if len(samples) == 0:
        print("[ERROR] Tidak ada berkas WAV ditemukan di dataset_perintah_suara/")
        return

    # Muat audio utuh ke memori
    loaded_audio = []
    for wav_path, label in samples:
        y, _ = librosa.load(wav_path, sr=SR)
        loaded_audio.append((y, label, os.path.basename(wav_path)))

    summary_rows = []

    for dur in DURATIONS:
        target_len = int(dur * SR)
        print(f"\n--- Pengujian Buffer: {dur:.2f} detik ({target_len} sampel) ---")

        y_true = []
        y_pred = []

        for y_raw, label, fname in loaded_audio:
            # Potong dari onset vokal (atau awal) sepanjang target_len
            if len(y_raw) > target_len:
                y_crop = y_raw[:target_len]
            else:
                y_crop = np.pad(y_raw, (0, target_len - len(y_raw)), mode="constant")

            feats = extract_47_features(y_crop, sr=SR)
            vec = np.array([feats[col] for col in feature_names]).reshape(1, -1)
            raw_pred = model.predict(vec)[0]

            if label_encoder is not None and isinstance(raw_pred, (int, np.integer)):
                pred_label = label_encoder.inverse_transform([raw_pred])[0]
            elif isinstance(raw_pred, (int, np.integer)) and hasattr(model, "classes_"):
                pred_label = classes[raw_pred]
            else:
                pred_label = str(raw_pred)

            y_true.append(label)
            y_pred.append(pred_label)

        acc = accuracy_score(y_true, y_pred) * 100.0
        print(f"  Akurasi Keseluruhan: {acc:.2f} %")

        # Hitung akurasi per kelas
        cls_accs = {}
        for c in classes:
            c_mask = [yt == c for yt in y_true]
            if sum(c_mask) > 0:
                c_acc = accuracy_score([y_true[i] for i, m in enumerate(c_mask) if m],
                                       [y_pred[i] for i, m in enumerate(c_mask) if m]) * 100.0
                cls_accs[c] = round(c_acc, 2)
            else:
                cls_accs[c] = 0.0

        print(f"  Akurasi per Kelas  : {cls_accs}")

        row = {
            "durasi_buffer_sec": dur,
            "durasi_buffer_ms": int(dur * 1000),
            "akurasi_total_pct": round(acc, 2),
            "total_sampel": len(y_true),
        }
        for c in classes:
            row[f"akurasi_{c}_pct"] = cls_accs[c]
        summary_rows.append(row)

    df_res = pd.DataFrame(summary_rows)
    out_xlsx = os.path.join(BASE_DIR, "hasil_sensitivitas_buffer_audio.xlsx")
    df_res.to_excel(out_xlsx, index=False)

    print("\n" + "=" * 80)
    print("  RINGKASAN EMPIRIS SENSITIVITAS BUFFER vs AKURASI")
    print("=" * 80)
    print(df_res[["durasi_buffer_sec", "durasi_buffer_ms", "akurasi_total_pct"]].to_string(index=False))
    print(f"\nHasil lengkap tersimpan ke: {out_xlsx}")
    print("=" * 80)

if __name__ == "__main__":
    main()
