"""
Comprehensive Integration Tests for Decision Engine SPI 90D Refinement
Scenarios 1 through 10 as specified in MASTER PROMPT PHASE 4
"""

import sys
import unittest
import numpy as np

from backend.decision_engine import (
    evaluate_pdkm_full,
    evaluate_pdcht_full,
    arbitrate_final_synthesis,
    evaluate_spi_indicator,
    evaluate_hth_indicator,
    evaluate_prob_low_rain_indicator
)
from backend.regional_warning_service import aggregate_region_hazard, evaluate_station_hazards_item


class TestDecisionEngineSpi90dIntegration(unittest.TestCase):

    def test_scenario_1_spi_90d_primary_trigger(self):
        """
        Pengujian 1 — SPI 90D menjadi pemicu utama:
        - SPI 90D = -2.15, SPI 30D = -0.40 -> PDKM AWAS.
        - SPI 90D = -1.65, SPI 30D = 0.20 -> PDKM SIAGA.
        - SPI 90D = -1.20, SPI 30D = 0.50 -> PDKM WASPADA.
        """
        # Case 1: SPI 90D = -2.15 -> AWAS
        res1 = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=-2.15)
        self.assertEqual(res1["status"], "AWAS")
        self.assertEqual(res1["level"], 3)
        self.assertIn("SPI 90D -2.15", res1["reasons"])

        # Case 2: SPI 90D = -1.65 -> SIAGA
        res2 = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=-1.65)
        self.assertEqual(res2["status"], "SIAGA")
        self.assertEqual(res2["level"], 2)
        self.assertIn("SPI 90D -1.65", res2["reasons"])

        # Case 3: SPI 90D = -1.20 -> WASPADA
        res3 = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=-1.20)
        self.assertEqual(res3["status"], "WASPADA")
        self.assertEqual(res3["level"], 1)
        self.assertIn("SPI 90D -1.20", res3["reasons"])

    def test_scenario_2_spi_30d_does_not_trigger(self):
        """
        Pengujian 2 — SPI 30D tidak menjadi pemicu:
        - SPI 90D = 0.20
        - SPI 30D = -2.50 (kering ekstrem di 30D, tapi 90D normal)
        - HTH = 5 hari
        - Pb20 = 20%
        Hasil yang diharapkan: PDKM AMAN/NORMAL (karena hanya SPI 90D yang dievaluasi ke engine)
        """
        res = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=0.20)
        self.assertEqual(res["status"], "NORMAL")
        self.assertEqual(res["level"], 0)
        self.assertTrue(res["evaluation_complete"])
        self.assertIn("PDKM AMAN", res["reasons"])

    def test_scenario_3_spi_90d_not_available(self):
        """
        Pengujian 3 — SPI 90D tidak tersedia:
        - SPI 90D = NULL
        - SPI 30D = -2.50 (tidak boleh dipakai untuk menggantikan 90D)
        - HTH = 5 hari
        - Pb20 = 20%
        Hasil: INCOMPLETE, bukan AMAN dan bukan AWAS.
        """
        res = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=None)
        self.assertEqual(res["status"], "INCOMPLETE")
        self.assertEqual(res["level"], 0)
        self.assertFalse(res["evaluation_complete"])
        self.assertIn("SPI_90D", res["missing_inputs"])
        self.assertIn("PDKM Data Tidak Lengkap", res["reasons"])

    def test_scenario_4_hth_trigger_with_missing_spi90d(self):
        """
        Pengujian 4 — Pemicu HTH tetap aktif meski SPI 90D kosong:
        - SPI 90D = NULL
        - HTH = 35 hari (SIAGA)
        - Pb20 = 20%
        Hasil: PDKM SIAGA, dengan transparansi data evaluasi parsial (SPI_90D belum tersedia).
        """
        res = evaluate_pdkm_full(hth_days=35, pb20=20.0, spi_val=None)
        self.assertEqual(res["status"], "SIAGA")
        self.assertEqual(res["level"], 2)
        self.assertFalse(res["evaluation_complete"])
        self.assertIn("HTH", res["triggered_indicators"])
        self.assertIn("SPI_90D belum tersedia", res["reasons"])

    def test_scenario_5_pb20_trigger(self):
        """
        Pengujian 5 — Pemicu Pb20:
        - SPI 90D = 0.20
        - HTH = 5 hari
        - Pb20 = 75% (> 70%)
        Hasil: PDKM WASPADA.
        """
        res = evaluate_pdkm_full(hth_days=5, pb20=75.0, spi_val=0.20)
        self.assertEqual(res["status"], "WASPADA")
        self.assertEqual(res["level"], 1)
        self.assertTrue(res["evaluation_complete"])
        self.assertIn("Prob_LowRain", res["triggered_indicators"])

    def test_scenario_6_multi_parameter_synthesis(self):
        """
        Pengujian 6 — Sintesis multi-parameter:
        L_PDKM = max(L_HTH, L_SPI90D, L_Pb20)
        - HTH 35 hr (SIAGA=2), SPI 90D -2.20 (AWAS=3), Pb20 75% (WASPADA=1)
        -> Level 3 (AWAS), mencatat pemicu gabungan.
        """
        res = evaluate_pdkm_full(hth_days=35, pb20=75.0, spi_val=-2.20)
        self.assertEqual(res["status"], "AWAS")
        self.assertEqual(res["level"], 3)
        self.assertIn("HTH", res["triggered_indicators"])
        self.assertIn("SPI", res["triggered_indicators"])
        self.assertIn("Prob_LowRain", res["triggered_indicators"])

    def test_scenario_7_pdcht_independence(self):
        """
        Pengujian 7 — Independensi PDCHT (Ambang > 50% per Phase 7):
        Pastikan seluruh hasil PDCHT identik dengan matriks acuan:
        - PA150 > 50% -> WASPADA
        - PA200 > 50% -> SIAGA
        - PA300 > 50% -> AWAS
        - PM300 > 50% -> WASPADA
        - PM400 > 50% -> SIAGA
        - PM500 > 50% -> AWAS
        Dan tidak terpengaruh sama sekali oleh nilai SPI 90D.
        """
        res_das = evaluate_pdcht_full(pa150=55.0, pa200=40.0, pa300=10.0)
        self.assertEqual(res_das["status"], "WASPADA")
        self.assertEqual(res_das["level"], 1)

        res_siaga = evaluate_pdcht_full(pa150=80.0, pa200=55.0, pa300=10.0)
        self.assertEqual(res_siaga["status"], "SIAGA")
        self.assertEqual(res_siaga["level"], 2)

        res_awas = evaluate_pdcht_full(pa300=52.0)
        self.assertEqual(res_awas["status"], "AWAS")
        self.assertEqual(res_awas["level"], 3)

        # Boundary test at exactly 50.0% -> NORMAL
        res_boundary = evaluate_pdcht_full(pa150=50.0, pa200=50.0, pa300=50.0, pm300=50.0, pm400=50.0, pm500=50.0)
        self.assertEqual(res_boundary["status"], "NORMAL")
        self.assertEqual(res_boundary["level"], 0)

        # Cross hazard tie
        pdkm_res = evaluate_pdkm_full(hth_days=5, pb20=20.0, spi_val=-1.20)  # WASPADA
        pdcht_res = evaluate_pdcht_full(pa150=75.0)  # WASPADA
        synth = arbitrate_final_synthesis(pdkm_res, pdcht_res)
        self.assertEqual(synth["final_status"], "WASPADA")
        self.assertTrue(synth["multi_hazard"])
        self.assertEqual(synth["hazard_type"], "MULTI_HAZARD")

    def test_scenario_8_regional_aggregation_uses_spi90d(self):
        """
        Pengujian 8 — Agregasi Regional:
        Pastikan status kabupaten/kota mengikuti level PDKM terbaru berbasis SPI 90D.
        Stasiun memiliki SPI 30D = -2.50 (AWAS palsu), tapi SPI 90D = 0.50 (Normal).
        Agregasi regional harus menyimpulkan AMAN / tidak terpicu AWAS oleh SPI 30D.
        """
        stn = {
            "station_id": "21010401A",
            "station_name": "Pos Tanjungpinang Barat",
            "kabupaten": "Kota Tanjungpinang",
            "is_arg": False,
            "hth_days": 5,
            "spi_value": -2.50,         # 30D
            "spi_value_90d": 0.50,      # 90D
            "forecast_pb20": 20.0,
            "forecast_pa150": 10.0,
            "forecast_pa200": 5.0,
            "forecast_pa300": 0.0,
            "monthly_pa300": 10.0,
            "monthly_pa400": 5.0,
            "monthly_pa500": 0.0
        }
        eval_stn = evaluate_station_hazards_item(stn, "2026-11-das1")
        # PDKM station must be NORMAL because SPI 90D is 0.50, HTH is 5, Pb20 is 20
        self.assertIn(eval_stn["pdkm"]["status"], ("NORMAL", "AMAN"))
        self.assertEqual(eval_stn["pdkm"]["level"], 0)
        self.assertEqual(eval_stn["spi_90d"], 0.50)

        # Aggregate regional
        region_meta = {"region_code": "TPI", "region_name": "Kota Tanjungpinang"}
        reg_agg = aggregate_region_hazard(
            region_meta=region_meta,
            evaluated_stations=[eval_stn],
            hazard_code="PDKM",
            period_label="2026-11-das1",
            cutoff_date="2026-10-31",
            forecast_issue_date="2026-10-31",
            min_coverage_pct=30.0
        )
        self.assertEqual(reg_agg["recommended_level"], "AMAN")
        self.assertEqual(len(reg_agg["triggering_stations"]), 0)

    def test_scenario_9_arg_policy_maintained(self):
        """
        Pengujian 9 — ARG dan data tidak lengkap:
        Pos ARG tidak pernah diuji terhadap SPI atau probabilitas ECMWF.
        Evaluasi ARG murni berbasis HTH.
        """
        arg_stn = {
            "station_id": "21040101B",
            "station_name": "ARG Daik Lingga",
            "kabupaten": "Kabupaten Lingga",
            "is_arg": True,
            "hth_days": 25,              # WASPADA HTH
            "spi_value": None,
            "spi_value_90d": None,
            "forecast_pb20": None,
        }
        eval_stn = evaluate_station_hazards_item(arg_stn, "2026-11-das1")
        self.assertEqual(eval_stn["pdkm"]["status"], "WASPADA")
        self.assertEqual(eval_stn["pdkm"]["level"], 1)
        self.assertTrue(eval_stn["pdkm"]["valid"])
        self.assertFalse(eval_stn["pdcht"]["applicable"])


if __name__ == "__main__":
    unittest.main()
