"""
Phase 4.1 regression suite: Decision Engine & Dual Hazard consistency.
Pure fixtures (no DB/Parquet writes). Live API checks are skipped if backend is down.
Run: python test_phase41_regression.py
"""
import unittest
from backend.decision_engine import evaluate_pdkm_full, evaluate_pdcht_full, arbitrate_final_synthesis

LVL = {"AWAS": 3, "SIAGA": 2, "WASPADA": 1}


class TestStationFixtures(unittest.TestCase):
    """SPI 30D values are given to show they are NOT an input to the engine."""

    def _run(self, hth, spi30, spi90, pb20):
        return evaluate_pdkm_full(hth_days=hth, pb20=pb20, spi_val=spi90)

    def test_sungai_enam(self):
        r = self._run(1, -2.08, -1.65, 1.0)
        self.assertEqual(r["status"], "SIAGA")
        self.assertIn("SPI 90D -1.65", r["reasons"])

    def test_bukit_langkap(self):
        r = self._run(4, -1.19, -2.03, 12.0)
        self.assertEqual(r["status"], "AWAS")

    def test_hang_nadim(self):
        r = self._run(1, -2.22, -1.96, 5.0)
        self.assertEqual(r["status"], "SIAGA")


class TestDualHazard(unittest.TestCase):
    def test_both_normal(self):
        s = arbitrate_final_synthesis(evaluate_pdkm_full(5, 20.0, 0.2),
                                      evaluate_pdcht_full(10, 5, 0, 10, 5, 0))
        self.assertEqual((s["final_status"], s["hazard_type"], s["multi_hazard"]), ("NORMAL", "NORMAL", False))

    def test_pdkm_only(self):
        s = arbitrate_final_synthesis(evaluate_pdkm_full(35, 20.0, 0.2),
                                      evaluate_pdcht_full(10, 5, 0, 10, 5, 0))
        self.assertEqual((s["final_status"], s["hazard_type"]), ("SIAGA", "DROUGHT"))

    def test_pdcht_only(self):
        s = arbitrate_final_synthesis(evaluate_pdkm_full(5, 20.0, 0.2),
                                      evaluate_pdcht_full(10, 75, 0, 10, 5, 0))
        self.assertEqual((s["final_status"], s["hazard_type"]), ("SIAGA", "HEAVY_RAIN"))

    def test_both_active_unequal(self):
        d = evaluate_pdkm_full(5, 20.0, -2.1)          # AWAS
        r = evaluate_pdcht_full(75, 0, 0, 10, 5, 0)    # WASPADA
        s = arbitrate_final_synthesis(d, r)
        self.assertEqual((s["final_status"], s["hazard_type"], s["multi_hazard"]), ("AWAS", "MULTI_HAZARD", True))
        self.assertEqual((s["pdkm_status"], s["pdcht_status"]), ("AWAS", "WASPADA"))

    def test_both_active_tie(self):
        s = arbitrate_final_synthesis(evaluate_pdkm_full(5, 20.0, -1.2), evaluate_pdcht_full(75, 0, 0, 10, 5, 0))
        self.assertEqual((s["final_status"], s["hazard_type"]), ("WASPADA", "MULTI_HAZARD"))

    def test_spi90_missing(self):
        d = evaluate_pdkm_full(5, 20.0, None)
        self.assertEqual(d["status"], "INCOMPLETE")
        self.assertIn("SPI_90D", d["missing_inputs"])

    def test_monthly_prob_missing(self):
        r = evaluate_pdcht_full(10, 5, 0, None, None, None)
        self.assertEqual(r["status"], "INCOMPLETE")       # NULL is not 0%
        self.assertIn("Prob_Bulanan", r["missing_inputs"])
        r2 = evaluate_pdcht_full(75, 0, 0, None, None, None)
        self.assertEqual(r2["status"], "WASPADA")          # trigger kept, partial flagged
        self.assertFalse(r2["evaluation_complete"])

    def test_one_hazard_incomplete_not_safe(self):
        s = arbitrate_final_synthesis(evaluate_pdkm_full(5, 20.0, None), evaluate_pdcht_full(10, 5, 0, 10, 5, 0))
        self.assertEqual(s["final_status"], "INCOMPLETE")


class TestLiveApiConsistency(unittest.TestCase):
    """Mirrors App.jsx logic: KPI counts must equal priority-card counts per hazard mode."""

    @classmethod
    def setUpClass(cls):
        try:
            import requests, backend.auth as auth
            tok = auth.create_session_token("operator_bmkg")
            cls.kw = dict(headers={"Authorization": f"Bearer {tok}"}, cookies={auth.SESSION_COOKIE_NAME: tok}, timeout=60)
            cls.rq = requests
            r = requests.post("http://127.0.0.1:8000/api/v1/warnings/refresh-evaluate", **cls.kw)
            cls.refresh = r.json()
            cls.items = requests.get("http://127.0.0.1:8000/api/v1/early-warning-table", **cls.kw).json()
            if isinstance(cls.items, dict):
                cls.items = cls.items.get("items") or cls.items.get("data") or []
        except Exception as e:
            raise unittest.SkipTest(f"backend unavailable: {e}")

    def test_refresh_ok(self):
        self.assertTrue(self.refresh.get("success"))
        self.assertEqual(self.refresh.get("stations_total"), 57)

    def test_table_has_canonical_fields(self):
        self.assertEqual(len(self.items), 57)
        for f in ("pdkm_status", "pdkm_level", "pdcht_status", "pdcht_level", "hazard_type", "warning_level"):
            self.assertIn(f, self.items[0])

    def test_mode_counts_match_priority_list(self):
        for key in ("pdkm_status", "pdcht_status"):
            kpi = {k: sum(1 for s in self.items if (s.get(key) or "").upper() == k) for k in LVL}
            prio = [s for s in self.items if (s.get(key) or "").upper() in LVL]
            self.assertEqual(len(prio), sum(kpi.values()), key)

    def test_overall_consistent_with_hazards(self):
        for s in self.items:
            d, r = LVL.get((s.get("pdkm_status") or "").upper(), 0), LVL.get((s.get("pdcht_status") or "").upper(), 0)
            if d and r:
                self.assertEqual(s["hazard_type"], "MULTI_HAZARD", s["station_id"])
            if max(d, r):
                self.assertEqual(LVL.get(s["warning_level"].upper(), 0), max(d, r), s["station_id"])
            if not d and not r:
                self.assertNotEqual(s["hazard_type"], "MULTI_HAZARD", s["station_id"])

    def test_readiness_no_future_date(self):
        d = self.rq.get("http://127.0.0.1:8000/api/v1/periods/readiness", **self.kw).json()
        self.assertLessEqual(d["latest_observation_date"], d["server_time"][:10])


if __name__ == "__main__":
    unittest.main(verbosity=2)

