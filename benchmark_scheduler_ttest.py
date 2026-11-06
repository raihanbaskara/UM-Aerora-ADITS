"""
================================================================================
BENCHMARK SCHEDULER: UJI-T BERPASANGAN (MODE ADAPTIF vs MODE STATIS)
================================================================================
Menjalankan N skenario IDENTIK pada dua scheduler (Adaptif preemptive vs
Statis FIFO), mengukur latensi respons tugas darurat (P0_EMERGENCY / STOP)
yang datang di tengah tugas rutin (P3_ROUTINE) yang sedang berjalan, lalu
membandingkan dua mode itu dengan uji-t berpasangan (scipy.stats.ttest_rel)
sesuai Bab 3.3 proposal.

PENTING -- soal integritas uji statistik:
Skrip ini TIDAK mengasumsikan hasilnya akan signifikan. p-value dihitung dari
data yang benar-benar dihasilkan tiap trial, dan dilaporkan apa adanya --
termasuk kalau ternyata p >= 0.05 atau efeknya kecil. Jangan edit angka
target di skrip ini supaya "terlihat lolos"; kalau hasilnya tidak
sebagus yang diharapkan proposal, itu sendiri adalah temuan yang sah untuk
dilaporkan dan dijelaskan penyebabnya.

Skenario per trial (dipasangkan sama persis di kedua mode lewat random seed):
  1. Task P3_ROUTINE ("SINKRON_KOREOGRAFI") disubmit, durasi simulasi 2.0 detik
     (merepresentasikan satu siklus sinkronisasi DSP/koreografi).
  2. Setelah jeda acak (0.3 - 1.5 detik, < durasi task #1), task P0_EMERGENCY
     ("STOP") disubmit -- ini mensimulasikan perintah suara darurat yang
     datang saat robot sedang menjalankan tugas rutin.
  3. Dicatat response_latency_sec milik task STOP di tiap mode.

Output:
  - hasil_uji_t_scheduler.xlsx  (data mentah tiap trial + ringkasan statistik)
  - scheduler_ttest_comparison.png (boxplot perbandingan)
  - Ringkasan tercetak di terminal: mean, std, t-statistic, p-value.
"""

import random
import time
import sys

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from adits_adaptive_scheduler import (
    AdaptivePreemptiveScheduler,
    StaticFIFOScheduler,
    Task,
    P0_EMERGENCY,
    P3_ROUTINE,
)

N_TRIALS = 30
ROUTINE_DURATION_SEC = 2.0
INJECTION_DELAY_RANGE = (0.3, 1.5)  # rentang kapan STOP datang, relatif ke mulainya routine
RANDOM_SEED = 9  # tetap, supaya skenario kedua mode persis sama (berpasangan)
ALPHA = 0.05


def run_trial(scheduler_cls, injection_delay: float) -> Task:
    """Jalankan satu skenario pada scheduler_cls, kembalikan task STOP-nya."""
    sch = scheduler_cls()
    routine = Task("routine", "SINKRON_KOREOGRAFI", P3_ROUTINE, duration_sec=ROUTINE_DURATION_SEC)
    sch.submit(routine)
    time.sleep(injection_delay)
    stop_cmd = Task("stop", "STOP", P0_EMERGENCY, duration_sec=0.05)
    sch.submit(stop_cmd)

    # Tunggu sampai task STOP benar-benar selesai diproses scheduler
    deadline = time.monotonic() + ROUTINE_DURATION_SEC + 2.0
    while stop_cmd.status not in ("DONE", "PREEMPTED", "CANCELLED") and time.monotonic() < deadline:
        time.sleep(0.005)

    sch.stop()
    return stop_cmd, routine


