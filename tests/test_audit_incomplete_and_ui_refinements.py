"""
tests/test_audit_incomplete_and_ui_refinements.py
Comprehensive automated test suite for:
- Bagian 1: 57 Stations Incomplete Audit & Authoritative Decision Engine
- Bagian 2: Map Focus to Kepri on "Total Stasiun" Click
- Bagian 3: Official Map Title Layout & Alignment (PDKM / PDCHT)
- Bagian 4: Kamus Operational Terms Synchronization
- Safety: Database Row Counts & Parquet Baselines
"""

import unittest
import json
import pymysql
import pandas as pd
from pathlib import Path
import sys

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.decision_engine import (
    evaluate_hth_indicator,
    evaluate_prob_low_rain_indicator,
    evaluate_spi_indicator,
    evaluate_pdkm_full,
    evaluate_pdcht_dasarian,
    evaluate_pdcht_monthly,
    evaluate_pdcht_full,
    arbitrate_final_synthesis,
    STATUS_TO_COLOR,
    LEVEL_TO_STATUS
)
from backend.map_generator import generate_official_warning_map


class TestBagian1AuthoritativeDecisionEngine(unittest.TestCase):
    """Bagian 1: Decision engine independent indicator evaluations."""

    def test_hth_indicator_boundaries(self):
        # < 21 -> Level 0 (NORMAL)
        res0 = evaluate_hth_indicator(0)
        self.assertEqual(res0["level"], 0)
        self.assertFalse(res0["triggered"])

        res20 = evaluate_hth_indicator(20)
        self.assertEqual(res20["level"], 0)
        self.assertFalse(res20["triggered"])

        # 21-30 -> Level 1 (WASPADA)
        res21 = evaluate_hth_indicator(21)
        self.assertEqual(res21["level"], 1)
        self.assertEqual(res21["status"], "WASPADA")
        self.assertTrue(res21["triggered"])

        res30 = evaluate_hth_indicator(30)
        self.assertEqual(res30["level"], 1)
        self.assertEqual(res30["status"], "WASPADA")

        # 31-60 -> Level 2 (SIAGA)
        res31 = evaluate_hth_indicator(31)
        self.assertEqual(res31["level"], 2)
        self.assertEqual(res31["status"], "SIAGA")
        self.assertTrue(res31["triggered"])

        res60 = evaluate_hth_indicator(60)
        self.assertEqual(res60["level"], 2)
        self.assertEqual(res60["status"], "SIAGA")

        # >= 61 -> Level 3 (AWAS)
        res61 = evaluate_hth_indicator(61)
        self.assertEqual(res61["level"], 3)
        self.assertEqual(res61["status"], "AWAS")
        self.assertTrue(res61["triggered"])

        res100 = evaluate_hth_indicator(100)
        self.assertEqual(res100["level"], 3)
        self.assertEqual(res100["status"], "AWAS")

        # None -> Invalid, Level 0
        res_none = evaluate_hth_indicator(None)
        self.assertEqual(res_none["level"], 0)
        self.assertFalse(res_none["valid"])

    def test_prob_low_rain_indicator_boundaries(self):
        # <= 70.0% -> Level 0
        self.assertEqual(evaluate_prob_low_rain_indicator(70.0)["level"], 0)
        self.assertEqual(evaluate_prob_low_rain_indicator(50.0)["level"], 0)
        self.assertEqual(evaluate_prob_low_rain_indicator(0.0)["level"], 0)

        # > 70.0% -> Level 1 (WASPADA)
        res70_1 = evaluate_prob_low_rain_indicator(70.1)
        self.assertEqual(res70_1["level"], 1)
        self.assertEqual(res70_1["status"], "WASPADA")
        self.assertTrue(res70_1["triggered"])

        res95 = evaluate_prob_low_rain_indicator(95.0)
        self.assertEqual(res95["level"], 1)
        self.assertEqual(res95["status"], "WASPADA")

        # None -> Invalid
        self.assertFalse(evaluate_prob_low_rain_indicator(None)["valid"])

    def test_spi_indicator_boundaries(self):
        # > -1.00 -> Level 0
        self.assertEqual(evaluate_spi_indicator(0.5)["level"], 0)
        self.assertEqual(evaluate_spi_indicator(-0.99)["level"], 0)

        # -1.50 < SPI <= -1.00 -> Level 1 (WASPADA)
        res_w1 = evaluate_spi_indicator(-1.00)
        self.assertEqual(res_w1["level"], 1)
        self.assertEqual(res_w1["status"], "WASPADA")

        res_w2 = evaluate_spi_indicator(-1.49)
        self.assertEqual(res_w2["level"], 1)
        self.assertEqual(res_w2["status"], "WASPADA")

        # -2.00 < SPI <= -1.50 -> Level 2 (SIAGA)
        res_s1 = evaluate_spi_indicator(-1.50)
        self.assertEqual(res_s1["level"], 2)
        self.assertEqual(res_s1["status"], "SIAGA")

        res_s2 = evaluate_spi_indicator(-1.99)
        self.assertEqual(res_s2["level"], 2)
        self.assertEqual(res_s2["status"], "SIAGA")

        # SPI <= -2.00 -> Level 3 (AWAS)
        res_a1 = evaluate_spi_indicator(-2.00)
        self.assertEqual(res_a1["level"], 3)
        self.assertEqual(res_a1["status"], "AWAS")

        res_a2 = evaluate_spi_indicator(-2.50)
        self.assertEqual(res_a2["level"], 3)
        self.assertEqual(res_a2["status"], "AWAS")

        # None -> Invalid
        self.assertFalse(evaluate_spi_indicator(None)["valid"])

    def test_pdkm_independent_synthesis(self):
        # Only HTH triggers SIAGA (HTH=35, pb20=10, spi=0.0) -> SIAGA
        res1 = evaluate_pdkm_full(hth_days=35, pb20=10.0, spi_val=0.0)
        self.assertEqual(res1["status"], "SIAGA")
        self.assertEqual(res1["level"], 2)
        self.assertTrue(res1["evaluation_complete"])

        # Only pb20 triggers WASPADA (HTH=5, pb20=85.0, spi=0.0) -> WASPADA
        res2 = evaluate_pdkm_full(hth_days=5, pb20=85.0, spi_val=0.0)
        self.assertEqual(res2["status"], "WASPADA")
        self.assertEqual(res2["level"], 1)

        # Only SPI triggers AWAS (HTH=10, pb20=20.0, spi=-2.3) -> AWAS
        res3 = evaluate_pdkm_full(hth_days=10, pb20=20.0, spi_val=-2.3)
        self.assertEqual(res3["status"], "AWAS")
        self.assertEqual(res3["level"], 3)

        # Multiple triggers: max taken, all recorded
        res4 = evaluate_pdkm_full(hth_days=35, pb20=85.0, spi_val=-2.3)
        self.assertEqual(res4["status"], "AWAS")
        self.assertEqual(len(res4["triggered_indicators"]), 3)

    def test_pdkm_incomplete_handling(self):
        # Missing inputs, but HTH triggers SIAGA -> honest partial SIAGA
        res_part = evaluate_pdkm_full(hth_days=35, pb20=None, spi_val=None)
        self.assertEqual(res_part["status"], "SIAGA")
        self.assertFalse(res_part["evaluation_complete"])
        self.assertIn("Evaluasi Parsial", res_part["reasons"])

        # Missing inputs, NO trigger -> INCOMPLETE (cannot blindly assign safe AMAN/HIJAU)
        res_inc = evaluate_pdkm_full(hth_days=5, pb20=None, spi_val=None)
        self.assertEqual(res_inc["status"], "INCOMPLETE")
        self.assertFalse(res_inc["evaluation_complete"])

    def test_arg_station_evaluation_policy(self):
        # ARG station evaluated on HTH alone, valid HTH -> COMPLETE
        res_arg = evaluate_pdkm_full(hth_days=25, pb20=None, spi_val=None, is_arg=True)
        self.assertEqual(res_arg["status"], "WASPADA")
        self.assertTrue(res_arg["evaluation_complete"])

        res_arg_normal = evaluate_pdkm_full(hth_days=5, pb20=None, spi_val=None, is_arg=True)
        self.assertEqual(res_arg_normal["status"], "NORMAL")
        self.assertTrue(res_arg_normal["evaluation_complete"])

    def test_pdcht_evaluation(self):
        # Dasarian pa200 > 70 -> SIAGA
        res_d = evaluate_pdcht_full(pa150=80.0, pa200=75.0, pa300=20.0, pm300=10.0, pm400=5.0, pm500=0.0)
        self.assertEqual(res_d["status"], "SIAGA")
        self.assertEqual(res_d["level"], 2)

        # Monthly pm500 > 70 -> AWAS
        res_m = evaluate_pdcht_full(pa150=10.0, pa200=5.0, pa300=0.0, pm300=80.0, pm400=75.0, pm500=72.0)
        self.assertEqual(res_m["status"], "AWAS")
        self.assertEqual(res_m["level"], 3)

    def test_arbitrate_final_synthesis(self):
        # PDKM SIAGA > PDCHT WASPADA -> DROUGHT SIAGA
        pdkm = evaluate_pdkm_full(hth_days=35, pb20=10.0, spi_val=0.0)
        pdcht = evaluate_pdcht_full(pa150=75.0, pa200=10.0, pa300=0.0, pm300=10.0, pm400=5.0, pm500=0.0)
        synth = arbitrate_final_synthesis(pdkm, pdcht)
        self.assertEqual(synth["final_status"], "SIAGA")
        self.assertEqual(synth["hazard_type"], "DROUGHT")

        # Multi-hazard tie: both WASPADA
        pdkm_w = evaluate_pdkm_full(hth_days=25, pb20=10.0, spi_val=0.0)
        synth_tie = arbitrate_final_synthesis(pdkm_w, pdcht)
        self.assertEqual(synth_tie["final_status"], "WASPADA")
        self.assertEqual(synth_tie["hazard_type"], "MULTI_HAZARD")


