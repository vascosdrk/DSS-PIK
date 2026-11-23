"""
Authoritative Decision Engine for CEWS BMKG Kepulauan Riau (PDKM & PDCHT)
Peraturan BMKG No. 9 Tahun 2019 / Penyempurnaan Operasional DSS-PIK

Level Mapping:
  Level 0: HIJAU (Aman / Tidak Ada Peringatan)
  Level 1: WASPADA (Kuning)
  Level 2: SIAGA (Oranye)
  Level 3: AWAS (Merah)

Prinsip Utama:
- Evaluasi independen untuk setiap indikator.
- status_pdkm = max(level_hth, level_prob, level_spi)
- status_pdcht = max(level_dasarian, level_bulanan)
- Ambang batas ketat (> 70.0% untuk Pb20 PDKM; > 50.0% untuk probabilitas PDCHT)
- Explicit missing & partial handling (null/NaN tidak pernah diubah menjadi nol)
"""

from typing import Dict, Any, List, Optional, Tuple
import math

LEVEL_TO_STATUS = {
    0: "NORMAL",   # HIJAU / AMAN
    1: "WASPADA",
    2: "SIAGA",
    3: "AWAS"
}

STATUS_TO_LEVEL = {
    "NORMAL": 0,
    "AMAN": 0,
    "HIJAU": 0,
    "WASPADA": 1,
    "SIAGA": 2,
    "AWAS": 3,
    "INCOMPLETE": 0,
    "TIDAK_LENGKAP": 0
}

STATUS_TO_COLOR = {
    "NORMAL": "Hijau",
    "AMAN": "Hijau",
    "HIJAU": "Hijau",
    "WASPADA": "Kuning",
    "SIAGA": "Oranye",
    "AWAS": "Merah",
    "INCOMPLETE": "Abu-abu",
    "TIDAK_LENGKAP": "Abu-abu"
}


def evaluate_hth_indicator(hth_days: Optional[int], hth_uncertain: bool = False) -> Dict[str, Any]:
    """
    Evaluasi HTH (Hari Tanpa Hujan):
      HTH >= 61 hari -> AWAS, level 3
      31 <= HTH < 61 hari -> SIAGA, level 2
      21 <= HTH < 31 hari -> WASPADA, level 1
      HTH < 21 hari -> HIJAU, level 0
    """
    if hth_days is None:
        return {
            "indicator": "HTH",
            "level": 0,
            "status": "NORMAL",
            "value": None,
            "valid": False,
            "triggered": False,
            "reason": "Data HTH tidak tersedia",
            "uncertain": hth_uncertain
        }

    val = int(hth_days)
    if val >= 61:
        lvl = 3
        st = "AWAS"
        trig = True
        r = f"HTH {val} hari (>= 61 hari)"
    elif val >= 31:
        lvl = 2
        st = "SIAGA"
        trig = True
        r = f"HTH {val} hari (31–60 hari)"
    elif val >= 21:
        lvl = 1
        st = "WASPADA"
        trig = True
        r = f"HTH {val} hari (21–30 hari)"
    else:
        lvl = 0
        st = "NORMAL"
        trig = False
        r = f"HTH {val} hari (< 21 hari, aman)"

    if hth_uncertain:
        r += " [Data observasi memiliki ketidakpastian/missing]"
        if val < 21:
            return {
                "indicator": "HTH",
                "level": 0,
                "status": "UNCERTAIN",
                "value": val,
                "valid": False,
                "triggered": False,
                "reason": f"HTH tidak dapat dipastikan ({val} hari terhitung, terdapat data observasi hilang/rusak/ambigu)",
                "uncertain": True
            }

    return {
        "indicator": "HTH",
        "level": lvl,
        "status": st,
        "value": val,
        "valid": True,
        "triggered": trig,
        "reason": r,
        "uncertain": hth_uncertain
    }


