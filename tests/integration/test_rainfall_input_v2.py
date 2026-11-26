"""
tests/integration/test_rainfall_input_v2.py
Comprehensive test suite for DSS-PIK Rainfall Data Input Module V2:
- 10.1 Four Raw Excel Parsers (Karimun, Lingga, Natuna, Anambas) + Partial-Period Import
- 10.2 Region-Aware Symbol Normalization
- 10.3 Multi-File Batch Detection, Mixed Raw+Legacy, Corrupt/Unknown, Mapping Wizard Profile Persistence
- 10.4 Multi-Date Manual Input (single date, dasarian, blank skip, conflict, correction)
- 10.5 Legacy Regression (Batam, Bintan XLSM, Tanjungpinang)
- 10.6 MariaDB Transactional Commit, Audit Log, History & Batch Rollback (isolated on 2099-10-* dates & cleaned up)
"""

import io
from pathlib import Path
import openpyxl
import pytest

from backend.database import get_db
from backend.ingestion_service import cancel_ingestion_batch
from backend.rainfall_ingestion_v2 import (
    commit_batch_session,
    commit_manual_input_v2,
    create_detect_batch_session,
    detect_rainfall_template,
    format_standard_display,
    get_regencies_metadata,
    get_regency_stations,
    list_template_profiles,
    normalize_rainfall_value,
    preview_batch_session,
    preview_manual_input_v2,
    save_template_profile,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _wb_to_bytes(wb: openpyxl.Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _make_karimun_raw_wb(partial_days=(21, 27)) -> bytes:
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Lembar1"
    wb.create_sheet("Lembar2")  # Empty second sheet

    # Block 1: Stamet Raja Haji Abdullah (21020302A)
    ws1.append(["No. Stasiun Hujan", ":", "21020302A"])
    ws1.append(["Nama Pos", ":", "Stamet Raja Haji Abdullah"])
    ws1.append(["Tanggal", "CH (mm)"])
    for d in range(partial_days[0], partial_days[1] + 1):
        val = "TTU" if d == 22 else (0 if d == 23 else (12.5 if d == 24 else None if d == 25 else 5.0))
        ws1.append([d, val])
    ws1.append(["Jumlah", 999])  # Summary row — must be ignored

    # Block 2: Kapling Tebing (21020301A)
    ws1.append(["No. Stasiun Hujan", ":", "21020301A"])
    ws1.append(["Nama Pos", ":", "Kapling Tebing"])
    ws1.append(["Tanggal", "CH (mm)"])
    for d in range(partial_days[0], partial_days[1] + 1):
        ws1.append([d, 3.2 if d != 26 else "UNKNOWN_SYM"])
    ws1.append(["Rata-rata", 1.5])
    return _wb_to_bytes(wb)


def _make_lingga_raw_wb() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SEP"  # Deliberate conflict with title OKTOBER 2026
    ws["B1"] = "DATA CURAH HUJAN KABUPATEN LINGGA OKTOBER 2026"
    ws.merge_cells("B1:K1")
    ws["B3"] = "Tanggal"
    stations = [
        "Dabo Singkep", "Dinas Pertanian Lingga", "Bukit Langkap", "Resun",
        "Duara", "Bukit Belah Raya", "Sungai Buluh", "ARG Singkep",
    ]
    for idx, st in enumerate(stations, start=3):
        ws.cell(row=3, column=idx, value=st)
    ws.cell(row=3, column=11, value="Dasarian")

    # Rows for days 1..5
    ws.cell(row=4, column=2, value=1); ws.cell(row=4, column=3, value=0); ws.cell(row=4, column=4, value="-"); ws.cell(row=4, column=5, value=8888); ws.cell(row=4, column=6, value=9999); ws.cell(row=4, column=11, value="Das I")
    ws.cell(row=5, column=2, value=2); ws.cell(row=5, column=3, value=14.5); ws.cell(row=5, column=4, value=None); ws.cell(row=5, column=11, value="Das I")
    # Bottom accumulation table — must be ignored
    ws.cell(row=7, column=2, value="Jumlah"); ws.cell(row=7, column=3, value=14.5)
    return _wb_to_bytes(wb)


def _make_natuna_raw_wb() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2610"
    header = ["Nama Pos"] + list(range(1, 32)) + ["Akumulasi", "Hari Hujan"]
    ws.append(header)
    row1 = ["Stamet Ranai Natuna"] + [None] * 31 + [150.0, 10]
    row1[1] = 0      # Day 1 -> OBSERVED_ZERO
    row1[2] = "-"    # Day 2 -> MISSING
    row1[3] = 22.4   # Day 3 -> OBSERVED_VALID
    row1[4] = "??"   # Day 4 -> UNRECOGNIZED
    ws.append(row1)
    row2 = ["Padang Meliso"] + [None] * 31 + [50.0, 5]
    row2[1] = 8.0
    ws.append(row2)
    return _wb_to_bytes(wb)


def _make_anambas_raw_wb() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NOV"
    ws["A1"] = "LAPORAN CH KEPULAUAN ANAMBAS TAHUN 2026"
    header = ["No", "Kode Pos", "Nama Pos", "Kec", "Kab", "Prov"] + list(range(1, 31)) + ["Das I", "Das II", "Das III", "Bulanan"]
    ws.append(header)
    # 1 station with code, 2 stations without code (matched by name)
    r1 = [1, "21050101A", "Stamet Tarempa", "Siantan", "Anambas", "Kepri"] + [None] * 30 + [10, 20, 30, 60]
    r1[6] = "-"      # Day 1 -> OBSERVED_ZERO
    r1[7] = 0        # Day 2 -> TTU (Anambas rule!)
    r1[8] = 9999     # Day 3 -> MISSING
    r1[9] = 18.5     # Day 4 -> OBSERVED_VALID
    ws.append(r1)

    r2 = [2, "", "Langir", "Palmatak", "Anambas", "Kepri"] + [None] * 30 + [5, 0, 0, 5]
    r2[6] = 4.5
    ws.append(r2)

    r3 = [3, None, "UPT Benih Pertanian", "Jemaja", "Anambas", "Kepri"] + [None] * 30 + [0, 0, 0, 0]
    r3[6] = "-"
    ws.append(r3)
    return _wb_to_bytes(wb)


def _make_unknown_custom_wb() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CustomSheet"
    ws.append(["Hari_Custom", "Curah_Custom"])
    ws.append([1, 7.5])
    ws.append([2, "TTU"])
    ws.append([3, None])
    return _wb_to_bytes(wb)


# ==============================================================================
# 10.2 NORMALIZATION TESTS (COMPLETE SECTION G STANDARDIZATION MATRIX)
# ==============================================================================
def test_region_symbol_normalization():
    def _std(val, prof, blank_as_missing=False):
        rf, st, _ = normalize_rainfall_value(val, prof, blank_as_missing=blank_as_missing)
        return rf, st, format_standard_display(rf, st)

    # Section G required matrix:
    assert _std(0, "RAW_KARIMUN") == (0.0, "OBSERVED_ZERO", "-")
    assert _std(0, "RAW_LINGGA") == (0.0, "OBSERVED_ZERO", "-")
    assert _std(0, "RAW_NATUNA") == (0.0, "TTU", "TTU")
    assert _std(0, "RAW_ANAMBAS") == (0.0, "TTU", "TTU")

    for prof in ("RAW_KARIMUN", "RAW_LINGGA", "RAW_NATUNA", "RAW_ANAMBAS", "LEGACY_STANDARD", "MANUAL_CANONICAL"):
        assert _std("TTU", prof) == (0.0, "TTU", "TTU")
        assert _std(9999, prof) == (None, "MISSING", "9999")
        assert _std(12.5, prof) == (12.5, "OBSERVED_VALID", "12.5")
        assert _std(None, prof, blank_as_missing=True) == (None, "MISSING", "9999")
        assert _std("", prof, blank_as_missing=True) == (None, "MISSING", "9999")

    assert _std("-", "LEGACY_STANDARD") == (0.0, "OBSERVED_ZERO", "-")
    assert _std("-", "RAW_ANAMBAS") == (0.0, "OBSERVED_ZERO", "-")
    assert _std("-", "RAW_LINGGA") == (None, "MISSING", "9999")
    assert _std("-", "RAW_NATUNA") == (None, "MISSING", "9999")
    assert _std(8888, "RAW_LINGGA") == (0.0, "TTU", "TTU")

    # Safety guards
    assert normalize_rainfall_value("", "MANUAL_CANONICAL", blank_as_missing=False)[:2] == (None, "NOT_PROVIDED")
    assert normalize_rainfall_value(-5, "RAW_KARIMUN")[:2] == (-5.0, "INVALID")
    assert normalize_rainfall_value("ABC", "RAW_KARIMUN")[:2] == (None, "UNRECOGNIZED")
    assert normalize_rainfall_value("XYZ", "RAW_NATUNA")[:2] == (None, "UNRECOGNIZED")


# ==============================================================================
# 10.1 FOUR RAW PARSERS + PARTIAL-PERIOD IMPORT
# ==============================================================================
def test_karimun_raw_detect_and_partial_period():
    raw = _make_karimun_raw_wb(partial_days=(21, 27))
    det = detect_rainfall_template(raw, "random_name_01.xlsx", "KARIMUN")
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == "RAW_KARIMUN"
    assert det["period_confirmation_required"] is True

    sess = create_detect_batch_session("KARIMUN", [("karimun_d3.xlsx", raw)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "year": 2099, "month": 10, "dasarian": 3}],
    )
    # Days 21..27 are present in file -> Day 25 blank cell becomes MISSING ('9999');
    # Days 28..31 are NOT present in file -> NO records created!
    b1 = {r["observation_date"]: r for r in prev["preview_rows"] if r["station_id"] == "21020302A"}
    assert "2099-10-28" not in b1
    assert len(b1) == 7
    assert b1["2099-10-22"]["display_value"] == "TTU"
    assert b1["2099-10-23"]["display_value"] == "-"
    assert b1["2099-10-24"]["display_value"] == "12.5"
    assert b1["2099-10-25"]["display_value"] == "9999"
    assert b1["2099-10-25"]["obs_status"] == "MISSING"
    assert prev["counts"]["ttu"] == 1
    assert prev["counts"]["unrecognized"] == 1


def test_lingga_raw_detect_conflict_and_parse():
    raw = _make_lingga_raw_wb()
    det = detect_rainfall_template(raw, "dabo_upload.xlsx", "LINGGA")
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == "RAW_LINGGA"
    assert any("SEP" in c and "Oktober" in c for c in det["metadata_conflicts"])

    sess = create_detect_batch_session("LINGGA", [("dabo_upload.xlsx", raw)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "year": 2099, "month": 10, "dasarian": 1}],
    )
    by_key = {(r["station_id"], r["observation_date"]): r for r in prev["preview_rows"]}
    assert by_key[("21040101A", "2099-10-01")]["display_value"] == "-"
    assert by_key[("21040203A", "2099-10-01")]["display_value"] == "9999"
    assert by_key[("21040201A", "2099-10-01")]["display_value"] == "TTU"
    assert by_key[("21040202A", "2099-10-01")]["display_value"] == "9999"
    # Blank cell on explicit date row (day 2) -> MISSING ('9999')
    assert by_key[("21040203A", "2099-10-02")]["display_value"] == "9999"
    # Absent date (day 6..10 not in file) -> NO record created
    assert ("21040101A", "2099-10-06") not in by_key