class TestBagian1Period202609Das2Data(unittest.TestCase):
    """Bagian 1: Snapshot and MariaDB data for 2026-09-das2."""

    def test_snapshot_file_and_counts(self):
        snap_path = ROOT_DIR / "data" / "processed" / "evaluation" / "snapshots" / "2026-09-das2.json"
        self.assertTrue(snap_path.exists())

        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)

        self.assertEqual(len(snap["items"]), 57)
        summary = snap["summary"]
        self.assertEqual(summary["TOTAL"], 57)
        self.assertEqual(summary["INCOMPLETE"], 0)
        self.assertEqual(summary["AWAS"], 6)
        self.assertEqual(summary["SIAGA"], 16)
        self.assertEqual(summary["WASPADA"], 29)
        self.assertEqual(summary["NORMAL"], 6)

    def test_mariadb_snapshot_table(self):
        conn = pymysql.connect(user='root', password='', host='127.0.0.1', port=3306, database='cews_db')
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cews_period_snapshot WHERE period_id='2026-09-das2'")
            count = cur.fetchone()[0]
            self.assertEqual(count, 57)

            cur.execute("SELECT count(*) FROM cews_period_snapshot WHERE period_id='2026-09-das2' AND evaluation_status='COMPLETE'")
            comp_count = cur.fetchone()[0]
            self.assertEqual(comp_count, 57)

            cur.execute("SELECT count(*) FROM cews_period_snapshot WHERE period_id='2026-09-das2' AND evaluation_status='INCOMPLETE'")
            inc_count = cur.fetchone()[0]
            self.assertEqual(inc_count, 0)
        conn.close()