def evaluate_prob_low_rain_indicator(pb20: Optional[float]) -> Dict[str, Any]:
    """
    Evaluasi Probabilitas Curah Hujan Rendah:
      forecast_rainfall_mm < 20 AND probability_percent > 70
      Diwujudkan via pb20 = P(CH < 20 mm/dasarian) > 70%
      Jika terpenuhi -> WASPADA, level 1 (Probabilitas tidak boleh langsung menghasilkan SIAGA atau AWAS).
      Jika pb20 <= 70% -> HIJAU, level 0.
    """
    if pb20 is None:
        return {
            "indicator": "Prob_LowRain",
            "level": 0,
            "status": "NORMAL",
            "value": None,
            "valid": False,
            "triggered": False,
            "reason": "Data probabilitas CH rendah (pb20) tidak tersedia"
        }

    val = float(pb20)
    if val > 70.0:
        lvl = 1
        st = "WASPADA"
        trig = True
        r = f"Peluang CH < 20 mm sebesar {val:.1f}% (> 70.0%)"
    else:
        lvl = 0
        st = "NORMAL"
        trig = False
        r = f"Peluang CH < 20 mm sebesar {val:.1f}% (<= 70.0%, normal)"

    return {
        "indicator": "Prob_LowRain",
        "level": lvl,
        "status": st,
        "value": val,
        "valid": True,
        "triggered": trig,
        "reason": r
    }


def evaluate_spi_indicator(spi_val: Optional[float]) -> Dict[str, Any]:
    """
    Evaluasi SPI (Standardized Precipitation Index):
      SPI <= -2.00: AWAS, level 3
      -2.00 < SPI <= -1.50: SIAGA, level 2
      -1.50 < SPI <= -1.00: WASPADA, level 1
      SPI > -1.00: HIJAU, level 0
    """
    if spi_val is None:
        return {
            "indicator": "SPI",
            "level": 0,
            "status": "NORMAL",
            "value": None,
            "valid": False,
            "triggered": False,
            "reason": "Data SPI 90D tidak tersedia"
        }

    val = float(spi_val)
    if val <= -2.00:
        lvl = 3
        st = "AWAS"
        trig = True
        r = f"SPI 90D {val:.2f} (<= -2.00, kering ekstrem)"
    elif val <= -1.50:
        lvl = 2
        st = "SIAGA"
        trig = True
        r = f"SPI 90D {val:.2f} (-1.99 s/d -1.50, sangat kering)"
    elif val <= -1.00:
        lvl = 1
        st = "WASPADA"
        trig = True
        r = f"SPI 90D {val:.2f} (-1.49 s/d -1.00, kering)"
    else:
        lvl = 0
        st = "NORMAL"
        trig = False
        r = f"SPI 90D {val:.2f} (> -1.00, normal/basah)"

    return {
        "indicator": "SPI",
        "level": lvl,
        "status": st,
        "value": val,
        "valid": True,
        "triggered": trig,
        "reason": r
    }


