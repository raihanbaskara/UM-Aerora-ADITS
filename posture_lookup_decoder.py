"""
================================================================================
POSTURE LOOKUP & DECODER UNTUK ROBOT TARI (ADITS / KRSTI)
================================================================================
Fungsi:
Menerjemahkan output 1 Kolom dari Random Forest menjadi:
1. Posisi Sudut Derajat Motor Servo Fisik (Kepala, Tangan Kanan, Tangan Kiri, Kaki).
2. Aksi Penyelamatan Diri (Safe Stop) jika musik tiba-tiba berhenti di detik tersebut.
================================================================================
"""

POSTURE_LOOKUP = {
    "P01_PEMBUKA__KEPALA_DEPAN__TANGAN_SELENDANG_BAWAH__KAKI_SIAP": {
        "babak": "Pembuka",
        "kepala": {"arah": "Hadap Depan Tegak", "servo_pan_tilt": [150, 150]},
        "tangan_kanan": {"pose": "Pegang Selendang Bawah", "servo_bahu_siku": [148, 152, 140]},
        "tangan_kiri": {"pose": "Pegang Selendang Bawah", "servo_bahu_siku": [148, 152, 140]},
        "kaki_badan": {"pose": "Mendak Diam Posisi Siap", "servo_lutut_engkel": [150, 150, 150]},
        "safe_stop_action": "Pertahankan posisi siap berdiri tegak seimbang"
    },
    "P02_PEMBUKA__KEPALA_SELEDET_KANAN__TANGAN_RENTANG_ANGKAT__KAKI_MENDAK": {
        "babak": "Pembuka",
        "kepala": {"arah": "Tengok Kanan Seledet", "servo_pan_tilt": [175, 145]},
        "tangan_kanan": {"pose": "Rentang Angkat Selendang Tinggi", "servo_bahu_siku": [215, 184, 175]},
        "tangan_kiri": {"pose": "Rentang Buka Selendang Rendah", "servo_bahu_siku": [129, 230, 184]},
        "kaki_badan": {"pose": "Mendak Rendah Badan Condong Kanan", "servo_lutut_engkel": [135, 165, 150]},
        "safe_stop_action": "Tahan rentang tangan dan stabilkan keseimbangan badan"
    },
    "P03_PAPESON__KEPALA_TENGOK_KIRI__TANGAN_KIBAS_TINGGI__LANGKAH_KIRI": {
        "babak": "Papeson",
        "kepala": {"arah": "Tengok Kiri Seledet", "servo_pan_tilt": [125, 155]},
        "tangan_kanan": {"pose": "Rentang Sedang", "servo_bahu_siku": [180, 160, 150]},
        "tangan_kiri": {"pose": "Kibas Selendang Tinggi", "servo_bahu_siku": [220, 190, 170]},
        "kaki_badan": {"pose": "Langkah Kaki Miring Kiri", "servo_lutut_engkel": [120, 90, 160]},
        "safe_stop_action": "Tutup langkah kaki menjadi rapat sejajar dan turunkan tangan"
    },
    "P04_PAPESON__KEPALA_SELEDET_KANAN__TANGAN_KIBAS_TINGGI__LANGKAH_KANAN": {
        "babak": "Papeson",
        "kepala": {"arah": "Hadap Depan Seledet Kanan", "servo_pan_tilt": [165, 145]},
        "tangan_kanan": {"pose": "Kibas Selendang Tinggi", "servo_bahu_siku": [220, 190, 170]},
        "tangan_kiri": {"pose": "Rentang Sedang", "servo_bahu_siku": [180, 160, 150]},
        "kaki_badan": {"pose": "Langkah Kaki Miring Kanan", "servo_lutut_engkel": [160, 90, 120]},
        "safe_stop_action": "Tutup langkah kaki menjadi rapat sejajar dan turunkan tangan"
    },
    "P05_PAPESON__KEPALA_DAGU_ANGKAT_KIRI__TANGAN_NGRUJI_DADA__MENDAK_KANAN": {
        "babak": "Papeson",
        "kepala": {"arah": "Tengok Kiri Dagu Angkat", "servo_pan_tilt": [130, 165]},
        "tangan_kanan": {"pose": "Tekuk Ngruji Depan Dada", "servo_bahu_siku": [145, 130, 200]},
        "tangan_kiri": {"pose": "Tekuk Ngruji Pinggang", "servo_bahu_siku": [110, 140, 150]},
        "kaki_badan": {"pose": "Mendak Diam Kaki Kanan Depan", "servo_lutut_engkel": [140, 160, 150]},
        "safe_stop_action": "Rapatkan kedua kaki dan pertahankan tangan di depan dada"
    },
    "P06_PAPESON__KEPALA_DAGU_ANGKAT_KANAN__TANGAN_NGRUJI_DADA__MENDAK_KIRI": {
        "babak": "Papeson",
        "kepala": {"arah": "Tengok Kanan Dagu Angkat", "servo_pan_tilt": [170, 165]},
        "tangan_kanan": {"pose": "Tekuk Ngruji Pinggang", "servo_bahu_siku": [110, 140, 150]},
        "tangan_kiri": {"pose": "Tekuk Ngruji Depan Dada", "servo_bahu_siku": [145, 130, 200]},
        "kaki_badan": {"pose": "Mendak Diam Kaki Kiri Depan", "servo_lutut_engkel": [160, 140, 150]},
        "safe_stop_action": "Rapatkan kedua kaki dan pertahankan tangan di depan dada"
    },
    "P07_PENGAWAK__KEPALA_LIUK_KIRI__TANGAN_NGEMBAT_ANGGUN__BADAN_MELIUK_KIRI": {
        "babak": "Pengawak",
        "kepala": {"arah": "Liuk Anggun Arah Kiri", "servo_pan_tilt": [135, 140]},
        "tangan_kanan": {"pose": "Ayunan Ngembat Lembut Atas", "servo_bahu_siku": [190, 175, 160]},
        "tangan_kiri": {"pose": "Ayunan Ngembat Lembut Bawah", "servo_bahu_siku": [130, 140, 150]},
        "kaki_badan": {"pose": "Badan Meliuk Kiri Mendak Anggun", "servo_lutut_engkel": [130, 170, 145]},
        "safe_stop_action": "Tegakkan badan perlahan dan turunkan ayunan tangan"
    },
    "P08_PENGAWAK__KEPALA_LIUK_KANAN__TANGAN_NGEMBAT_ANGGUN__BADAN_MELIUK_KANAN": {
        "babak": "Pengawak",
        "kepala": {"arah": "Liuk Anggun Arah Kanan", "servo_pan_tilt": [165, 140]},
        "tangan_kanan": {"pose": "Ayunan Ngembat Lembut Bawah", "servo_bahu_siku": [130, 140, 150]},
        "tangan_kiri": {"pose": "Ayunan Ngembat Lembut Atas", "servo_bahu_siku": [190, 175, 160]},
        "kaki_badan": {"pose": "Badan Meliuk Kanan Mendak Anggun", "servo_lutut_engkel": [170, 130, 155]},
        "safe_stop_action": "Tegakkan badan perlahan dan turunkan ayunan tangan"
    },
    "P09_PENGAWAK__KEPALA_SELEDET_KIRI__TANGAN_SILANG_DADA__CONDONG_KIRI": {
        "babak": "Pengawak",
        "kepala": {"arah": "Seledet Mata Tengok Kiri", "servo_pan_tilt": [120, 150]},
        "tangan_kanan": {"pose": "Silang Depan Dada", "servo_bahu_siku": [160, 120, 190]},
        "tangan_kiri": {"pose": "Silang Depan Perut", "servo_bahu_siku": [140, 130, 170]},
        "kaki_badan": {"pose": "Badan Condong Kiri Kaki Tegak", "servo_lutut_engkel": [140, 160, 150]},
        "safe_stop_action": "Buka silangan tangan ke samping dan luruskan badan"
    },
    "P10_PENGAWAK__KEPALA_SELEDET_KANAN__TANGAN_BUKA_SAMPING__CONDONG_KANAN": {
        "babak": "Pengawak",
        "kepala": {"arah": "Seledet Mata Tengok Kanan", "servo_pan_tilt": [180, 150]},
        "tangan_kanan": {"pose": "Buka ke Samping Kanan", "servo_bahu_siku": [200, 170, 150]},
        "tangan_kiri": {"pose": "Buka ke Samping Kiri", "servo_bahu_siku": [200, 170, 150]},
        "kaki_badan": {"pose": "Badan Condong Kanan Kaki Tegak", "servo_lutut_engkel": [160, 140, 150]},
        "safe_stop_action": "Turunkan tangan ke samping paha secara bertahap"
    },
    "P11_MEPUKPUK__KEPALA_PATUK_KIRI__TANGAN_MEPUKPUK_CEPAT__GETAR_PINGGUL": {
        "babak": "Mepukpuk",
        "kepala": {"arah": "Patuk Cepat ke Kiri", "servo_pan_tilt": [130, 170]},
        "tangan_kanan": {"pose": "Gerak Cepat Mepukpuk Atas", "servo_bahu_siku": [170, 200, 160]},
        "tangan_kiri": {"pose": "Gerak Cepat Mepukpuk Bawah", "servo_bahu_siku": [150, 140, 180]},
        "kaki_badan": {"pose": "Mendak Getar Pinggul", "servo_lutut_engkel": [145, 155, 150]},
        "safe_stop_action": "Hentikan getaran seketika dan kunci posisi mendak stabil"
    },
    "P12_MEPUKPUK__KEPALA_PATUK_KANAN__TANGAN_MEPUKPUK_CEPAT__GETAR_PINGGUL": {
        "babak": "Mepukpuk",
        "kepala": {"arah": "Patuk Cepat ke Kanan", "servo_pan_tilt": [170, 170]},
        "tangan_kanan": {"pose": "Gerak Cepat Mepukpuk Bawah", "servo_bahu_siku": [150, 140, 180]},
        "tangan_kiri": {"pose": "Gerak Cepat Mepukpuk Atas", "servo_bahu_siku": [170, 200, 160]},
        "kaki_badan": {"pose": "Mendak Getar Pinggul", "servo_lutut_engkel": [155, 145, 150]},
        "safe_stop_action": "Hentikan getaran seketika dan kunci posisi mendak stabil"
    },
    "P13_PEKAAD__KEPALA_HADAP_DEPAN__TANGAN_LURUS_DIAGONAL__LANGKAH_CEPAT_KANAN": {
        "babak": "Pekaad",
        "kepala": {"arah": "Hadap Depan Dagu Tinggi", "servo_pan_tilt": [150, 160]},
        "tangan_kanan": {"pose": "Lurus Diagonal Atas", "servo_bahu_siku": [225, 180, 150]},
        "tangan_kiri": {"pose": "Tekuk Sudut 90 Pinggang", "servo_bahu_siku": [120, 150, 160]},
        "kaki_badan": {"pose": "Langkah Cepat Kaki Kanan", "servo_lutut_engkel": [170, 110, 140]},
        "safe_stop_action": "Segera injak kaki ke lantai dan tahan langkah agar tidak jatuh"
    },
    "P14_PEKAAD__KEPALA_TENGOK_KIRI__TANGAN_LURUS_DIAGONAL__LANGKAH_CEPAT_KIRI": {
        "babak": "Pekaad",
        "kepala": {"arah": "Tengok Kiri Ekspresi Tegas", "servo_pan_tilt": [120, 160]},
        "tangan_kanan": {"pose": "Tekuk Sudut 90 Pinggang", "servo_bahu_siku": [120, 150, 160]},
        "tangan_kiri": {"pose": "Lurus Diagonal Atas", "servo_bahu_siku": [225, 180, 150]},
        "kaki_badan": {"pose": "Langkah Cepat Kaki Kiri", "servo_lutut_engkel": [110, 170, 160]},
        "safe_stop_action": "Segera injak kaki ke lantai dan tahan langkah agar tidak jatuh"
    },
    "P15_PENUTUP__KEPALA_MERUNDUK_HORMAT__TANGAN_SEMBAH_DADA__LUTUT_TEKUK": {
        "babak": "Salam Penutup",
        "kepala": {"arah": "Merunduk Tunduk Hormat", "servo_pan_tilt": [150, 120]},
        "tangan_kanan": {"pose": "Sembah Rapat Depan Dada", "servo_bahu_siku": [150, 130, 210]},
        "tangan_kiri": {"pose": "Sembah Rapat Depan Dada", "servo_bahu_siku": [150, 130, 210]},
        "kaki_badan": {"pose": "Merunduk Lutut Tekuk Penutup", "servo_lutut_engkel": [120, 120, 150]},
        "safe_stop_action": "Pertahankan pose sembah hormat sempurna hingga robot dimatikan"
    }
}