def test_natuna_raw_detect_and_ignore_accumulations():
    raw = _make_natuna_raw_wb()
    det = detect_rainfall_template(raw, "natuna_raw.xlsx", "NATUNA")
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == "RAW_NATUNA"
    assert det["suggested_year"] == 2026 and det["suggested_month"] == 10
    assert det["period_confirmation_required"] is True

    sess = create_detect_batch_session("NATUNA", [("natuna_raw.xlsx", raw)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "year": 2099, "month": 10, "dasarian": 1}],
    )
    by_key = {(r["station_id"], r["observation_date"]): r for r in prev["preview_rows"]}
    # Active days in file: 1..4 (days 5..10 completely absent -> NOT created!)
    assert by_key[("21030701A", "2099-10-01")]["display_value"] == "TTU"    # Natuna 0 -> TTU!
    assert by_key[("21030701A", "2099-10-02")]["display_value"] == "9999"   # Natuna '-' -> 9999
    assert by_key[("21030701A", "2099-10-03")]["display_value"] == "22.4"
    assert by_key[("21031801A", "2099-10-02")]["display_value"] == "9999"   # Blank on active day 2 -> 9999
    assert ("21030701A", "2099-10-05") not in by_key                        # Absent day -> NO record
    assert prev["counts"]["unrecognized"] == 1


