"""
tests/integration/test_multivintage_ecmwf.py
================================================================================
DSS-PIK MULTI-VINTAGE ECMWF INTEGRATION TEST SUITE
BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang
================================================================================

Comprehensive verification of:
1. Multi-Vintage Isolation (issue_date in primary key, old vintages never deleted/overwritten)
2. Operational Parameter Restriction (Dasarian: pb20, pa150, pa200, pa300; Monthly: pa300, pa400, pa500)
3. Deterministic Batch Size (52 stations x 4 parameters = 208 rows per dasarian target)
4. Multi-Vintage Diff Classification (NEW, NEW VINTAGE, IDENTICAL, UPDATED)
5. Active & Historical Vintage Selection in get_probability_data
6. Protection of 57 Master Stations (52 Manual, 5 ARG Strictly NULL)
7. Operator Consent Gate for UPDATED records (not required for NEW or NEW VINTAGE)
8. Zero Corruption of Baseline cews_rainfall_daily (286,085 rows)
"""

import io
import unittest
import openpyxl
from pathlib import Path
from datetime import datetime, date

from backend.database import get_raw_connection, get_db
from backend.ingestion_service import (
    parse_probability_excel,
    commit_ingestion_session,
    ARG_STATION_IDS,
)
from backend.data_service import get_probability_data

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURE_19_OKT = ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx"
FIXTURE_MONTHLY = ROOT_DIR / "tambahan" / "template_data_input" / "prob" / "bulanan" / "KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx"


