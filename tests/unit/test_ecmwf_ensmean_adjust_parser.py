"""
tests/unit/test_ecmwf_ensmean_adjust_parser.py

Phase 2 unit tests covering:
1. ENSMEAN header classification & Adjust priority (case-insensitive, ignores 'natuna').
2. Conflict detection when >1 Adjust candidates exist for the same target period.
3. Historical/analysis columns (anlis, analisis, obs) flagged as IGNORED NON-FORECAST COLUMN.
4. Dynamic monthly period detection & year rollover (Dec -> Jan).
5. Strict verified issue_date extraction (NO fallback to datetime.now()).
6. Dasarian multi-period & 3-file release validation (issue_date mismatch & target conflict).
7. Coverage difference warning between Probability and ENSMEAN without fabricating/zeroing records.
"""

import io
from datetime import date
import openpyxl
import pytest

from backend.ecmwf_forecast_service import (
    extract_verified_issue_date,
    parse_ecmwf_dasarian_release,
    parse_ecmwf_workbook_unified,
    parse_period_token,
    resolve_ensmean_columns,
)


def _make_xlsx_bytes(sheets: dict) -> bytes:
    wb = openpyxl.Workbook()
    first = True
    for sname, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(sname)
        ws.title = sname
        first = False
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_01_adjust_priority_over_regular_and_ignore_region_descriptor():
    headers = [
        "NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB",
        "Agt", "Agt (adjust natuna)", "Sep", "Okt", "Okt Adjust", "Nov",
    ]
    res = resolve_ensmean_columns(headers, issue_dt=date(2026, 8, 1), is_monthly=True)
    assert res["conflicts"] == []
    sel = {c["period_id"]: c for c in res["selected_columns"]}
    assert list(sel.keys()) == ["2026-08", "2026-09", "2026-10", "2026-11"]

    # Agt (adjust natuna) prioritized; 'natuna' NOT used as region logic, original header preserved
    assert sel["2026-08"]["adjustment_status"] == "ADJUSTED"
    assert sel["2026-08"]["source_column"] == "Agt (adjust natuna)"
    assert sel["2026-08"]["overrode_regular_columns"] == ["Agt"]

    # Sep has no Adjust -> Regular
    assert sel["2026-09"]["adjustment_status"] == "REGULAR"
    assert sel["2026-09"]["source_column"] == "Sep"

    # Okt Adjust prioritized over Okt
    assert sel["2026-10"]["adjustment_status"] == "ADJUSTED"
    assert sel["2026-10"]["source_column"] == "Okt Adjust"
    assert sel["2026-10"]["overrode_regular_columns"] == ["Okt"]

    # Nov -> Regular
    assert sel["2026-11"]["adjustment_status"] == "REGULAR"
    assert sel["2026-11"]["source_column"] == "Nov"


def test_02_multiple_adjust_candidates_for_same_period_triggers_conflict():
    headers = [
        "NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB",
        "Agt", "Agt (adjust)", "Agt (adjust natuna)", "Sep",
    ]
    res = resolve_ensmean_columns(headers, issue_dt=date(2026, 8, 1), is_monthly=True)
    assert len(res["conflicts"]) == 1
    conf = res["conflicts"][0]
    assert conf["period_id"] == "2026-08"
    assert set(conf["candidates"]) == {"Agt (adjust)", "Agt (adjust natuna)"}
    # Conflicted period must NOT be randomly picked into selected_columns
    selected_pids = [c["period_id"] for c in res["selected_columns"]]
    assert "2026-08" not in selected_pids
    assert selected_pids == ["2026-09"]


def test_03_historical_analysis_columns_flagged_as_ignored_non_forecast():
    headers = [
        "NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB",
        "anlis apr", "analisis mei", "obs jun", "Jul", "Agt", "Sep",
    ]
    res = resolve_ensmean_columns(headers, issue_dt=date(2026, 6, 1), is_monthly=True)
    ignored = res["ignored_non_forecast_columns"]
    assert len(ignored) == 3
    assert [i["source_column"] for i in ignored] == ["anlis apr", "analisis mei", "obs jun"]
    assert all(i["classification"] == "IGNORED NON-FORECAST COLUMN" for i in ignored)
    assert [c["period_id"] for c in res["selected_columns"]] == ["2026-07", "2026-08", "2026-09"]