def test_anambas_raw_codeless_stations_and_symbols():
    raw = _make_anambas_raw_wb()
    det = detect_rainfall_template(raw, "anambas_nov.xlsx", "ANAMBAS")
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == "RAW_ANAMBAS"
    assert det["suggested_year"] == 2026 and det["suggested_month"] == 11

    sess = create_detect_batch_session("ANAMBAS", [("anambas_nov.xlsx", raw)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "year": 2099, "month": 11, "dasarian": 1}],
    )
    sids = {r["station_id"] for r in prev["preview_rows"]}
    assert sids == {"21050101A", "21050201A", "21050501A"}  # All 3 matched (2 without codes!)
    by_key = {(r["station_id"], r["observation_date"]): r for r in prev["preview_rows"]}
    assert by_key[("21050101A", "2099-11-01")]["obs_status"] == "OBSERVED_ZERO"
    assert by_key[("21050101A", "2099-11-02")]["obs_status"] == "TTU"
    assert by_key[("21050101A", "2099-11-03")]["obs_status"] == "MISSING"
    assert by_key[("21050101A", "2099-11-04")]["rainfall_mm"] == 18.5


# ==============================================================================
# 10.3 REGENCY MATRIX, CORRUPT FILE, MAPPING WIZARD PROFILE PERSISTENCE
# ==============================================================================
def test_regency_matrix_and_corrupt_file_isolation():
    raw_karimun = _make_karimun_raw_wb()
    # Uploading raw Karimun under Batam (legacy-only) must be rejected cleanly
    det_batam = detect_rainfall_template(raw_karimun, "karimun.xlsx", "BATAM")
    assert det_batam["status"] == "UNSUPPORTED_FOR_REGENCY"

    # Mixed batch: 1 valid Karimun raw + 1 corrupt file -> valid file still detected
    sess = create_detect_batch_session(
        "KARIMUN",
        [("valid_karimun.xlsx", raw_karimun), ("corrupt.xlsx", b"not_a_zip_excel")],
    )
    statuses = {f["filename"]: f["status"] for f in sess["files"]}
    assert statuses["valid_karimun.xlsx"] == "DETECTED"
    assert statuses["corrupt.xlsx"] == "CORRUPT_FILE"


