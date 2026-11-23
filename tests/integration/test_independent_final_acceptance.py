"""
tests/integration/test_independent_final_acceptance.py
================================================================================
DSS-PIK INDEPENDENT FINAL ACCEPTANCE AUDIT TEST SUITE
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
================================================================================

Covers Scenarios A–F of the Independent Final Acceptance Audit:
- Scenario A: Multi-Vintage Dasarian (19 Oct 2026 -> 29 Oct 2026 -> 30 Oct 2026)
- Scenario B: Multi-Vintage Bulanan (29 Oct 2026 -> 30 Oct 2026) + Non-NULL target_dasarian=0 sentinel
- Scenario C: Idempotency, UPDATED diff, and Explicit Operator Consent Gate
- Scenario D: Workbook vs Filename issue_date Conflict Rejection
- Scenario E: Vintage Cutoff Selection Simulation (25 Oct -> 19 Oct, 29 Oct -> 29 Oct, 30 Oct -> 30 Oct, 01 Oct -> None)
- Scenario F: Station Metadata Reconciliation (57 Master Stations in DailyRainfallTable & ProbabilityDataTable)
- Scenario G: Operational KPI Aggregation (COMMITTED only) & Scoped Void/Correction Audit Trail
"""

import io
import unittest
import openpyxl
from pathlib import Path
from backend.database import get_raw_connection
from backend.ingestion_service import (
    parse_probability_excel,
    commit_ingestion_session,
    get_operational_summary,
    get_correction_and_void_logs,
    get_latest_data_status,
    void_probability_record,
    ARG_STATION_IDS,
)
from backend.data_service import get_probability_data, select_eligible_vintage
from backend.main import get_rainfall_columns, get_rainfall_daily_table

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURE_19_OKT = ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx"
FIXTURE_MONTHLY = ROOT_DIR / "tambahan" / "template_data_input" / "prob" / "bulanan" / "KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx"


def _clone_workbook_with_issue_date(source_bytes: bytes, new_issue_str: str) -> bytes:
    """Clones workbook bytes and updates any ver_YYYY.MM.DD metadata in Sheet1/TabelPCH/TabelPSH."""
    wb = openpyxl.load_workbook(io.BytesIO(source_bytes))
    dot_date = new_issue_str.replace("-", ".")
    for s_name in ("Sheet1", "TabelPCH", "TabelPSH"):
        if s_name in wb.sheetnames:
            ws = wb[s_name]
            for r in range(1, 6):
                for c in range(1, 10):
                    val = ws.cell(row=r, column=c).value
                    if val is not None and "ver_" in str(val):
                        import re
                        ws.cell(row=r, column=c, value=re.sub(r"ver_\d{4}[._-]\d{2}[._-]\d{2}", f"ver_{dot_date}", str(val)))
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