def decode_movement_state(state_name: str) -> dict:
    """Menerjemahkan 1 nama string state menjadi kamus detail posisi robot."""
    return POSTURE_LOOKUP.get(state_name, {
        "babak": "Unknown",
        "kepala": {"arah": "Default", "servo_pan_tilt": [150, 150]},
        "tangan_kanan": {"pose": "Default", "servo_bahu_siku": [150, 150, 150]},
        "tangan_kiri": {"pose": "Default", "servo_bahu_siku": [150, 150, 150]},
        "kaki_badan": {"pose": "Default", "servo_lutut_engkel": [150, 150, 150]},
        "safe_stop_action": "Kembali ke posisi diam tegak"
    })


def get_posture_detail(name: str) -> dict:
    """Menerjemahkan nama babak tari atau nama state ke dalam rincian string pose & sudut servo."""
    # Cari di POSTURE_LOOKUP berdasarkan kecocokan babak atau prefix
    matched = None
    for k, v in POSTURE_LOOKUP.items():
        if name in k or (isinstance(v, dict) and v.get("babak", "").lower() in name.lower()):
            matched = v
            break

    if not matched:
        # Default posture
        return {
            "kepala": "Hadap Depan Tegak",
            "sudut_kepala": [150, 150],
            "tangan_kanan": "Pegang Selendang Bawah",
            "sudut_tangan_kanan": [148, 152, 140],
            "tangan_kiri": "Pegang Selendang Bawah",
            "sudut_tangan_kiri": [148, 152, 140],
            "kaki_badan": "Mendak Diam Posisi Siap",
            "sudut_kaki": [150, 150, 150],
            "safe_action": "Pertahankan posisi siap berdiri tegak seimbang"
        }

    return {
        "kepala": matched["kepala"]["arah"],
        "sudut_kepala": matched["kepala"]["servo_pan_tilt"],
        "tangan_kanan": matched["tangan_kanan"]["pose"],
        "sudut_tangan_kanan": matched["tangan_kanan"]["servo_bahu_siku"],
        "tangan_kiri": matched["tangan_kiri"]["pose"],
        "sudut_tangan_kiri": matched["tangan_kiri"]["servo_bahu_siku"],
        "kaki_badan": matched["kaki_badan"]["pose"],
        "sudut_kaki": matched["kaki_badan"]["servo_lutut_engkel"],
        "safe_action": matched["safe_stop_action"]
    }


if __name__ == "__main__":
    contoh_state = "P03_PAPESON__KEPALA_TENGOK_KIRI__TANGAN_KIBAS_TINGGI__LANGKAH_KIRI"
    print("Contoh Decode 1 Kolom:")
    hasil = decode_movement_state(contoh_state)
    import pprint
    pprint.pprint(hasil)