def test_mapping_wizard_profile_persistence_and_redetection():
    custom_bytes = _make_unknown_custom_wb()
    det1 = detect_rainfall_template(custom_bytes, "unknown_format.xlsx", "KARIMUN")
    assert det1["status"] == "NEEDS_MAPPING"
    fp = det1["structure_fingerprint"]

    saved = save_template_profile(
        profile_name="Test Custom Karimun",
        regency_code="KARIMUN",
        structure_fingerprint=fp,
        sheet_rules={"sheet_name": "CustomSheet"},
        header_config={"header_row": 1},
        date_config={"orientation": "VERTICAL", "date_col": 1},
        value_config={"value_col": 2},
        station_config={"station_col": 1, "fixed_station_id": "21020302A"},
        ignored_columns=[],
        symbol_mapping={},
        operator="PYTEST",
    )
    try:
        # Second detection must automatically match saved persistent profile!
        det2 = detect_rainfall_template(custom_bytes, "renamed_upload.xlsx", "KARIMUN")
        assert det2["status"] == "DETECTED"
        assert det2["template_kind"] == "CUSTOM_MAPPED"
        assert det2["profile_id"] == saved["profile_id"]
    finally:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cews_rainfall_template_profiles WHERE profile_id = %s", (saved["profile_id"],))
            conn.commit()


# ==============================================================================
# 10.5 LEGACY REGRESSION TESTS (BATAM, BINTAN XLSM, TANJUNGPINANG)
# ==============================================================================
@pytest.mark.parametrize(
    "regency_code,rel_path,expected_kind",
    [
        ("BATAM", "tambahan/template_data_input/ch/Kota Batam.xlsx", "LEGACY_MULTI_SHEET"),
        ("BINTAN", "tambahan/baru/Entry Data Pos Hujan Bintan.xlsm", "LEGACY_BINTAN_XLSM"),
        ("TANJUNGPINANG", "tambahan/template_data_input/ch/Kota Tanjungpinang.xlsx", "LEGACY_MULTI_SHEET"),
    ],
)
def test_legacy_templates_regression(regency_code, rel_path, expected_kind):
    fpath = ROOT / rel_path
    if not fpath.exists():
        pytest.skip(f"Fixture not present: {fpath}")
    fbytes = fpath.read_bytes()
    det = detect_rainfall_template(fbytes, fpath.name, regency_code)
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == expected_kind
    assert det["is_raw"] is False


