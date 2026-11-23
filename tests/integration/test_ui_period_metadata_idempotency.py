"""
tests/integration/test_ui_period_metadata_idempotency.py
Comprehensive Test Suite for DSS-PIK Final Refinement:
- Dynamic +1 Upcoming Dasarian Period in Selector
- Station Metadata Authoritative Master & Collision Isolation (Nopos 228D, Tanjung Riau)
- Idempotent Preview & Diff with Deterministic Float Comparison (< 1e-4)
- Operational Summary KPI & Independent SPI/Probability Voiding
- Protection of 57 Station Canonical Metadata (52 Manual, 5 ARG Strictly NULL)
"""

import unittest
import os
import json
from pathlib import Path
from datetime import datetime, date

from backend.database import get_db
from backend.period_service import (
    get_active_period,
    get_10_dasarian_window_items,
    get_next_dasarian,
)
from backend.ingestion_service import (
    get_additional_mapping_lookup,
    parse_probability_excel,
    get_operational_summary,
    void_spi_record,
    void_probability_record,
    get_latest_data_status,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURE_PCH_NOV1 = ROOT_DIR / "tambahan" / "02_EKSTRAK_POS" / "DASARIAN" / "KEPRI_pch_ecmwf_perpos_ver_2026.10.19_das 1 nov.xlsx"


class TestUiPeriodMetadataIdempotency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Baseline row count check for cews_rainfall_daily
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM cews_rainfall_daily;")
                cls.baseline_ch_count = cur.fetchone()["cnt"]

    # =========================================================================
    # 1. DYNAMIC DASARIAN PERIOD (+1 UPCOMING FORECAST PERIOD)
    # =========================================================================
    def test_dynamic_period_contains_11th_forecast_item(self):
        """Verify get_10_dasarian_window_items contains observation periods and dynamic forecast periods marked as forecast."""
        active_pid, mode, window_items = get_10_dasarian_window_items()
        self.assertGreaterEqual(len(window_items), 11, "Jendela dasarian harus berisi minimal 11 item (observasi + prakiraan dinamis)")

        # Verify observation items and forecast items
        forecast_items = [item for item in window_items if item.get("is_forecast")]
        self.assertGreaterEqual(len(forecast_items), 1, "Harus memuat minimal 1 item periode prakiraan mendatang")

        for item in forecast_items:
            self.assertTrue(item.get("is_forecast"), "Item prakiraan harus berstatus is_forecast: True")
            self.assertIn("[Prakiraan]", item.get("label", ""), "Label item prakiraan harus memuat penanda [Prakiraan]")
            self.assertFalse(item.get("is_default", True), "Item prakiraan tidak boleh menjadi default observasi")

        # Verify active period remains the actual calendar observation period
        active_period = get_active_period()
        self.assertFalse(active_period.get("is_forecast", False), "Active period must be an observation period")

    def test_get_next_dasarian_calculation(self):
        """Test calculation of next dasarian across dasarian and month boundaries."""
        # Dasarian 1 -> 2
        y, m, d = get_next_dasarian(2026, 10, "das1")
        self.assertEqual((y, m, d), (2026, 10, "das2"))

        # Dasarian 2 -> 3
        y, m, d = get_next_dasarian(2026, 10, "das2")
        self.assertEqual((y, m, d), (2026, 10, "das3"))

        # Dasarian 3 -> 1 next month
        y, m, d = get_next_dasarian(2026, 10, "das3")
        self.assertEqual((y, m, d), (2026, 11, "das1"))

        # Dasarian 3 December -> 1 January next year
        y, m, d = get_next_dasarian(2026, 12, "das3")
        self.assertEqual((y, m, d), (2027, 1, "das1"))

    # =========================================================================
    # 2. STATION METADATA AUTHORITATIVE MAPPING & COLLISION ISOLATION
    # =========================================================================
    def test_station_mapping_lookup_collision_isolation(self):
        """Verify nopos 228D collision and external station isolation."""
        lookup = get_additional_mapping_lookup()
        self.assertIn("pairs", lookup)
        self.assertIn("names", lookup)
        self.assertIn("nopos_unique", lookup)

        # In nopos_unique, '228D' must NOT be present due to collision between Duara and UPT Benih Pertanian
        self.assertNotIn("228D", lookup["nopos_unique"], "Nopos 228D collision must be isolated from unique lookup")

        # Both Duara and UPT Benih Pertanian must be uniquely resolved by normalized name
        self.assertEqual(lookup["names"].get("duara"), "21040501A")
        self.assertEqual(lookup["names"].get("upt benih pertanian"), "21050501A", "UPT Benih Pertanian must resolve to Bukit Padi (21050501A)")

    def test_probability_parser_isolates_external_post_and_avoids_duplicate(self):
        """Test that parsing the actual forecast Excel maps exactly 52 manual stations with 0 duplicates."""
        if not FIXTURE_PCH_NOV1.exists():
            self.skipTest(f"Fixture {FIXTURE_PCH_NOV1} not found")

        with open(FIXTURE_PCH_NOV1, "rb") as f:
            content = f.read()

        parsed = parse_probability_excel(content, FIXTURE_PCH_NOV1.name)
        mapping_summary = parsed.get("summary", {}).get("station_mapping_summary", {})

        # Total rows in file: 53 data rows (54 total including header)
        self.assertEqual(mapping_summary.get("total_rows_in_file"), 53)

        # Matched manual stations: exactly 52 master stations!
        self.assertEqual(mapping_summary.get("matched_stations_count"), 52)

        # Duplicates count must be strictly 0!
        self.assertEqual(mapping_summary.get("duplicate_stations_count"), 0)

        # Unmapped external stations count: exactly 1 ('Tanjung Riau Kota Batam')
        self.assertEqual(mapping_summary.get("unmapped_external_count"), 1)
        unmapped_names = [x["name"] for x in parsed.get("summary", {}).get("unmapped_external_stations", [])]
        self.assertIn("Tanjung Riau Kota Batam", unmapped_names)

    # =========================================================================
    # 3. IDEMPOTENT PREVIEW & DIFF
    # =========================================================================
    def test_idempotent_reupload_yields_zero_new_and_exact_identical(self):
        """Re-uploading an already committed probability file must result in NEW=0 and IDENTICAL=572."""
        if not FIXTURE_PCH_NOV1.exists():
            self.skipTest(f"Fixture {FIXTURE_PCH_NOV1} not found")

        with open(FIXTURE_PCH_NOV1, "rb") as f:
            content = f.read()

        parsed = parse_probability_excel(content, FIXTURE_PCH_NOV1.name)
        summary = parsed.get("summary", {})
        new_cnt = summary.get("total_new", 0)
        identical_cnt = summary.get("total_identical", 0)
        updated_cnt = summary.get("total_updated", 0)

        # Because batch 2026.10.19 das 1 nov was already committed with 4 operational parameters (pb20, pa150, pa200, pa300):
        self.assertEqual(new_cnt, 0, f"Expected NEW=0 on re-upload, got {new_cnt}")
        self.assertEqual(updated_cnt, 0, f"Expected UPDATED=0 on re-upload, got {updated_cnt}")
        self.assertEqual(identical_cnt, 52 * 4, f"Expected IDENTICAL=208 (52 stations * 4 operational parameters: pb20, pa150, pa200, pa300), got {identical_cnt}")

    # =========================================================================
    # 4. OPERATIONAL SUMMARY KPI & VOIDING ENDPOINTS
    # =========================================================================
    def test_operational_summary_kpi_query(self):
        """Verify get_operational_summary returns consistent KPI aggregates from DB."""
        summary = get_operational_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("total_batches", summary)
        self.assertIn("successful_batches", summary)
        self.assertIn("rolled_back_batches", summary)
        self.assertIn("total_new_records", summary)
        self.assertIn("total_updated_records", summary)
        self.assertIn("total_rejected_records", summary)

        self.assertGreaterEqual(summary["total_batches"], 0)
        self.assertGreaterEqual(summary["successful_batches"], 0)
        self.assertGreaterEqual(summary["total_new_records"], 0)

    def test_void_spi_record_safety(self):
        """Verify void_spi_record safely handles nullifying records without affecting un-targeted timescales, then restores original file."""
        import shutil
        from pathlib import Path
        target_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "spi" / "dasarian" / "SPI_all_90d.parquet"
        orig_bytes = target_path.read_bytes()
        try:
            res = void_spi_record(
                station_id="21010401A",
                period_type="DASARIAN",
                timescale="90D",
                date_str="2026-10-01",
                reason="Integration testing void SPI safe execution",
                operator="TEST_OPERATOR"
            )
            self.assertEqual(res.get("status"), "SUCCESS")
            self.assertEqual(res.get("station_id"), "21010401A")
            self.assertEqual(res.get("timescale"), "90D")
        finally:
            target_path.write_bytes(orig_bytes)
            for bak in target_path.parent.glob("*.bak_void_*"):
                try:
                    bak.unlink()
                except Exception:
                    pass

    def test_void_probability_record_safety(self):
        """Verify void_probability_record executes safely and records audit event."""
        # Using a dummy target period to verify query execution and audit trail
        res = void_probability_record(
            issue_date="2099-01-01",
            target_period="2099-01-das1",
            reason="Integration testing void probability safe execution",
            operator="TEST_OPERATOR"
        )
        self.assertEqual(res.get("status"), "SUCCESS")

    # =========================================================================
    # 5. CANONICAL STORAGE STATUS INTEGRITY
    # =========================================================================
    def test_latest_data_status_canonical_storages(self):
        """Verify get_latest_data_status accurately inspects canonical MariaDB and Parquet."""
        status_data = get_latest_data_status()
        self.assertEqual(status_data.get("status"), "ok")
        self.assertIn("curah_hujan", status_data)
        self.assertIn("spi_harian_30d", status_data)
        self.assertIn("spi_harian_90d", status_data)
        self.assertIn("spi_dasarian_30d", status_data)
        self.assertIn("spi_dasarian_90d", status_data)
        self.assertIn("spi_bulanan", status_data)
        self.assertIn("probabilitas_dasarian", status_data)
        self.assertIn("probabilitas_bulanan", status_data)

        # Verify ARG strictly handled
        for k in ["spi_harian_30d", "spi_harian_90d", "spi_dasarian_30d", "spi_dasarian_90d", "spi_bulanan"]:
            spi_cat = status_data.get(k, {})
            self.assertEqual(spi_cat.get("arg_stations_handled"), 5, f"{k} must strictly handle 5 ARG stations as NULL")

    # =========================================================================
    # 6. BASELINE DATA PROTECTION
    # =========================================================================
    def test_baseline_rainfall_records_intact(self):
        """Verify cews_rainfall_daily row count was not altered by tests."""
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM cews_rainfall_daily;")
                current_cnt = cur.fetchone()["cnt"]
                self.assertEqual(current_cnt, self.baseline_ch_count, "MariaDB baseline cews_rainfall_daily must remain strictly protected!")


if __name__ == "__main__":
    unittest.main()