def main():
    random.seed(RANDOM_SEED)
    injection_delays = [random.uniform(*INJECTION_DELAY_RANGE) for _ in range(N_TRIALS)]

    rows = []
    print(f"Menjalankan {N_TRIALS} skenario berpasangan (Adaptif vs Statis)...")
    print(f"{'Trial':<6}{'Jeda Injeksi':<15}{'Latensi Adaptif':<18}{'Latensi Statis':<16}")
    print("-" * 55)

    for i, delay in enumerate(injection_delays, 1):
        stop_adaptive, routine_adaptive = run_trial(AdaptivePreemptiveScheduler, delay)
        time.sleep(0.05)  # jeda kecil antar trial, hindari interferensi thread sisa
        stop_static, routine_static = run_trial(StaticFIFOScheduler, delay)
        time.sleep(0.05)

        lat_adaptive = stop_adaptive.response_latency_sec
        lat_static = stop_static.response_latency_sec

        rows.append({
            "trial": i,
            "injection_delay_sec": round(delay, 4),
            "latency_adaptive_sec": lat_adaptive,
            "latency_static_sec": lat_static,
            "routine_status_adaptive": routine_adaptive.status,
            "routine_status_static": routine_static.status,
        })
        print(f"{i:<6}{delay:<15.3f}{lat_adaptive*1000:<18.1f}{lat_static*1000:<16.1f}")

    df = pd.DataFrame(rows)
    lat_a = df["latency_adaptive_sec"].values * 1000.0  # ms
    lat_s = df["latency_static_sec"].values * 1000.0    # ms

    mean_a, std_a = np.mean(lat_a), np.std(lat_a, ddof=1)
    mean_s, std_s = np.mean(lat_s), np.std(lat_s, ddof=1)

    t_stat, p_value = stats.ttest_rel(lat_s, lat_a)  # H1: statis > adaptif

    print("\n" + "=" * 70)
    print("HASIL UJI-T BERPASANGAN (scipy.stats.ttest_rel)")
    print("=" * 70)
    print(f"Mode Adaptif : mean = {mean_a:8.2f} ms | std = {std_a:7.2f} ms | n = {len(lat_a)}")
    print(f"Mode Statis  : mean = {mean_s:8.2f} ms | std = {std_s:7.2f} ms | n = {len(lat_s)}")
    print(f"Selisih rata-rata (Statis - Adaptif) : {mean_s - mean_a:8.2f} ms")
    print(f"t-statistic : {t_stat:.4f}")
    print(f"p-value     : {p_value:.6g}")
    if p_value < ALPHA:
        print(f"=> SIGNIFIKAN pada alpha={ALPHA} (p < {ALPHA}): mode adaptif terbukti "
              f"berbeda secara statistik dari mode statis untuk skenario ini.")
    else:
        print(f"=> TIDAK signifikan pada alpha={ALPHA} (p >= {ALPHA}). Laporkan apa adanya -- "
              f"jangan ubah skenario/parameter hanya supaya lolos ambang ini.")
    print("=" * 70)

    # --- simpan Excel ---
    summary_df = pd.DataFrame([{
        "mode": "Adaptive (Preemptive)", "mean_latency_ms": mean_a, "std_latency_ms": std_a, "n_trials": len(lat_a),
    }, {
        "mode": "Static (FIFO)", "mean_latency_ms": mean_s, "std_latency_ms": std_s, "n_trials": len(lat_s),
    }, {
        "mode": "Paired t-test", "t_statistic": t_stat, "p_value": p_value, "alpha": ALPHA,
    }])

    out_xlsx = "hasil_uji_t_scheduler.xlsx"
    with pd.ExcelWriter(out_xlsx) as writer:
        df.to_excel(writer, sheet_name="Data_Mentah_Per_Trial", index=False)
        summary_df.to_excel(writer, sheet_name="Ringkasan_Statistik", index=False)
    print(f"\nData tersimpan: {out_xlsx}")

    # --- boxplot ---
    fig, ax = plt.subplots(figsize=(6.5, 5))
    try:
        ax.boxplot([lat_a, lat_s], tick_labels=["Adaptif\n(Preemptive)", "Statis\n(FIFO)"],
                   patch_artist=True,
                   boxprops=dict(facecolor="#cfe3ff"),
                   medianprops=dict(color="#1f3a93", linewidth=2))
    except TypeError:
        # Kompatibilitas versi matplotlib lama yang masih pakai "labels"
        ax.boxplot([lat_a, lat_s], labels=["Adaptif\n(Preemptive)", "Statis\n(FIFO)"],
                   patch_artist=True,
                   boxprops=dict(facecolor="#cfe3ff"),
                   medianprops=dict(color="#1f3a93", linewidth=2))
    ax.set_ylabel("Latensi Respons Perintah Darurat (ms)")
    ax.set_title(f"Perbandingan Latensi: Adaptif vs Statis (n={N_TRIALS})\n"
                 f"t={t_stat:.2f}, p={p_value:.4g}")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    out_png = "scheduler_ttest_comparison.png"
    plt.savefig(out_png, dpi=200)
    print(f"Boxplot tersimpan: {out_png}")

    return df, summary_df


if __name__ == "__main__":
    main()