# ==============================================================================
# 10.4 & 10.6 MANUAL INPUT + DB COMMIT + CONFLICT + AUDIT + ROLLBACK
# ==============================================================================
def test_manual_input_commit_conflict_and_rollback():
    sid = "21050101A"  # Stamet Tarempa (Anambas)
    test_dates = ["2099-10-01", "2099-10-02", "2099-10-03", "2099-10-04"]
    created_batches = []

    try:
        # 1. Preview & Commit NEW manual entries (including blank skip, 0, TTU, X)
        rows1 = [
            {"observation_date": "2099-10-01", "raw_value": "15.5"},
            {"observation_date": "2099-10-02", "raw_value": "0"},
            {"observation_date": "2099-10-03", "raw_value": "TTU"},
            {"observation_date": "2099-10-04", "raw_value": ""},  # Blank -> NOT_PROVIDED (must not save!)
        ]
        prev1 = preview_manual_input_v2("ANAMBAS", sid, rows1)
        assert prev1["counts"]["new"] == 3
        assert prev1["counts"]["ttu"] == 1

        res1 = commit_manual_input_v2(
            "ANAMBAS", sid, rows1, confirm_conflicts=False, correction_reason="", operator="PYTEST_OP",
            baseline_fingerprint=prev1["baseline_fingerprint"],
        )
        created_batches.append(res1["batch_id"])
        assert res1["records_added"] == 3

        # 2. Re-submit identical + conflict -> conflict blocked without confirm_conflicts
        rows2 = [
            {"observation_date": "2099-10-01", "raw_value": "20.0"},  # CONFLICT (was 15.5)
            {"observation_date": "2099-10-02", "raw_value": "0"},     # IDENTICAL
        ]
        prev2 = preview_manual_input_v2("ANAMBAS", sid, rows2)
        assert prev2["counts"]["conflict"] == 1
        assert prev2["counts"]["identical"] == 1

        with pytest.raises(ValueError):
            commit_manual_input_v2("ANAMBAS", sid, rows2, confirm_conflicts=False, operator="PYTEST_OP")

        # 3. Approve conflict with mandatory reason -> succeeds & writes correction log
        res2 = commit_manual_input_v2(
            "ANAMBAS", sid, rows2, confirm_conflicts=True, correction_reason="Koreksi kalibrasi PYTEST",
            operator="PYTEST_OP", baseline_fingerprint=prev2["baseline_fingerprint"],
        )
        created_batches.append(res2["batch_id"])
        assert res2["records_updated"] == 1
        assert res2["records_identical_skipped"] == 1

        # Verify correction log & batch rollback
        cancel_res = cancel_ingestion_batch(res2["batch_id"], reason="Rollback test", operator="PYTEST_OP")
        assert cancel_res["status"] == "CANCELLED"
        assert cancel_res["records_reverted"] == 1

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rainfall_mm FROM cews_rainfall_daily WHERE station_id=%s AND observation_date='2099-10-01'",
                    (sid,),
                )
                row = cur.fetchone()
                assert float(row["rainfall_mm"]) == 15.5  # Restored by batch rollback!
    finally:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cews_rainfall_daily WHERE station_id=%s AND observation_date BETWEEN '2099-10-01' AND '2099-10-04'",
                    (sid,),
                )
                cur.execute(
                    "DELETE FROM cews_rainfall_correction_log WHERE station_id=%s AND observation_date BETWEEN '2099-10-01' AND '2099-10-04'",
                    (sid,),
                )
                for bid in created_batches:
                    cur.execute("DELETE FROM staging_rainfall_import WHERE import_batch_id=%s", (bid,))
                    cur.execute("DELETE FROM cews_ingestion_history WHERE batch_id=%s", (bid,))
            conn.commit()


# ==============================================================================
# 10.7 REAL RAW WORKBOOK VALIDATION (F:\TNJ\paper\template_mentah)
# ==============================================================================
REAL_RAW_DIR = Path(r"F:\TNJ\paper\template_mentah")


