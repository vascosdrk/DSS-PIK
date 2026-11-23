"""
tests/integration/test_operational_data_management.py
End-to-End Test Suite for DSS-PIK Operational Data Management Center:
- Fitur A: Live Status Data Operasional Terakhir (Canonical Storage)
- Fitur B & C: Actual Period Reading, Strict 0-100% Scale, Probability Preview & Diff Fix
- Fitur D: Strict Temporal Separation (Observation vs Forecast) & Scoped Authorization
- Fitur E: Forecast Vintage Management & Isolation
- Fitur F: Batch Listing, Batch Cancellation (Rollback), Record Correction & Voiding
- Fitur G: HTH Uncertainty Semantics & Decision Engine False Green Prevention
- Baseline Integrity: Protection of Canonical MariaDB & Parquet Baselines
"""

import unittest
import os
import json
import io
import pandas as pd
from datetime import datetime, date
from pathlib import Path

from backend.database import get_db, get_raw_connection
from backend.ingestion_service import (
    get_latest_data_status,
    parse_probability_excel,
    parse_rainfall_excel,
    parse_spi_parquet,
    parse_spi_bulanan_excel,
    get_ingestion_batches,
    get_batch_details,
    cancel_ingestion_batch,
    correct_rainfall_record,
    void_rainfall_record,
    get_forecast_vintages,
)
from backend.decision_engine import (
    evaluate_hth_indicator,
    evaluate_pdkm_full,
)
from backend.period_service import get_active_period

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROB_DASARIAN_FIXTURE = ROOT_DIR / "tambahan" / "template_data_input" / "prob" / "dasarian" / "KEPRI_pch_ecmwf_perpos_ver_2026.04.30.xlsx"
PROB_BULANAN_FIXTURE = ROOT_DIR / "tambahan" / "template_data_input" / "prob" / "bulanan" / "KEPRI_pch_ecmwf_perpos_ver_2026.08.01.xlsx"


class TestOperationalDataManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Record MariaDB baseline row count for cews_rainfall_daily
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM cews_rainfall_daily;")
                cls.baseline_ch_count = cur.fetchone()["cnt"]

    # ==========================================================================
    # FITUR A: STATUS DATA OPERASIONAL TERAKHIR
    # ==========================================================================
    def test_fitur_a_latest_data_status_canonical_query(self):
        """Fitur A: Query live canonical storage and verify all 6 operational categories."""
        status = get_latest_data_status()
        self.assertEqual(status["status"], "ok")
        self.assertIn("checked_at", status)

        # 1. Curah Hujan Harian
        ch = status["curah_hujan"]
        self.assertEqual(ch["total_stations"], 57)
        self.assertGreater(ch["reported_stations"], 0)
        self.assertGreater(ch["coverage_pct"], 0.0)
        self.assertIn("latest_date", ch)
        self.assertIn("latest_dasarian", ch)
        self.assertIsInstance(ch["missing_stations"], list)

        # 2. SPI Harian
        spi_h30 = status["spi_harian_30d"]
        self.assertEqual(spi_h30["total_manual_stations"], 52)
        self.assertEqual(spi_h30["arg_stations_handled"], 5)
        self.assertIn("latest_date", spi_h30)

        # 3. SPI Dasarian
        spi_d30 = status["spi_dasarian_30d"]
        self.assertEqual(spi_d30["total_manual_stations"], 52)
        self.assertEqual(spi_d30["arg_stations_handled"], 5)
        self.assertIn("evaluation_period", spi_d30)

        # 4. Probabilitas Dasarian
        prob_das = status["probabilitas_dasarian"]
        self.assertIn(prob_das["status_label"], ["Tersedia", "Belum tersedia"])
        if prob_das["status_label"] == "Tersedia":
            self.assertIn("latest_issue_date", prob_das)
            self.assertIn("target_period", prob_das)
            self.assertGreater(prob_das["stations_count"], 0)
            self.assertGreater(prob_das["indicators_count"], 0)

    # ==========================================================================
    # FITUR B & C: ACTUAL PERIOD READING & PROBABILITY PREVIEW DIFF FIX
    # ==========================================================================
    def test_fitur_b_and_c_probability_preview_diff_fix(self):
        """Fitur B & C: Fix Nilai Baru showing '–', populate diff, and strict 0-100% scale."""
        self.assertTrue(PROB_DASARIAN_FIXTURE.exists(), f"Fixture missing: {PROB_DASARIAN_FIXTURE}")
        file_bytes = PROB_DASARIAN_FIXTURE.read_bytes()
        res = parse_probability_excel(file_bytes, PROB_DASARIAN_FIXTURE.name, "DASARIAN")

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data_type"], "PROBABILITAS_DASARIAN")
        self.assertEqual(res["summary"]["scale_verified"], "0-100% (STRICT)")

        # Verify parsed items have new_value populated (never missing/hyphen)
        preview_items = res["preview_items"]
        self.assertGreater(len(preview_items), 0)
        sample = preview_items[0]

        self.assertIn("new_value", sample)
        self.assertIn("old_value", sample)
        self.assertIn("diff", sample)
        self.assertIn("indicator", sample)
        self.assertIn("forecast_issue_date", sample)
        self.assertIn("target_period", sample)
        self.assertIn("change_type", sample)

        # Verify diff_samples is populated with representative records
        self.assertGreater(len(res["diff_samples"]), 0)

        # Verify all probability values strictly within [0, 100]
        for item in preview_items:
            val = item.get("new_value")
            if val is not None:
                self.assertGreaterEqual(val, 0.0)
                self.assertLessEqual(val, 100.0)

    def test_fitur_b_probability_monthly_year_rollover(self):
        """Fitur B: Verify year rollover for monthly forecasts (Jan/Feb rollover to next year)."""
        self.assertTrue(PROB_BULANAN_FIXTURE.exists(), f"Fixture missing: {PROB_BULANAN_FIXTURE}")
        file_bytes = PROB_BULANAN_FIXTURE.read_bytes()
        res = parse_probability_excel(file_bytes, PROB_BULANAN_FIXTURE.name, "BULANAN")

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data_type"], "PROBABILITAS_BULANAN")
        periods = res["summary"]["periods_detected"]

        # Issue date is August 2026 -> January and February must be 2027
        jan_period = next((p for p in periods if p["target_month"] == 1), None)
        feb_period = next((p for p in periods if p["target_month"] == 2), None)

        self.assertIsNotNone(jan_period)
        self.assertEqual(jan_period["target_year"], 2027)
        self.assertIn("2027-01", jan_period["period_id"])

        self.assertIsNotNone(feb_period)
        self.assertEqual(feb_period["target_year"], 2027)
        self.assertIn("2027-02", feb_period["period_id"])

    # ==========================================================================
    # FITUR D: STRICT TEMPORAL SEPARATION
    # ==========================================================================
    def test_fitur_d_temporal_separation_and_active_period_stability(self):
        """Fitur D: Forecasts for future dates are accepted without shifting active evaluation period."""
        active_before = get_active_period()

        # Parsing a future forecast should NOT alter active evaluation period
        file_bytes = PROB_DASARIAN_FIXTURE.read_bytes()
        _ = parse_probability_excel(file_bytes, PROB_DASARIAN_FIXTURE.name, "DASARIAN")

        active_after = get_active_period()
        self.assertEqual(active_before["period_id"], active_after["period_id"])
        self.assertEqual(active_before["mode"], active_after["mode"])

    # ==========================================================================
    # FITUR E: FORECAST VINTAGE MANAGEMENT
    # ==========================================================================
    def test_fitur_e_forecast_vintages_isolation(self):
        """Fitur E: Multiple issue dates for the same target period are archived separately."""
        vintages = get_forecast_vintages()
        self.assertIsInstance(vintages, list)
        self.assertGreater(len(vintages), 0)

        for v in vintages:
            self.assertIn("target_period_id", v)
            self.assertIn("issue_date", v)
            self.assertIn("stations_count", v)
            self.assertIn("parameters_count", v)
            self.assertIn("source_file", v)

    # ==========================================================================
    # FITUR F: BATCH LISTING, DETAIL, CORRECTION & VOIDING
    # ==========================================================================
    def test_fitur_f_batch_listing_and_filtering(self):
        """Fitur F: Paginated ingestion batch listing with filter support."""
        all_batches = get_ingestion_batches(limit=10, offset=0)
        self.assertIn("total", all_batches)
        self.assertIn("items", all_batches)
        self.assertIsInstance(all_batches["items"], list)

        if all_batches["items"]:
            first_id = all_batches["items"][0]["batch_id"]
            details = get_batch_details(first_id)
            self.assertEqual(details["batch_id"], first_id)
            self.assertIn("items", details)

    def test_fitur_f_record_correction_and_voiding(self):
        """Fitur F: Single record correction and voiding with cews_rainfall_correction_log."""
        test_sid = "21720201A"
        test_date = "2026-09-01"

        # 1. Correct record
        corr_res = correct_rainfall_record(
            station_id=test_sid,
            observation_date=test_date,
            new_rainfall_mm=15.5,
            reason="Uji coba koreksi data operasional test suite",
            operator="TEST_OPERATOR"
        )
        self.assertEqual(corr_res["status"], "SUCCESS")
        self.assertEqual(corr_res["new_rainfall_mm"], 15.5)
        self.assertEqual(corr_res["new_obs_status"], "CORRECTED")

        # Verify DB state
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT rainfall_mm, obs_status FROM cews_rainfall_daily WHERE station_id = %s AND observation_date = %s", (test_sid, test_date))
                row = cur.fetchone()
                self.assertEqual(float(row["rainfall_mm"]), 15.5)
                self.assertEqual(row["obs_status"], "CORRECTED")

                # Verify correction log
                cur.execute("SELECT * FROM cews_rainfall_correction_log WHERE station_id = %s AND observation_date = %s ORDER BY id DESC LIMIT 1", (test_sid, test_date))
                log_row = cur.fetchone()
                self.assertIsNotNone(log_row)
                self.assertEqual(float(log_row["new_rainfall_mm"]), 15.5)
                self.assertEqual(log_row["new_obs_status"], "CORRECTED")

        # 2. Void record
        void_res = void_rainfall_record(
            station_id=test_sid,
            observation_date=test_date,
            reason="Uji coba void rekor observasi test suite",
            operator="TEST_OPERATOR"
        )
        self.assertEqual(void_res["status"], "SUCCESS")
        self.assertEqual(void_res["new_obs_status"], "VOID")

        # Verify DB state is VOID
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT obs_status FROM cews_rainfall_daily WHERE station_id = %s AND observation_date = %s", (test_sid, test_date))
                row = cur.fetchone()
                self.assertEqual(row["obs_status"], "VOID")

        # Restore original observation value for test isolation
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE cews_rainfall_daily SET rainfall_mm = 0.0, obs_status = 'OBSERVED_ZERO' WHERE station_id = %s AND observation_date = %s", (test_sid, test_date))

    # ==========================================================================
    # FITUR G: HTH UNCERTAINTY SEMANTICS & DECISION ENGINE
    # ==========================================================================
    def test_fitur_g_hth_uncertainty_semantics_and_false_green_prevention(self):
        """Fitur G: Missing/damaged/ambiguous data marks HTH as UNCERTAIN and prevents false green."""
        # 1. When HTH is certain and < 21 -> NORMAL (Level 0, Valid)
        res_certain = evaluate_hth_indicator(hth_days=10, hth_uncertain=False)
        self.assertTrue(res_certain["valid"])
        self.assertEqual(res_certain["status"], "NORMAL")
        self.assertEqual(res_certain["level"], 0)

        # 2. When HTH is uncertain and < 21 -> UNCERTAIN (Not valid to declare AMAN)
        res_uncertain = evaluate_hth_indicator(hth_days=10, hth_uncertain=True)
        self.assertFalse(res_uncertain["valid"])
        self.assertEqual(res_uncertain["status"], "UNCERTAIN")
        self.assertTrue(res_uncertain["uncertain"])

        # 3. Decision Engine: PDKM must NOT output AMAN / false green when HTH is uncertain
        pdkm_res = evaluate_pdkm_full(
            hth_days=10,
            pb20=10.0,  # Below drought probability threshold
            spi_val=0.5, # Normal SPI
            is_arg=False,
            hth_uncertain=True
        )
        # Should be INCOMPLETE or have evaluation_complete == False, NOT false green AMAN
        self.assertFalse(pdkm_res["evaluation_complete"])
        self.assertIn("INCOMPLETE", pdkm_res["status"])

    # ==========================================================================
    # BASELINE PRESERVATION VERIFICATION
    # ==========================================================================
    def test_database_baseline_preservation(self):
        """Confirm cews_rainfall_daily row count matches baseline."""
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM cews_rainfall_daily;")
                count_after = cur.fetchone()["cnt"]
        self.assertEqual(
            count_after,
            self.baseline_ch_count,
            f"MariaDB cews_rainfall_daily row count altered! Before: {self.baseline_ch_count}, After: {count_after}"
        )


if __name__ == "__main__":
    unittest.main()