class TestBagian2MapFocusKepri(unittest.TestCase):
    """Bagian 2: Map focus on 'Total Stasiun' click."""

    def test_map_leaflet_bounds_and_focus_trigger(self):
        map_file = ROOT_DIR / "frontend" / "src" / "components" / "MapLeaflet.jsx"
        content = map_file.read_text(encoding="utf-8")

        # Verify KEPRI_BOUNDS definition
        self.assertIn("-0.65, 103.20", content)
        self.assertIn("4.85, 109.15", content)

        # Verify focusTrigger prop and effect
        self.assertIn("focusTrigger = 0", content)
        self.assertIn("focusTrigger > 0", content)
        self.assertIn("map.fitBounds(KEPRI_BOUNDS", content)

    def test_app_jsx_total_stasiun_click_handler(self):
        app_file = ROOT_DIR / "frontend" / "src" / "App.jsx"
        content = app_file.read_text(encoding="utf-8")

        # Verify mapFocusTrigger state and invocation on cardId === 'ALL'
        self.assertIn("mapFocusTrigger, setMapFocusTrigger", content)
        self.assertIn("if (cardId === 'ALL')", content)
        self.assertIn("setMapFocusTrigger((prev) => prev + 1)", content)
        self.assertIn("focusTrigger={mapFocusTrigger}", content)