@pytest.mark.parametrize(
    "regency_code,filename,year,month,expected_kind,expected_stations",
    [
        ("KARIMUN", "Karimun.xlsx", 2026, 10, "RAW_KARIMUN", 7),
        ("LINGGA", "Lingga.xlsx", 2026, 10, "RAW_LINGGA", 8),
        ("NATUNA", "Natuna.xlsx", 2026, 10, "RAW_NATUNA", 15),
        ("ANAMBAS", "Anambas.xlsx", 2026, 11, "RAW_ANAMBAS", 3),
    ],
)
def test_real_raw_workbooks_end_to_end(regency_code, filename, year, month, expected_kind, expected_stations):
    fpath = REAL_RAW_DIR / filename
    if not fpath.exists():
        pytest.skip(f"Real raw workbook not present in this environment: {fpath}")

    fbytes = fpath.read_bytes()
    det = detect_rainfall_template(fbytes, filename, regency_code)
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == expected_kind

    sess = create_detect_batch_session(regency_code, [(filename, fbytes)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "year": year, "month": month, "dasarian": None}],
    )
    fs = prev["file_summaries"][0]
    assert fs["status"] == "PARSED"
    assert fs["recognized_stations_count"] == expected_stations
    assert fs["unmapped_stations"] == []
    assert prev["counts"]["unrecognized"] == 0
    assert fs["records_count"] > 0


# ==============================================================================
# 10.8 BINTAN VS TANJUNGPINANG STRICT STATION ISOLATION
# ==============================================================================
def test_bintan_tanjungpinang_strict_isolation():
    fpath = ROOT / "tambahan/template_data_input/ch/Kota Tanjungpinang.xlsx"
    if not fpath.exists():
        pytest.skip(f"Legacy workbook not present: {fpath}")
    fbytes = fpath.read_bytes()

    bintan_master = {s["station_id"].upper() for s in get_regency_stations("BINTAN")}
    tpi_master = {s["station_id"].upper() for s in get_regency_stations("TANJUNGPINANG")}
    assert bintan_master.isdisjoint(tpi_master)

    sess_b = create_detect_batch_session("BINTAN", [(fpath.name, fbytes)])
    prev_b = preview_batch_session(
        sess_b["batch_session_id"],
        [{"file_id": sess_b["files"][0]["file_id"], "include": True, "start_date": "2026-01-01", "end_date": "2026-01-10"}],
    )
    b_sids = {r["station_id"].upper() for r in prev_b["preview_rows"]}
    assert b_sids.issubset(bintan_master)

    sess_t = create_detect_batch_session("TANJUNGPINANG", [(fpath.name, fbytes)])
    prev_t = preview_batch_session(
        sess_t["batch_session_id"],
        [{"file_id": sess_t["files"][0]["file_id"], "include": True, "start_date": "2026-01-01", "end_date": "2026-01-10"}],
    )
    t_sids = {r["station_id"].upper() for r in prev_t["preview_rows"]}
    assert t_sids.issubset(tpi_master)
    assert b_sids.isdisjoint(t_sids)