def test_04_dynamic_monthly_year_rollover_dec_to_jan():
    headers = [
        "NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB",
        "Okt", "Nov", "Nov Adjust", "Des", "Des Adjust", "Jan", "Jan Adjust", "Feb", "Mar", "Apr",
    ]
    res = resolve_ensmean_columns(headers, issue_dt=date(2026, 10, 1), is_monthly=True)
    pids = [c["period_id"] for c in res["selected_columns"]]
    assert pids == ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"]
    adj_pids = [c["period_id"] for c in res["selected_columns"] if c["adjustment_status"] == "ADJUSTED"]
    assert adj_pids == ["2026-11", "2026-12", "2027-01"]


def test_05_strict_issue_date_no_datetime_now_fallback():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "pb20"
    ws.append(["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", "NovIII"])
    with pytest.raises(ValueError, match="Issue date"):
        extract_verified_issue_date(wb, "KEPRI_without_version_date.xlsx")

    # Valid filename date
    iss, src = extract_verified_issue_date(wb, "KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 3 NOV.xlsx")
    assert iss == "2026-11-17"
    assert src == "FILENAME_VERIFIED"

    # Conflict between workbook Sheet1 metadata and filename must raise
    ws_meta = wb.create_sheet("Sheet1")
    ws_meta.append(["ver_2026.11.10"])
    with pytest.raises(ValueError, match="Konflik metadata issue_date"):
        extract_verified_issue_date(wb, "KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 3 NOV.xlsx")


def test_06_coverage_difference_warning_without_fabricating_or_zeroing():
    # pa300 has 3 months (Agt, Sep, Okt), EnsMean has 2 months (Sep, Okt)
    b = _make_xlsx_bytes({
        "pa300": [
            ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", "Agt", "Sep", "Okt"],
            ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 20.0, 35.0, 50.0],
        ],
        "pa400": [
            ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", "Agt", "Sep", "Okt"],
            ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 10.0, 15.0, 25.0],
        ],
        "pa500": [
            ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", "Agt", "Sep", "Okt"],
            ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 5.0, 5.0, 10.0],
        ],
        "EnsMean": [
            ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", "Sep", "Okt"],
            ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 185.4, 240.8],
        ],
    })
    res = parse_ecmwf_workbook_unified(
        b, "KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx", forecast_type="PROBABILITAS_BULANAN", register_session=False
    )
    assert any("Perbedaan cakupan target periode" in w for w in res["warnings"])
    det_entries = res["_session_obj"]["deterministic_entries"]
    assert {e["period_id"] for e in det_entries} == {"2026-09", "2026-10"}
    assert "2026-08" not in {e["period_id"] for e in det_entries}
    prob_entries = res["_session_obj"]["entries"]
    assert {e["period_id"] for e in prob_entries} == {"2026-08", "2026-09", "2026-10"}


def test_07_dasarian_three_file_release_validation_rejects_mismatch_and_conflict():
    def _das_file(col_hdr: str) -> bytes:
        return _make_xlsx_bytes({
            "pb20": [
                ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", col_hdr],
                ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 12.0],
            ],
            "pa150": [
                ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", col_hdr],
                ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 5.0],
            ],
            "pa200": [
                ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", col_hdr],
                ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 2.0],
            ],
            "pa300": [
                ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", col_hdr],
                ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 0.0],
            ],
            "EnsMean": [
                ["NOPOS", "KECAMATAN-POSHUJAN", "LON", "LAT", "PROV", "KAB", "URUTKAB", col_hdr],
                ["21010401A", "Kawal", 104.6, 1.0, "KEPRI", "Kab. Bintan", 1, 68.5],
            ],
        })

    # 1. Valid 3-file release
    rel = parse_ecmwf_dasarian_release([
        ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 3 NOV.xlsx", _das_file("NovIII")),
        ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 1 DES.xlsx", _das_file("DesI")),
        ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 2 DES.xlsx", _das_file("DesII")),
    ])
    assert rel["release_group_id"] == "ECMWF_DAS_2026-11-17"
    assert {p["period_id"] for p in rel["periods_detected"]} == {"2026-11-das3", "2026-12-das1", "2026-12-das2"}

    # 2. Mismatched issue_date across files -> rejected
    with pytest.raises(ValueError, match="Konflik issue_date"):
        parse_ecmwf_dasarian_release([
            ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 3 NOV.xlsx", _das_file("NovIII")),
            ("KEPRI_pch_ecmwf_perpos_ver_2026.11.19_DAS 1 DES.xlsx", _das_file("DesI")),
        ])

    # 3. Duplicate target period across files -> rejected
    with pytest.raises(ValueError, match="Konflik target periode"):
        parse_ecmwf_dasarian_release([
            ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_DAS 3 NOV.xlsx", _das_file("NovIII")),
            ("KEPRI_pch_ecmwf_perpos_ver_2026.11.17_COPY.xlsx", _das_file("NovIII")),
        ])