class TestMultiVintageEcmwf(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Verify baseline and isolate test target period 2026-11."""
        conn = get_raw_connection()
        cur = conn.cursor()
        
        # 1. Baseline verification
        cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
        row = cur.fetchone()
        cls.baseline_ch = row["total"] if isinstance(row, dict) else row[0]
        assert cls.baseline_ch == 286085, f"Baseline cews_rainfall_daily corrupted! Expected 286085, got {cls.baseline_ch}"

        # 2. Record max id in cews_ingestion_history to clean test batches on teardown
        cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM cews_ingestion_history;")
        h_row = cur.fetchone()
        cls.max_history_id = h_row["max_id"] if isinstance(h_row, dict) else h_row[0]

        # 3. Clean target periods for deterministic multi-vintage test run
        cur.execute("DELETE FROM cews_forecast_snapshot WHERE target_year = 2026 AND target_month = 11;")
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean synthetic test rows, restore genuine BMKG November vintages, and verify baseline."""
        conn = get_raw_connection()
        cur = conn.cursor()

        # 1. Remove synthetic test rows & test history entries
        cur.execute("DELETE FROM cews_forecast_snapshot WHERE target_year = 2026 AND target_month = 11;")
        cur.execute("DELETE FROM cews_ingestion_history WHERE id > %s;", (cls.max_history_id,))
        conn.commit()
        conn.close()

        # 2. Restore genuine BMKG operational fixtures for November 2026 (vintages 09 Oct & 19 Oct)
        real_fixtures = [
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.09_das 1 nov.xlsx",
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx",
            ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 2 nov.xlsx",
        ]
        for rf in real_fixtures:
            if rf.exists():
                p_res = parse_probability_excel(rf.read_bytes(), filename=rf.name, forecast_type="PROBABILITAS_DASARIAN")
                commit_ingestion_session(p_res["staging_token"])

        # 3. Check baseline again
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
        row = cur.fetchone()
        current_ch = row["total"] if isinstance(row, dict) else row[0]
        conn.close()
        assert current_ch == 286085, "Baseline corrupted during tests!"

    # =========================================================================
    # SCENARIO 1: INITIAL INGESTION (VINTAGE 19 OKT 2026) -> NEW = 208
    # =========================================================================
    def test_01_initial_ingestion_vintage_19_oct(self):
        """First upload for target 2026-11-das1 yields NEW=208 and only 4 operational parameters."""
        self.assertTrue(FIXTURE_19_OKT.exists(), f"Fixture missing: {FIXTURE_19_OKT}")
        data_19 = FIXTURE_19_OKT.read_bytes()

        preview = parse_probability_excel(
            data_19,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN"
        )

        self.assertEqual(preview["status"], "SUCCESS")
        summary = preview["summary"]
        self.assertEqual(summary["total_new"], 208, "Harus menghasilkan tepat 208 rekaman NEW (52 stasiun x 4 parameter)")
        self.assertEqual(summary.get("total_new_vintage", 0), 0)
        self.assertEqual(summary["total_updated"], 0)
        self.assertEqual(summary["total_identical"], 0)

        # Check operational parameter restriction (no EnsMean, pb50, pb100, etc.)
        from backend.ingestion_service import _STAGING_SESSIONS
        session_entries = _STAGING_SESSIONS[preview["staging_token"]]["entries"]
        parsed_params = set(e["forecast_parameter"] for e in session_entries)
        
        self.assertEqual(parsed_params, {"pb20", "pa150", "pa200", "pa300"},
                         "Hanya 4 parameter operasional dasarian yang boleh diekstrak")

        # Commit without consent (NEW does not require update consent)
        commit_res = commit_ingestion_session(preview["staging_token"])
        self.assertEqual(commit_res["status"], "COMMITTED")

        # Verify DB rows
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS total FROM cews_forecast_snapshot
            WHERE target_year = 2026 AND target_month = 11 AND target_dasarian = 1 AND issue_date = '2026-10-19';
        """)
        row = cur.fetchone()
        cnt = row["total"] if isinstance(row, dict) else row[0]
        conn.close()
        self.assertEqual(cnt, 208, "DB harus menyimpan tepat 208 rekaman untuk vintage 19 Okt")

    # =========================================================================
    # SCENARIO 2: MULTI-VINTAGE INGESTION (VINTAGE 30 OKT 2026) -> NEW VINTAGE = 208
    # =========================================================================
    def test_02_multi_vintage_ingestion_vintage_30_oct(self):
        """Second upload for same target with new issue date yields NEW VINTAGE=208 without overwrite."""
        data = FIXTURE_19_OKT.read_bytes()

        # Ingest with issue date 2026-10-30
        preview = parse_probability_excel(
            data,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN"
        )

        self.assertEqual(preview["status"], "SUCCESS")
        summary = preview["summary"]
        self.assertEqual(summary.get("total_new_vintage", 0), 208, "Harus menghasilkan tepat 208 rekaman NEW VINTAGE")
        self.assertEqual(summary["total_new"], 0)
        self.assertEqual(summary["total_updated"], 0)
        self.assertEqual(summary["total_identical"], 0)

        # Commit without consent (NEW VINTAGE does not require explicit update consent)
        commit_res = commit_ingestion_session(preview["staging_token"], explicit_update_consent=False)
        self.assertEqual(commit_res["status"], "COMMITTED")

    # =========================================================================
    # SCENARIO 3: DATABASE MULTI-VINTAGE INTEGRITY (416 ROWS TOTAL)
    # =========================================================================
    def test_03_database_multi_vintage_isolation(self):
        """Verify DB stores both vintages concurrently (total 416 rows) without data deletion."""
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT issue_date, COUNT(*) as cnt 
            FROM cews_forecast_snapshot 
            WHERE target_year = 2026 AND target_month = 11 AND target_dasarian = 1 
            GROUP BY issue_date 
            ORDER BY issue_date;
        """)
        rows = cur.fetchall()
        conn.close()

        vintages = {r["issue_date"].strftime("%Y-%m-%d"): r["cnt"] for r in rows}
        self.assertEqual(len(vintages), 2, "Harus terdapat 2 vintage independen di database")
        self.assertEqual(vintages.get("2026-10-19"), 208, "Vintage 19 Okt harus memiliki tepat 208 rows")
        self.assertEqual(vintages.get("2026-10-30"), 208, "Vintage 30 Okt harus memiliki tepat 208 rows")
        self.assertEqual(sum(vintages.values()), 416, "Total baris kedua vintage harus tepat 416")

    # =========================================================================
    # SCENARIO 4: ACTIVE VINTAGE RETRIEVAL (LATEST BY DEFAULT)
    # =========================================================================
    def test_04_active_vintage_retrieval(self):
        """get_probability_data defaults to active vintage (2026-10-30) and returns 57 stations (5 ARG NULL)."""
        res = get_probability_data(period_id="2026-11-das1")
        meta = res.get("meta", {})

        self.assertEqual(meta.get("active_vintage_issue"), "2026-10-30", "Active vintage harus 2026-10-30 (terbaru)")
        self.assertIn("2026-10-30", meta.get("available_vintages", []))
        self.assertIn("2026-10-19", meta.get("available_vintages", []))

        items = res.get("data", [])
        self.assertEqual(len(items), 57, "Harus mengembalikan seluruh 57 stasiun master")

        manual_items = [i for i in items if i["station_id"] not in ARG_STATION_IDS]
        arg_items = [i for i in items if i["station_id"] in ARG_STATION_IDS]

        self.assertEqual(len(manual_items), 52)
        self.assertEqual(len(arg_items), 5)

        # 52 manual stations must have non-null operational values
        for item in manual_items:
            self.assertIsNotNone(item.get("prob_below20"))
            self.assertIsNotNone(item.get("prob_above150"))
            self.assertIsNotNone(item.get("prob_above200"))
            self.assertIsNotNone(item.get("prob_above300"))

        # 5 ARG stations must be strictly NULL
        for item in arg_items:
            self.assertIsNone(item.get("prob_below20"), f"ARG {item['station_id']} must have prob_below20=None")
            self.assertIsNone(item.get("prob_above150"), f"ARG {item['station_id']} must have prob_above150=None")
            self.assertIsNone(item.get("prob_above200"), f"ARG {item['station_id']} must have prob_above200=None")
            self.assertIsNone(item.get("prob_above300"), f"ARG {item['station_id']} must have prob_above300=None")

    # =========================================================================
    # SCENARIO 5: HISTORICAL VINTAGE RETRIEVAL (19 OKT 2026)
    # =========================================================================
    def test_05_historical_vintage_retrieval(self):
        """get_probability_data with issue_date='2026-10-19' retrieves historical vintage accurately."""
        res = get_probability_data(period_id="2026-11-das1", issue_date="2026-10-19")
        meta = res.get("meta", {})

        self.assertEqual(meta.get("active_vintage_issue"), "2026-10-19", "Harus mengembalikan metadata issue 2026-10-19")
        items = res.get("data", [])
        self.assertEqual(len(items), 57, "Tetap mengembalikan 57 stasiun master")

        # 5 ARG stations strictly NULL
        arg_items = [i for i in items if i["station_id"] in ARG_STATION_IDS]
        self.assertEqual(len(arg_items), 5)
        for item in arg_items:
            self.assertIsNone(item.get("prob_below20"))
            self.assertIsNone(item.get("prob_above150"))

    # =========================================================================
    # SCENARIO 6: IDEMPOTENT RE-INGESTION OF SAME VINTAGE
    # =========================================================================
    def test_06_idempotent_reingestion_same_vintage(self):
        """Re-uploading vintage 30 Okt yields IDENTICAL=208, NEW=0, UPDATED=0, NEW VINTAGE=0."""
        data = FIXTURE_19_OKT.read_bytes()

        preview = parse_probability_excel(
            data,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN"
        )

        self.assertEqual(preview["status"], "SUCCESS")
        summary = preview["summary"]
        self.assertEqual(summary["total_identical"], 208, "Harus menghasilkan tepat 208 rekaman IDENTICAL")
        self.assertEqual(summary["total_new"], 0)
        self.assertEqual(summary.get("total_new_vintage", 0), 0)
        self.assertEqual(summary["total_updated"], 0)

        # Committing identical records skips DB writes and maintains row count
        commit_res = commit_ingestion_session(preview["staging_token"])
        self.assertEqual(commit_res["status"], "COMMITTED")

        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM cews_forecast_snapshot WHERE target_year = 2026 AND target_month = 11 AND target_dasarian = 1;")
        row = cur.fetchone()
        conn.close()
        total_cnt = row["total"] if isinstance(row, dict) else row[0]
        self.assertEqual(total_cnt, 416, "Total baris di DB tidak boleh bertambah saat re-upload identik")

    # =========================================================================
    # SCENARIO 7: VINTAGE UPDATE WITH DIFFERENT VALUES & CONSENT GATE
    # =========================================================================
    def test_07_vintage_update_with_different_values_and_consent(self):
        """Re-uploading same vintage with modified value (> 1e-4) yields UPDATED and requires consent."""
        wb = openpyxl.load_workbook(FIXTURE_19_OKT)
        ws = wb["pb20"]
        # Modify row 2 column 8 (first period column for first station)
        orig_val = ws.cell(row=2, column=8).value
        new_test_val = 88.5 if orig_val != 88.5 else 92.0
        ws.cell(row=2, column=8, value=new_test_val)

        buf = io.BytesIO()
        wb.save(buf)
        modified_bytes = buf.getvalue()
        wb.close()

        preview = parse_probability_excel(
            modified_bytes,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.30_das 1 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN"
        )

        self.assertEqual(preview["status"], "SUCCESS")
        summary = preview["summary"]
        self.assertGreaterEqual(summary["total_updated"], 1, "Harus mendeteksi minimal 1 rekaman UPDATED")
        self.assertEqual(summary["total_new"], 0)
        self.assertEqual(summary.get("total_new_vintage", 0), 0)

        # 1. Attempt commit without consent -> MUST fail with ValueError
        with self.assertRaises(ValueError) as ctx:
            commit_ingestion_session(preview["staging_token"], explicit_update_consent=False)
        self.assertIn("memerlukan izin eksplisit dari petugas", str(ctx.exception))

        # 2. Commit with consent -> MUST succeed
        commit_res = commit_ingestion_session(preview["staging_token"], explicit_update_consent=True)
        self.assertEqual(commit_res["status"], "COMMITTED")

    # =========================================================================
    # SCENARIO 8: OPERATIONAL PARAMETER RESTRICTION (MONTHLY)
    # =========================================================================
    def test_08_monthly_parameter_restriction(self):
        """Monthly probability parser restricts extraction strictly to pa300, pa400, pa500."""
        self.assertTrue(FIXTURE_MONTHLY.exists(), f"Monthly fixture missing: {FIXTURE_MONTHLY}")
        data_monthly = FIXTURE_MONTHLY.read_bytes()

        preview = parse_probability_excel(
            data_monthly,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx",
            forecast_type="PROBABILITAS_BULANAN"
        )

        self.assertEqual(preview["status"], "SUCCESS")
        from backend.ingestion_service import _STAGING_SESSIONS
        session_entries = _STAGING_SESSIONS[preview["staging_token"]]["entries"]
        parsed_params = set(e["forecast_parameter"] for e in session_entries)
        
        self.assertEqual(parsed_params, {"pa300", "pa400", "pa500"},
                         "Hanya 3 parameter operasional bulanan yang boleh diekstrak (pa300, pa400, pa500)")

    # =========================================================================
    # SCENARIO 9: MULTI-PERIOD INGESTION (DAS I, II, III NOVEMBER 2026)
    # =========================================================================
    def test_09_multi_period_november_3_dasarians(self):
        """
        File with 3 target periods (NovI, NovII, NovIII) recognizes all 3,
        stores them on their respective targets without mixing, and makes them
        selectable in the dashboard period selector.
        """
        wb = openpyxl.load_workbook(FIXTURE_19_OKT)
        for s_name in ["pb20", "pa150", "pa200", "pa300"]:
            ws = wb[s_name]
            ws.cell(row=1, column=8, value="NovI")
            ws.cell(row=1, column=9, value="NovII")
            ws.cell(row=1, column=10, value="NovIII")
            for r_idx in range(2, ws.max_row + 1):
                base_v = ws.cell(row=r_idx, column=8).value
                v_num = float(base_v) if base_v is not None else 10.0
                ws.cell(row=r_idx, column=9, value=min(100.0, round(v_num + 5.0, 2)))
                ws.cell(row=r_idx, column=10, value=min(100.0, round(v_num + 10.0, 2)))

        buf = io.BytesIO()
        wb.save(buf)
        multi_bytes = buf.getvalue()
        wb.close()

        preview = parse_probability_excel(
            multi_bytes,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.31_das 1-3 nov.xlsx",
            forecast_type="PROBABILITAS_DASARIAN"
        )
        self.assertEqual(preview["status"], "SUCCESS")
        pids = [p["period_id"] for p in preview["summary"]["periods_detected"]]
        self.assertEqual(pids, ["2026-11-das1", "2026-11-das2", "2026-11-das3"],
                         "Ketiga periode target November harus dikenali secara terpisah")

        # 2026-11-das1 already has vintages -> 208 NEW VINTAGE; das2 and das3 are brand new -> 416 NEW
        self.assertEqual(preview["summary"]["total_new_vintage"], 208)
        self.assertEqual(preview["summary"]["total_new"], 416)

        commit_res = commit_ingestion_session(preview["staging_token"])
        self.assertEqual(commit_res["status"], "COMMITTED")

        # Verify each period is queryable and distinct in get_probability_data
        r_das1 = get_probability_data(period_id="2026-11-das1")
        r_das2 = get_probability_data(period_id="2026-11-das2")
        r_das3 = get_probability_data(period_id="2026-11-das3")

        self.assertEqual(r_das1["meta"]["active_vintage_issue"], "2026-10-31")
        self.assertEqual(r_das2["meta"]["active_vintage_issue"], "2026-10-31")
        self.assertEqual(r_das3["meta"]["active_vintage_issue"], "2026-10-31")
        self.assertEqual(r_das2["meta"]["available_stations_count"], 52)
        self.assertEqual(r_das3["meta"]["available_stations_count"], 52)

    # =========================================================================
    # SCENARIO 10: RESOLUTION ISOLATION (pa300 DASARIAN VS BULANAN)
    # =========================================================================
    def test_10_resolution_isolation_pa300_dasarian_vs_bulanan(self):
        """
        Verify pa300 Dasarian and pa300 Bulanan are strictly isolated by forecast_resolution
        even when sharing target_year=2026, target_month=11, target_dasarian=1, issue_date='2026-10-31'.
        """
        # Create a monthly forecast for Nov 2026 with issue_date 2026-10-31 and distinct pa300=77.0
        wb = openpyxl.load_workbook(FIXTURE_MONTHLY)
        for s_name in ["pa300", "pa400", "pa500"]:
            if s_name in wb.sheetnames:
                ws = wb[s_name]
                # Keep only 1 period column 'Nov' at col 8
                for c_del in range(ws.max_column, 8, -1):
                    ws.delete_cols(c_del)
                ws.cell(row=1, column=8, value="Nov")
                for r_idx in range(2, ws.max_row + 1):
                    ws.cell(row=r_idx, column=8, value=77.0 if s_name == "pa300" else 45.0)
        buf = io.BytesIO()
        wb.save(buf)
        m_bytes = buf.getvalue()
        wb.close()

        preview_m = parse_probability_excel(
            m_bytes,
            filename="KEPRI_pch_ecmwf_perpos_ver_2026.10.31_bulanan_nov.xlsx",
            forecast_type="PROBABILITAS_BULANAN"
        )
        self.assertEqual(preview_m["status"], "SUCCESS")
        # Must be classified as NEW (not UPDATED/IDENTICAL against Dasarian!)
        self.assertGreaterEqual(preview_m["summary"]["total_new"], 153)
        self.assertEqual(preview_m["summary"]["total_updated"], 0)
        commit_ingestion_session(preview_m["staging_token"])

        # Query Dasarian vs Bulanan
        res_das = get_probability_data(period_id="2026-11-das1", issue_date="2026-10-31")
        res_bul = get_probability_data(period_id="2026-11", issue_date="2026-10-31")

        self.assertEqual(res_das["meta"]["resolution"], "DASARIAN")
        self.assertEqual(res_bul["meta"]["resolution"], "BULANAN")

        das_manual = [i for i in res_das["data"] if not i["is_arg"]][0]
        bul_manual = [i for i in res_bul["data"] if not i["is_arg"]][0]

        self.assertIsNotNone(das_manual["prob_above300"])
        self.assertIsNone(das_manual["prob_month_above300"])
        self.assertEqual(bul_manual["prob_month_above300"], 77.0)
        self.assertIsNone(bul_manual["prob_above300"])

    # =========================================================================
    # SCENARIO 11: CUTOFF ELIGIBLE VINTAGE & DASHBOARD PERIOD SELECTION
    # =========================================================================
    def test_11_cutoff_eligible_vintage_and_dashboard_periods(self):
        """
        1. Cutoff eligibility: cutoff_date='2026-10-25' selects vintage '2026-10-19' (ignoring 30/31 Oct).
        2. Dashboard periods include 2026-10-das3, 2026-11-das1, 2026-11-das2, 2026-11-das3.
        """
        from backend.period_service import get_10_dasarian_window_items

        res_cutoff = get_probability_data(period_id="2026-11-das1", cutoff_date="2026-10-25")
        self.assertEqual(res_cutoff["meta"]["active_vintage_issue"], "2026-10-19",
                         "Dengan cutoff 2026-10-25, vintage yang dipilih harus 2026-10-19")

        _, _, window_items = get_10_dasarian_window_items()
        window_pids = [w["period_id"] for w in window_items]
        for expected_pid in ["2026-10-das3", "2026-11-das1", "2026-11-das2", "2026-11-das3"]:
            self.assertIn(expected_pid, window_pids, f"Periode {expected_pid} wajib tersedia di selector dashboard")

    # =========================================================================
    # SCENARIO 12: BASELINE CH PROTECTION
    # =========================================================================
    def test_12_baseline_ch_protection(self):
        """cews_rainfall_daily remains exactly 286,085 rows throughout the entire process."""
        conn = get_raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM cews_rainfall_daily;")
        row = cur.fetchone()
        conn.close()
        current_ch = row["total"] if isinstance(row, dict) else row[0]
        self.assertEqual(current_ch, 286085, f"Baseline corrupted! Expected 286085, got {current_ch}")


if __name__ == "__main__":
    unittest.main()