# ==============================================================================
# 10.9 PERIOD-BASED SOFT-DELETE (VOID), AUDIT TRAIL & RECOVERY
# ==============================================================================
def test_period_soft_delete_void_audit_and_recovery():
    from backend.rainfall_ingestion_v2 import (
        commit_delete_rainfall_period,
        preview_delete_rainfall_period,
    )

    sid_a = "21050101A"  # Stamet Tarempa (Anambas)
    sid_b = "21050201A"  # Langir (Anambas)
    batches = []

    try:
        # Seed isolated test records on 2099-11-01..03 for 2 Anambas stations
        r_a = commit_manual_input_v2(
            "ANAMBAS", sid_a,
            [
                {"observation_date": "2099-11-01", "raw_value": "12.5"},
                {"observation_date": "2099-11-02", "raw_value": "0"},
                {"observation_date": "2099-11-03", "raw_value": "5.0"},
            ],
            operator="PYTEST_SEED",
        )
        r_b = commit_manual_input_v2(
            "ANAMBAS", sid_b,
            [
                {"observation_date": "2099-11-01", "raw_value": "8.0"},
                {"observation_date": "2099-11-02", "raw_value": "TTU"},
            ],
            operator="PYTEST_SEED",
        )
        batches.extend([r_a["batch_id"], r_b["batch_id"]])

        # 1. Preview delete for single station (sid_a) on 2099-11-01..02
        p1 = preview_delete_rainfall_period("ANAMBAS", "2099-11-01", "2099-11-02", station_ids=[sid_a])
        assert p1["total_records"] == 2
        assert p1["affected_stations_count"] == 1

        # 2. Commit soft-delete VOID for sid_a on 2099-11-01..02
        d1 = commit_delete_rainfall_period(
            "ANAMBAS", "2099-11-01", "2099-11-02",
            reason="Uji soft-delete periode PYTEST", operator="PYTEST_OP", station_ids=[sid_a],
        )
        batches.append(d1["batch_id"])
        assert d1["voided_records"] == 2

        # Verify sid_a 2099-11-01..02 are VOID, while sid_a 2099-11-03 and sid_b are UNTOUCHED
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT station_id, observation_date, rainfall_mm, obs_status FROM cews_rainfall_daily "
                    "WHERE station_id IN (%s, %s) AND observation_date BETWEEN '2099-11-01' AND '2099-11-03'",
                    (sid_a, sid_b),
                )
                state = {(r["station_id"], r["observation_date"].strftime("%Y-%m-%d")): r for r in cur.fetchall()}

        assert state[(sid_a, "2099-11-01")]["obs_status"] == "VOID"
        assert state[(sid_a, "2099-11-01")]["rainfall_mm"] is None
        assert state[(sid_a, "2099-11-03")]["obs_status"] == "OBSERVED_VALID"
        assert state[(sid_b, "2099-11-01")]["obs_status"] == "OBSERVED_VALID"

        # 3. Verify recovery via cancel_ingestion_batch restores sid_a 2099-11-01 back to 12.5
        rec = cancel_ingestion_batch(d1["batch_id"], reason="Pemulihan uji PYTEST", operator="PYTEST_OP")
        assert rec["status"] == "CANCELLED"
        assert rec["records_reverted"] == 2

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rainfall_mm, obs_status FROM cews_rainfall_daily WHERE station_id=%s AND observation_date='2099-11-01'",
                    (sid_a,),
                )
                restored = cur.fetchone()
                assert float(restored["rainfall_mm"]) == 12.5
                assert restored["obs_status"] == "OBSERVED_VALID"
    finally:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cews_rainfall_daily WHERE station_id IN (%s, %s) AND observation_date BETWEEN '2099-11-01' AND '2099-11-03'",
                    (sid_a, sid_b),
                )
                cur.execute(
                    "DELETE FROM cews_rainfall_correction_log WHERE station_id IN (%s, %s) AND observation_date BETWEEN '2099-11-01' AND '2099-11-03'",
                    (sid_a, sid_b),
                )
                for bid in batches:
                    cur.execute("DELETE FROM staging_rainfall_import WHERE import_batch_id=%s", (bid,))
                    cur.execute("DELETE FROM cews_ingestion_history WHERE batch_id=%s", (bid,))
            conn.commit()


# ==============================================================================
# 10.10 NATUNA LEGACY REGRESSION (WITHOUT docs/ SCHEMA FILE — DOCKER SIMULATION)
# ==============================================================================
def test_natuna_legacy_all_15_sheets_without_docs_schema(monkeypatch):
    import backend.ingestion_service as ing_mod

    fpath = ROOT / "tambahan/template_data_input/ch/Kabupaten Natuna.xlsx"
    if not fpath.exists():
        pytest.skip(f"Legacy Natuna workbook not found: {fpath}")

    # Simulate production Docker container where docs/DSS_PIK_TEMPLATE_INPUT_SCHEMA.json is absent
    monkeypatch.setattr(ing_mod, "get_curah_hujan_sheet_mapping", lambda: {})

    fbytes = fpath.read_bytes()
    det = detect_rainfall_template(fbytes, fpath.name, "NATUNA")
    assert det["status"] == "DETECTED"
    assert det["template_kind"] == "LEGACY_MULTI_SHEET"

    sess = create_detect_batch_session("NATUNA", [(fpath.name, fbytes)])
    fid = sess["files"][0]["file_id"]
    prev = preview_batch_session(
        sess["batch_session_id"],
        [{"file_id": fid, "include": True, "start_date": "2026-01-01", "end_date": "2026-01-20"}],
    )
    fs = prev["file_summaries"][0]
    assert fs["status"] == "PARSED"
    assert fs["unmapped_stations"] == []
    assert fs["recognized_stations_count"] == 15