class TestBagian3OfficialMapTitleLayout(unittest.TestCase):
    """Bagian 3: Tight, centered, proportional title layout in map generator."""

    def test_map_generator_layout_parameters(self):
        gen_file = ROOT_DIR / "backend" / "map_generator.py"
        content = gen_file.read_text(encoding="utf-8")

        # Bottom-left box clear rectangle
        self.assertIn("draw.rectangle([68, 814, 573, 927]", content)
        # Center x = 318
        self.assertIn("cx = 318", content)
        # 4 exact lines
        self.assertIn("title_line1 = \"PETA PERINGATAN DINI\"", content)
        self.assertIn("KEKERINGAN METEOROLOGIS", content)
        self.assertIn("CURAH HUJAN TINGGI", content)
        self.assertIn("title_line4 = \"PROVINSI KEPULAUAN RIAU\"", content)
        # Line vertical coordinates
        self.assertIn("draw_centered(821, title_line1", content)
        self.assertIn("draw_centered(850, title_line2", content)
        self.assertIn("draw_centered(879, title_line3", content)
        self.assertIn("draw_centered(907, title_line4", content)

    def test_generated_map_files_exist(self):
        maps_dir = ROOT_DIR / "data" / "operational" / "maps"
        png_files = list(maps_dir.glob("*.png"))
        pdf_files = list(maps_dir.glob("*.pdf"))
        self.assertGreater(len(png_files), 0)
        self.assertGreater(len(pdf_files), 0)


class TestBagian4KamusOperationalTerms(unittest.TestCase):
    """Bagian 4: Operational terms in KamusPage.jsx."""

    def test_kamus_terms_synchronized(self):
        kamus_file = ROOT_DIR / "frontend" / "src" / "components" / "KamusPage.jsx"
        content = kamus_file.read_text(encoding="utf-8")

        # Verify independent evaluation principles
        self.assertIn("evaluasi independen 3 indikator", content)
        self.assertIn("status_pdkm = max(level_hth, level_prob, level_spi)", content)
        self.assertIn("status_pdcht = max(level_dasarian, level_bulanan)", content)
        self.assertIn("status_akhir = max(status_pdkm, status_pdcht)", content)

        # Verify SPI 30D authoritative vs SPI 90D companion
        self.assertIn("SPI 30D (Otoritatif) vs SPI 90D (Pendamping)", content)
        self.assertIn("Authoritative Basis", content)
        self.assertIn("Informative Companion", content)

        # Verify ARG policy & no zero-fill
        self.assertIn("Larangan Zero-Fill", content)
        self.assertIn("Larangan Auto-Hijau", content)
        self.assertIn("Evaluasi Parsial yang Jujur", content)
        self.assertIn("Kebijakan Stasiun ARG", content)

        # Verify NO legacy obsolete AND rule remains
        self.assertNotIn("HTH >= 21 DAN pb20 > 70%", content)
        self.assertNotIn("HTH >= 31 DAN pb20 > 70%", content)
        self.assertNotIn("HTH >= 61 DAN pb20 > 70%", content)


class TestSafetyBaselines(unittest.TestCase):
    """Safety: Verify raw datasets were never modified."""

    def test_database_raw_baselines(self):
        conn = pymysql.connect(user='root', password='', host='127.0.0.1', port=3306, database='cews_db')
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cews_rainfall_daily")
            rf_count = cur.fetchone()[0]
            self.assertEqual(rf_count, 286085)

            cur.execute("SELECT count(*) FROM cews_warning_history")
            wh_count = cur.fetchone()[0]
            self.assertEqual(wh_count, 2052)
        conn.close()


if __name__ == "__main__":
    unittest.main()