def evaluate_pdkm_full(
    hth_days: Optional[int],
    pb20: Optional[float],
    spi_val: Optional[float],
    hth_uncertain: bool = False,
    is_arg: bool = False,
    target_label: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluasi Lengkap PDKM (Peringatan Dini Kekeringan Meteorologis).
    Setiap indikator dievaluasi secara independen:
      status_pdkm = max(level_hth, level_prob, level_spi)
    Untuk stasiun ARG: SPI dan Prob tidak berlaku, evaluasi hanya berbasis HTH.
    """
    hth_res = evaluate_hth_indicator(hth_days, hth_uncertain)
    prob_res = evaluate_prob_low_rain_indicator(None if is_arg else pb20)
    spi_res = evaluate_spi_indicator(None if is_arg else spi_val)

    if is_arg:
        # ARG: only HTH
        max_level = hth_res["level"]
        complete = hth_res["valid"]
        missing_inputs = [] if hth_res["valid"] else ["HTH"]
        all_indicators = [hth_res]
    else:
        max_level = max(hth_res["level"], prob_res["level"], spi_res["level"])
        missing_inputs = []
        if not hth_res["valid"]: missing_inputs.append("HTH")
        if not prob_res["valid"]: missing_inputs.append("Prob_LowRain(pb20)")
        if not spi_res["valid"]: missing_inputs.append("SPI_90D")
        complete = len(missing_inputs) == 0
        all_indicators = [hth_res, prob_res, spi_res]

    status = LEVEL_TO_STATUS[max_level]
    triggered = [ind for ind in all_indicators if ind["triggered"]]

    # Build concise and descriptive reasons
    target_str = f" untuk {target_label}" if target_label else ""
    if triggered:
        trig_reasons = [t["reason"] for t in triggered]
        reason_text = f"PDKM {status}{target_str}: " + "; ".join(trig_reasons)
        if not complete:
            reason_text += f" (Evaluasi Parsial: input {', '.join(missing_inputs)} belum tersedia)"
    else:
        if not complete:
            # No trigger proven, but required inputs missing -> cannot blindly assign safe AMAN/HIJAU!
            status = "INCOMPLETE"
            reason_text = f"PDKM Data Tidak Lengkap{target_str}: Tidak ada pemicu pada data tersedia, namun input {', '.join(missing_inputs)} belum tersedia"
        else:
            reason_text = f"PDKM AMAN{target_str}: Seluruh parameter kekeringan dalam batas normal"

    return {
        "status": status,
        "level": max_level,
        "color": STATUS_TO_COLOR[status],
        "triggered_indicators": [t["indicator"] for t in triggered],
        "reasons": reason_text,
        "input_values": {
            "hth_days": hth_days,
            "pb20": pb20,
            "spi": spi_val
        },
        "evaluation_complete": complete,
        "missing_inputs": missing_inputs,
        "details": {
            "hth": hth_res,
            "prob_low_rain": prob_res,
            "spi": spi_res
        }
    }


def evaluate_pdcht_dasarian(
    pa150: Optional[float],
    pa200: Optional[float],
    pa300: Optional[float]
) -> Dict[str, Any]:
    """
    PDCHT Dasarian:
      pa300 > 50% -> AWAS, level 3
      pa200 > 50% -> SIAGA, level 2
      pa150 > 50% -> WASPADA, level 1
      Else -> HIJAU, level 0
    Ambang ketat > 50.0%
    """
    th = 50.0
    p150 = float(pa150) if pa150 is not None else None
    p200 = float(pa200) if pa200 is not None else None
    p300 = float(pa300) if pa300 is not None else None

    trig = []
    lvl = 0
    if p300 is not None and p300 > th:
        lvl = 3
        trig.append(f"P(CH Dasarian > 300 mm) = {p300:.1f}% (> 50%)")
    elif p200 is not None and p200 > th:
        lvl = 2
        trig.append(f"P(CH Dasarian > 200 mm) = {p200:.1f}% (> 50%)")
    elif p150 is not None and p150 > th:
        lvl = 1
        trig.append(f"P(CH Dasarian > 150 mm) = {p150:.1f}% (> 50%)")

    valid = (p150 is not None or p200 is not None or p300 is not None)
    return {
        "level": lvl,
        "status": LEVEL_TO_STATUS[lvl],
        "triggered": len(trig) > 0,
        "reasons": trig,
        "valid": valid
    }


def evaluate_pdcht_monthly(
    pm300: Optional[float],
    pm400: Optional[float],
    pm500: Optional[float]
) -> Dict[str, Any]:
    """
    PDCHT Bulanan:
      prob_gt500 > 50% -> AWAS, level 3
      prob_gt400 > 50% -> SIAGA, level 2
      prob_gt300 > 50% -> WASPADA, level 1
      Else -> HIJAU, level 0
    Ambang ketat > 50.0%
    """
    th = 50.0
    p300 = float(pm300) if pm300 is not None else None
    p400 = float(pm400) if pm400 is not None else None
    p500 = float(pm500) if pm500 is not None else None

    trig = []
    lvl = 0
    if p500 is not None and p500 > th:
        lvl = 3
        trig.append(f"P(CH Bulanan > 500 mm) = {p500:.1f}% (> 50%)")
    elif p400 is not None and p400 > th:
        lvl = 2
        trig.append(f"P(CH Bulanan > 400 mm) = {p400:.1f}% (> 50%)")
    elif p300 is not None and p300 > th:
        lvl = 1
        trig.append(f"P(CH Bulanan > 300 mm) = {p300:.1f}% (> 50%)")

    valid = (p300 is not None or p400 is not None or p500 is not None)
    return {
        "level": lvl,
        "status": LEVEL_TO_STATUS[lvl],
        "triggered": len(trig) > 0,
        "reasons": trig,
        "valid": valid
    }


def evaluate_pdcht_full(
    pa150: Optional[float] = None,
    pa200: Optional[float] = None,
    pa300: Optional[float] = None,
    pm300: Optional[float] = None,
    pm400: Optional[float] = None,
    pm500: Optional[float] = None,
    is_arg: bool = False,
    target_label: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluasi Lengkap PDCHT:
      status_pdcht = max(level_dasarian, level_bulanan)
    """
    if is_arg:
        return {
            "status": "NORMAL",
            "level": 0,
            "color": "Hijau",
            "triggered_indicators": [],
            "reasons": "PDCHT tidak berlaku untuk stasiun ARG",
            "input_values": {},
            "evaluation_complete": True,
            "missing_inputs": []
        }

    das_res = evaluate_pdcht_dasarian(pa150, pa200, pa300)
    month_res = evaluate_pdcht_monthly(pm300, pm400, pm500)

    max_lvl = max(das_res["level"], month_res["level"])
    status = LEVEL_TO_STATUS[max_lvl]

    all_trigs = das_res["reasons"] + month_res["reasons"]
    target_str = f" untuk {target_label}" if target_label else ""

    missing = []
    if not das_res["valid"]: missing.append("Prob_Dasarian")
    if not month_res["valid"]: missing.append("Prob_Bulanan")
    complete = len(missing) == 0

    if all_trigs:
        r_text = f"PDCHT {status}{target_str}: " + "; ".join(all_trigs)
        if not complete:
            r_text += f" (Evaluasi Parsial: input {', '.join(missing)} belum tersedia)"
    else:
        if not complete:
            status = "INCOMPLETE"
            r_text = f"PDCHT Data Tidak Lengkap{target_str}: Parameter curah hujan tinggi ({', '.join(missing)}) tidak tersedia"
        else:
            r_text = f"PDCHT AMAN{target_str}: Peluang curah hujan tinggi berada di bawah ambang 50%"

    return {
        "status": status,
        "level": max_lvl,
        "color": STATUS_TO_COLOR[status],
        "triggered_indicators": all_trigs,
        "reasons": r_text,
        "input_values": {
            "pa150": pa150, "pa200": pa200, "pa300": pa300,
            "pm300": pm300, "pm400": pm400, "pm500": pm500
        },
        "evaluation_complete": complete,
        "missing_inputs": missing
    }


def arbitrate_final_synthesis(
    pdkm_result: Dict[str, Any],
    pdcht_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Sintesis Status Akhir DSS-PIK:
    PDKM dan PDCHT tetap dipertahankan secara terpisah.
    Status sintesis akhir mengambil level tertinggi dengan label hazard transparan.
    Jika tidak ada peringatan (level 0) namun evaluasi belum lengkap, status ditandai INCOMPLETE.
    """
    lvl_d = pdkm_result["level"]
    lvl_r = pdcht_result["level"]
    is_complete = pdkm_result["evaluation_complete"] and pdcht_result["evaluation_complete"]

    if lvl_d > 0 and lvl_r > 0:
        # Both hazards active: keep both, overall level = highest
        final_level = max(lvl_d, lvl_r)
        final_status = LEVEL_TO_STATUS[final_level]
        hazard = "MULTI_HAZARD"
        reason = f"MULTI-HAZARD ({final_status}): PDKM {pdkm_result['status']} [{pdkm_result['reasons']}] & PDCHT {pdcht_result['status']} [{pdcht_result['reasons']}]"
        multi_hazard = True
    elif lvl_d > lvl_r:
        final_level = lvl_d
        final_status = pdkm_result["status"]
        hazard = "DROUGHT"
        reason = pdkm_result["reasons"]
        multi_hazard = False
    elif lvl_r > lvl_d:
        final_level = lvl_r
        final_status = pdcht_result["status"]
        hazard = "HEAVY_RAIN"
        reason = pdcht_result["reasons"]
        multi_hazard = False
    elif lvl_d > 0 and lvl_d == lvl_r:
        # Tie at warning level (e.g. both WASPADA)
        final_level = lvl_d
        final_status = pdkm_result["status"]
        hazard = "MULTI_HAZARD"
        reason = f"MULTI-HAZARD ({final_status}): PDKM [{pdkm_result['reasons']}] & PDCHT [{pdcht_result['reasons']}]"
        multi_hazard = True
    else:
        final_level = 0
        multi_hazard = False
        if not is_complete:
            final_status = "INCOMPLETE"
            hazard = "INCOMPLETE"
            reason = f"Evaluasi belum lengkap: {pdkm_result['reasons']} | {pdcht_result['reasons']}"
        else:
            final_status = "NORMAL"
            hazard = "NORMAL"
            reason = "Seluruh indikator kekeringan dan curah hujan tinggi dalam batas normal"

    return {
        "final_status": final_status,
        "final_level": final_level,
        "color": STATUS_TO_COLOR[final_status],
        "hazard_type": hazard,
        "reason": reason,
        "multi_hazard": multi_hazard,
        "pdkm_status": pdkm_result["status"],
        "pdkm_level": pdkm_result["level"],
        "pdcht_status": pdcht_result["status"],
        "pdcht_level": pdcht_result["level"],
        "evaluation_complete": is_complete
    }