# ==============================================================================
# 10.11 TAB 3 STANDARDIZED 5-STATE CORRECTION, SELECTED VOID & CONFLICT RECOVERY
# ==============================================================================
def test_tab3_standardized_correction_selected_void_and_conflict_recovery():
    from backend.rainfall_ingestion_v2 import (
        correct_rainfall_record_v2,
        query_rainfall_records_v2,
        recover_void_batch_v2,
        void_selected_rainfall_records,
    )

    sid = "21030701A"  # Stamet Ranai Natuna
    batches = []
    try:
        seed = commit_manual_input_v2(
            "NATUNA", sid,
            [
                {"observation_date": "2099-12-01", "raw_value": "10.0"},
                {"observation_date": "2099-12-02", "raw_value": "20.0"},
            ],
            operator="klimatkepri",
        )
        batches.append(seed["batch_id"])

        # 1. Standardized 5-state corrections
        c1 = correct_rainfall_record_v2(sid, "2099-12-01", "OBSERVED_ZERO", None, "Uji zero", "klimatkepri")
        assert c1["new_display"] == "-" and c1["new_obs_status"] == "OBSERVED_ZERO"

        c2 = correct_rainfall_record_v2(sid, "2099-12-01", "TTU", None, "Uji TTU", "klimatkepri")
        assert c2["new_display"] == "TTU" and c2["new_obs_status"] == "TTU"

        c3 = correct_rainfall_record_v2(sid, "2099-12-01", "MISSING", None, "Uji missing", "klimatkepri")
        assert c3["new_display"] == "9999" and c3["new_obs_status"] == "MISSING"

        c4 = correct_rainfall_record_v2(sid, "2099-12-01", "DAMAGED", None, "Uji rusak", "klimatkepri")
        assert c4["new_display"] == "9999" and c4["new_obs_status"] == "DAMAGED"

        c5 = correct_rainfall_record_v2(sid, "2099-12-01", "OBSERVED_VALID", 14.5, "Uji valid", "klimatkepri")
        assert c5["new_display"] == "14.5" and c5["new_obs_status"] == "OBSERVED_VALID"

        # 2. Query Tab 3 records with human labels & standardized display
        q = query_rainfall_records_v2(regency_code="NATUNA", station_id=sid, start_date="2099-12-01", end_date="2099-12-02")
        assert q["total"] == 2
        assert q["items"][0]["status_label"] == "Hujan Terukur"

        # 3. Void selected 2 records
        v = void_selected_rainfall_records(
            [
                {"station_id": sid, "observation_date": "2099-12-01"},
                {"station_id": sid, "observation_date": "2099-12-02"},
            ],
            reason="Uji void terpilih",
            operator="klimatkepri",
        )
        batches.append(v["batch_id"])
        assert v["voided_records"] == 2

        # 4. Simulate post-VOID correction on 2099-12-02 -> recovery must skip 2099-12-02 (conflict) & restore 2099-12-01!
        correct_rainfall_record_v2(sid, "2099-12-02", "OBSERVED_VALID", 33.0, "Input ulang pasca VOID", "klimatkepri")
        rec = recover_void_batch_v2(v["batch_id"], reason="Pemulihan uji konflik", operator="klimatkepri")
        assert rec["restored_records"] == 1
        assert rec["conflict_skipped"] == 1

        q_after = query_rainfall_records_v2(regency_code="NATUNA", station_id=sid, start_date="2099-12-01", end_date="2099-12-02")
        by_d = {r["observation_date"]: r for r in q_after["items"]}
        assert by_d["2099-12-01"]["display_value"] == "14.5"
        assert by_d["2099-12-02"]["display_value"] == "33.0"  # Preserved post-VOID edit!
    finally:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cews_rainfall_daily WHERE station_id=%s AND observation_date BETWEEN '2099-12-01' AND '2099-12-02'",
                    (sid,),
                )
                cur.execute(
                    "DELETE FROM cews_rainfall_correction_log WHERE station_id=%s AND observation_date BETWEEN '2099-12-01' AND '2099-12-02'",
                    (sid,),
                )
                for bid in batches:
                    cur.execute("DELETE FROM staging_rainfall_import WHERE import_batch_id=%s", (bid,))
                    cur.execute("DELETE FROM cews_ingestion_history WHERE batch_id=%s", (bid,))
            conn.commit()