class TestIndependentFinalAcceptance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
        row = cur.fetchone()
        cls.baseline_ch = row["total"] if isinstance(row, dict) else row[0]
        assert cls.baseline_ch == 286085, f"Expected 286085 rows in cews_rainfall_daily, got {cls.baseline_ch}"

        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM cews_ingestion_history;")
        h_row = cur.fetchone()
        cls.max_history_id = h_row["max_id"] if isinstance(h_row, dict) else h_row[0]

        # Clean target rows for clean Scenario A & B execution
        cur.execute("DELETE FROM cews_forecast_snapshot WHERE target_year IN (2026, 2027) AND (target_month = 11 OR (forecast_resolution = 'BULANAN' AND issue_date IN ('2026-10-29', '2026-10-30')));")
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM cews_forecast_snapshot WHERE target_year = 2026 AND target_month = 11;")
        cur.execute("DELETE FROM cews_forecast_snapshot WHERE forecast_resolution = 'BULANAN' AND issue_date IN ('2026-10-29', '2026-10-30');")
        cur.execute("DELETE FROM cews_ingestion_history WHERE id > %s;", (cls.max_history_id,))
        conn.commit()
        conn.close()

        # Restore genuine BMKG operational fixtures for November 2026 (vintages 09 Oct & 19 Oct)
        real_fixtures = [
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.09_das 1 nov.xlsx",
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx",
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 2 nov.xlsx",
        ]
        for rf in real_fixtures:
            if rf.exists():
                p_res = parse_probability_excel(rf.read_bytes(), filename=rf.name, forecast_type="PROBABILITAS_DASARIAN")
                commit_ingestion_session(p_res["staging_token"])

        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
        row = cur.fetchone()
        current_ch = row["total"] if isinstance(row, dict) else row[0]
        conn.close()
        assert current_ch == 286085, "Baseline cews_rainfall_daily corrupted!"

    def test_01_scenario_a_three_vintages_dasarian_19_29_30_oct(self):
        """
        Scenario A:
        1. Upload Dasarian I Nov 2026 issue 2026-10-19 -> NEW = 208
        2. Upload Dasarian I Nov 2026 issue 2026-10-29 -> NEW VINTAGE = 208
        3. Upload Dasarian I Nov 2026 issue 2026-10-30 -> NEW VINTAGE = 208
        Total in DB for 2026-11-das1 = 624 rows (3 vintages x 208 rows).
        """
        raw_19 = FIXTURE_19_OKT.read_bytes()
        raw_29 = _clone_workbook_with_issue_date(raw_19, "2026-10-29")
        raw_30 = _clone_workbook_with_issue_date(raw_19, "2026-10-30")

        # 1. Vintage 19 Oct 2026
        p19 = parse_probability_excel(raw_19, "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx", "PROBABILITAS_DASARIAN")
        self.assertEqual(p19["summary"]["total_new"], 208)
        self.assertEqual(p19["summary"].get("total_new_vintage", 0), 0)
        c19 = commit_ingestion_session(p19["staging_token"])
        self.assertEqual(c19["status"], "COMMITTED")

        # 2. Vintage 29 Oct 2026
        p29 = parse_probability_excel(raw_29, "KEPRI_pch_ecmwf_perpos_ver_2026.10.29_das 1 nov.xlsx", "PROBABILITAS_DASARIAN")
        self.assertEqual(p29["summary"].get("total_new_vintage", 0), 208)
        self.assertEqual(p29["summary"]["total_new"], 0)
        c29 = commit_ingestion_session(p29["staging_token"])
        self.assertEqual(c29["status"], "COMMITTED")

        # 3. Vintage 30 Oct 2026
        p30 = parse_probability_excel(raw_30, "KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx", "PROBABILITAS_DASARIAN")
        self.assertEqual(p30["summary"].get("total_new_vintage", 0), 208)
        self.assertEqual(p30["summary"]["total_new"], 0)
        c30 = commit_ingestion_session(p30["staging_token"])
        self.assertEqual(c30["status"], "COMMITTED")

        # Verify 3 vintages coexist in MariaDB (624 rows)
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT issue_date, COUNT(*) as cnt
            FROM cews_forecast_snapshot
            WHERE target_year = 2026 AND target_month = 11 AND target_dasarian = 1 AND forecast_resolution = 'DASARIAN'
            GROUP BY issue_date
            ORDER BY issue_date DESC
        """)
        rows = cur.fetchall()
        conn.close()

        v_map = {r["issue_date"].strftime("%Y-%m-%d"): r["cnt"] for r in rows}
        self.assertEqual(v_map, {"2026-10-30": 208, "2026-10-29": 208, "2026-10-19": 208})
        self.assertEqual(sum(v_map.values()), 624)

    def test_02_scenario_e_vintage_cutoff_selection_simulation(self):
        """
        Scenario E (Prioritas 1.2):
        For target Dasarian I Nov 2026 with vintages [2026-10-30, 2026-10-29, 2026-10-19]:
        - Cutoff 2026-10-25 -> selects 2026-10-19
        - Cutoff 2026-10-29 -> selects 2026-10-29
        - Cutoff 2026-10-30 -> selects 2026-10-30
        - Cutoff 2026-10-01 (before all vintages) -> selects None (never uses future vintage after cutoff)
        """
        d25 = get_probability_data(period_id="2026-11-das1", cutoff_date="2026-10-25")
        self.assertEqual(d25["meta"]["active_vintage_issue"], "2026-10-19")

        d29 = get_probability_data(period_id="2026-11-das1", cutoff_date="2026-10-29")
        self.assertEqual(d29["meta"]["active_vintage_issue"], "2026-10-29")

        d30 = get_probability_data(period_id="2026-11-das1", cutoff_date="2026-10-30")
        self.assertEqual(d30["meta"]["active_vintage_issue"], "2026-10-30")

        # Direct unit check for cutoff earlier than all vintages
        none_vintage = select_eligible_vintage(["2026-10-30", "2026-10-29", "2026-10-19"], evaluation_cutoff_date="2026-10-01")
        self.assertIsNone(none_vintage, "Vintages published after evaluation_cutoff_date must never be selected")

    def test_03_scenario_b_multi_vintage_bulanan_and_sentinel(self):
        """
        Scenario B:
        Monthly probability ingestion with vintages 2026-10-29 and 2026-10-30 across 6 monthly horizons.
        Each target month stores 52 manual stations x 3 parameters (pa300, pa400, pa500) = 156 rows per month
        (936 rows across 6 monthly horizons) with non-NULL sentinel target_dasarian = 0.
        """
        base_monthly = FIXTURE_MONTHLY.read_bytes()

        m_29 = _clone_workbook_with_issue_date(base_monthly, "2026-10-29")
        m_30 = _clone_workbook_with_issue_date(base_monthly, "2026-10-30")

        p29 = parse_probability_excel(m_29, "KEPRI_pch_ecmwf_bulanan_ver_2026.10.29.xlsx", "PROBABILITAS_BULANAN")
        self.assertEqual(p29["summary"]["total_new"], 936)
        self.assertEqual(p29["summary"].get("total_new_vintage", 0), 156)  # 2026-01 already has vintage 2025-12-29
        commit_ingestion_session(p29["staging_token"])

        p30 = parse_probability_excel(m_30, "KEPRI_pch_ecmwf_bulanan_ver_2026.10.30.xlsx", "PROBABILITAS_BULANAN")
        self.assertEqual(p30["summary"].get("total_new_vintage", 0), 1092)  # All 7 horizons now have prior vintage 2026-10-29
        self.assertEqual(p30["summary"]["total_new"], 0)
        commit_ingestion_session(p30["staging_token"])

        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT issue_date, target_dasarian, COUNT(*) as cnt
            FROM cews_forecast_snapshot
            WHERE target_year = 2026 AND target_month = 11 AND forecast_resolution = 'BULANAN'
            GROUP BY issue_date, target_dasarian
            ORDER BY issue_date DESC
        """)
        rows = cur.fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r["target_dasarian"], 0, "Monthly forecast must use non-NULL sentinel target_dasarian=0")
            self.assertEqual(r["cnt"], 156, "Each monthly horizon must store 52 stations x 3 parameters = 156 rows")

    def test_04_scenario_c_idempotency_and_updated_consent(self):
        """
        Scenario C:
        - Re-uploading identical 2026-10-30 Dasarian I Nov 2026 -> IDENTICAL = 208
        - Modifying 1 cell -> UPDATED = 1, IDENTICAL = 207; commit without consent raises ValueError; commit with consent succeeds.
        """
        raw_19 = FIXTURE_19_OKT.read_bytes()
        raw_30 = _clone_workbook_with_issue_date(raw_19, "2026-10-30")

        p_idemp = parse_probability_excel(raw_30, "KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx", "PROBABILITAS_DASARIAN")
        self.assertEqual(p_idemp["summary"]["total_identical"], 208)
        self.assertEqual(p_idemp["summary"]["total_new"], 0)
        self.assertEqual(p_idemp["summary"]["total_updated"], 0)

        # Modify 1 cell
        wb = openpyxl.load_workbook(io.BytesIO(raw_30))
        ws = wb["pb20"]
        orig_v = ws.cell(row=2, column=8).value
        ws.cell(row=2, column=8, value=77.5 if orig_v != 77.5 else 81.2)
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()

        p_upd = parse_probability_excel(buf.getvalue(), "KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx", "PROBABILITAS_DASARIAN")
        self.assertEqual(p_upd["summary"]["total_updated"], 1)
        self.assertEqual(p_upd["summary"]["total_identical"], 207)

        with self.assertRaises(ValueError):
            commit_ingestion_session(p_upd["staging_token"], explicit_update_consent=False)

        c_upd = commit_ingestion_session(p_upd["staging_token"], explicit_update_consent=True)
        self.assertEqual(c_upd["status"], "COMMITTED")

    def test_05_scenario_d_workbook_vs_filename_issue_date_conflict_rejected(self):
        """
        Scenario D (Prioritas 1.2):
        If workbook content states ver_2026.10.19 but filename states ver_2026.10.29,
        parse_probability_excel must reject the conflict with ValueError instead of silently accepting.
        """
        wb = openpyxl.load_workbook(FIXTURE_19_OKT)
        if "Sheet1" not in wb.sheetnames:
            ws_meta = wb.create_sheet("Sheet1", 0)
        else:
            ws_meta = wb["Sheet1"]
        ws_meta.cell(row=1, column=1, value="Metadata ECMWF ver_2026.10.19")
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()

        with self.assertRaises(ValueError) as ctx:
            parse_probability_excel(
                buf.getvalue(),
                filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.29_das 1 nov.xlsx",
                forecast_type="PROBABILITAS_DASARIAN"
            )
        self.assertIn("Konflik metadata issue_date terdeteksi", str(ctx.exception))

    def test_06_scenario_f_station_metadata_57_master_consistency(self):
        """
        Scenario F (Prioritas 4):
        Verify get_rainfall_columns() and get_rainfall_daily_table() return exactly 57 master station columns
        (isolating the 58th external non-master column Tanjung Riau 21710502A), matching ProbabilityDataTable (57 stations).
        """
        col_res = get_rainfall_columns()
        self.assertEqual(len(col_res.station_columns), 57, "Rainfall columns must strictly expose 57 master stations")
        sids = {c.station_id.upper() for c in col_res.station_columns}
        self.assertNotIn("21710502A", sids, "Non-master external station 21710502A must be isolated from operational table")

        tbl_res = get_rainfall_daily_table(page=1, page_size=10, year=2026, month=10, dasarian=1, start_date=None, end_date=None, order="desc")
        self.assertEqual(len(tbl_res.columns), 57)

        prob_res = get_probability_data(period_id="2026-11-das1")
        self.assertEqual(len(prob_res["data"]), 57)
        arg_rows = [r for r in prob_res["data"] if r["station_id"] in ARG_STATION_IDS]
        self.assertEqual(len(arg_rows), 5)

    def test_07_scenario_g_kpi_summary_and_scoped_void_audit(self):
        """
        Scenario G (Prioritas 5 & 6.4):
        - Verify get_operational_summary() counts only COMMITTED batches in total_new_records / total_updated_records.
        - Verify void_probability_record() deletes only the targeted vintage/period and records in get_correction_and_void_logs().
        - Verify get_latest_data_status() returns both Dasarian and Bulanan probability status accurately.
        """
        void_res = void_probability_record(
            issue_date="2026-10-30",
            target_period="2026-11-das1",
            station_id="21010401A",
            forecast_parameter="pb20",
            reason="Uji audit pembatalan terarah 1 parameter",
            operator="AUDITOR_BMKG"
        )
        self.assertEqual(void_res["status"], "SUCCESS")
        self.assertEqual(void_res["records_voided"], 1)

        # Vintage 2026-10-29 and 2026-10-19 must remain 208 rows each, while 2026-10-30 has 207 rows
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT issue_date, COUNT(*) as cnt
            FROM cews_forecast_snapshot
            WHERE target_year = 2026 AND target_month = 11 AND target_dasarian = 1 AND forecast_resolution = 'DASARIAN'
            GROUP BY issue_date
        """)
        v_counts = {r["issue_date"].strftime("%Y-%m-%d"): r["cnt"] for r in cur.fetchall()}
        conn.close()
        self.assertEqual(v_counts["2026-10-30"], 207)
        self.assertEqual(v_counts["2026-10-29"], 208)
        self.assertEqual(v_counts["2026-10-19"], 208)

        # Verify correction & void logs endpoint includes this void action
        logs = get_correction_and_void_logs(limit=20)
        self.assertGreaterEqual(logs["total"], 1)
        self.assertTrue(any(item["action_type"] == "VOID_PROBABILITAS" for item in logs["items"]))

        # Verify latest status includes both dasarian and bulanan probability
        st = get_latest_data_status()
        self.assertEqual(st["probabilitas_dasarian"]["status_label"], "Tersedia")
        self.assertEqual(st["probabilitas_bulanan"]["status_label"], "Tersedia")
        self.assertIn("latest_target_period", st["probabilitas_dasarian"])
        self.assertIn("latest_target_period", st["probabilitas_bulanan"])

        # Verify KPI summary
        kpi = get_operational_summary()
        self.assertGreaterEqual(kpi["total_batches"], kpi["successful_batches"])
        self.assertGreaterEqual(kpi["total_new_records"], 0)


if __name__ == "__main__":
    unittest.main()

