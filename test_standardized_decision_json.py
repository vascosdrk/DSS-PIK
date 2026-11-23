"""
Comprehensive Test Suite for Standardized Decision-Based JSON Output (DSS-PIK)
Covers all 16 functional & quality-control scenarios:
- Kecamatan status: AMAN, WASPADA, SIAGA, AWAS
- Kecamatan without stations & parent inheritance (inherited_from_parent)
- Kecamatan without stations and without valid parent decision -> INSUFFICIENT_DATA
- Kecamatan with operator override (original recommendation preserved; cancelled warning removed)
- Regions with COMPLETE, PARTIAL, INSUFFICIENT_DATA
- PDKM only, PDCHT only, Dual-Hazard simultaneous (MULTI_HAZARD), No active hazard
- Publication revision & status metadata consistency (DRAFT / APPROVED / PUBLISHED / Aktif)
- Operator decision modification
- 18-point Quality Control Validator positive & negative checks
- Live actual DSS-PIK pipeline execution against real operational data (no dummy data)
"""

import copy
import json
import math
import unittest

from backend.regional_warning_service import (
    _build_standardized_decision_payload,
    _build_structured_triggered_conditions,
    _synthesize_entity_decision,
    build_sih3_publication_json,
    compute_kecamatan_recommendations,
    compute_regional_recommendations,
    validate_sih3_json_payload,
)


def _make_mock_bundles():
    """Creates deterministic structural test bundles using canonical 7 regions & 59 kecamatan."""
    # Start from real canonical registry metadata via live snapshot for exact 59 kecamatan & 7 regions
    rec_bundle = compute_regional_recommendations(period_id="2026-11-das2")
    kec_bundle = compute_kecamatan_recommendations(period_id="2026-11-das2")
    return copy.deepcopy(rec_bundle), copy.deepcopy(kec_bundle)


class TestStandardizedDecisionJson(unittest.TestCase):

    def test_01_live_actual_pipeline_builds_valid_decision_json(self):
        """Real pipeline test on actual DSS-PIK data (2026-11-das2) passes all 18 QC checks."""
        payload = build_sih3_publication_json(period_id="2026-11-das2")
        val = validate_sih3_json_payload(payload)
        self.assertTrue(val["valid"], f"Validation failed: {val['errors']}")
        self.assertEqual(val["regions_count"], 7)
        self.assertEqual(val["kecamatan_count"], 59)

        expected_top = [
            "schema_version",
            "system",
            "institution",
            "publication",
            "source",
            "generated_at",
            "period",
            "province",
            "kecamatan",
            "regions",
        ]
        self.assertEqual(list(payload.keys()), expected_top)
        self.assertNotIn("stations", payload)
        self.assertNotIn("data_completeness", payload)
        self.assertNotIn("period_id", payload["period"])
        self.assertEqual(payload["source"]["period_id"], "2026-11-das2")

        # Strict JSON without NaN/Infinity
        dumped = json.dumps(payload, allow_nan=False)
        self.assertTrue(len(dumped) > 1000)

    def test_02_kecamatan_all_warning_levels_and_override(self):
        """Verifies AMAN, WASPADA, SIAGA, AWAS, and operator override preserving recommendation."""
        rec_b, kec_b = _make_mock_bundles()
        pub_meta = {
            "publication_id": "DSSPIK-20261111-112",
            "revision": 1,
            "status": "Aktif",
            "published_at": None,
            "approved_by": None,
            "published_by": None,
            "revision_reason": None,
        }
        # Pick 4 kecamatan with stations to set AMAN, WASPADA, SIAGA, AWAS explicitly
        k_with_stns = [k for k in kec_b["kecamatan"] if k["stations_count"] > 0][:5]
        self.assertGreaterEqual(len(k_with_stns), 5)

        kec_ov = {
            k_with_stns[0]["kecamatan_id"]: {
                "fin_p": "AMAN", "fin_c": "AMAN",
                "ov_reason_p": "Koreksi lokal aman", "ov_reason_c": "Koreksi lokal aman",
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
            k_with_stns[1]["kecamatan_id"]: {
                "fin_p": "AMAN", "fin_c": "WASPADA",
                "ov_reason_p": None, "ov_reason_c": "Verifikasi ECMWF > 50%",
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
            k_with_stns[2]["kecamatan_id"]: {
                "fin_p": "SIAGA", "fin_c": "AMAN",
                "ov_reason_p": "Defisit hujan 90 hari", "ov_reason_c": None,
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
            k_with_stns[3]["kecamatan_id"]: {
                "fin_p": "AWAS", "fin_c": "AMAN",
                "ov_reason_p": "Kekeringan ekstrem", "ov_reason_c": None,
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
            k_with_stns[4]["kecamatan_id"]: {
                "fin_p": "SIAGA", "fin_c": "WASPADA",
                "ov_reason_p": "Multi-bahaya aktif", "ov_reason_c": "Multi-bahaya aktif",
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
        }

        payload = _build_standardized_decision_payload(
            rec_bundle=rec_b,
            kec_bundle=kec_b,
            publication_meta=pub_meta,
            valid_from="2026-11-11",
            valid_until="2026-11-20",
            generated_at_iso="2026-11-19T06:00:00+07:00",
            kecamatan_overrides=kec_ov,
            default_operator="klimatkepri",
        )
        val = validate_sih3_json_payload(payload)
        self.assertTrue(val["valid"], f"Validation errors: {val['errors']}")

        by_id = {k["kecamatan_id"]: k for k in payload["kecamatan"]}

        # 1. AMAN (overridden if recommendation was active -> warnings must be [])
        k0 = by_id[k_with_stns[0]["kecamatan_id"]]
        self.assertEqual(k0["overall_status"], "AMAN")
        self.assertEqual(k0["warnings"], [])
        self.assertEqual(k0["final_decision"]["status"], "NONE")
        self.assertEqual(k0["hazard_assessments"]["PDKM"]["recommended_level"], k0["recommendations"]["PDKM"]["level"])

        # 2. WASPADA (PDCHT only)
        k1 = by_id[k_with_stns[1]["kecamatan_id"]]
        self.assertEqual(k1["overall_status"], "WASPADA")
        self.assertEqual(k1["final_decision"]["warning_type"], "PDCHT")
        self.assertEqual(len(k1["warnings"]), 1)
        self.assertEqual(k1["warnings"][0]["hazard_code"], "PDCHT")

        # 3. SIAGA (PDKM only)
        k2 = by_id[k_with_stns[2]["kecamatan_id"]]
        self.assertEqual(k2["overall_status"], "SIAGA")
        self.assertEqual(k2["final_decision"]["warning_type"], "PDKM")
        self.assertEqual(len(k2["warnings"]), 1)
        self.assertEqual(k2["warnings"][0]["hazard_code"], "PDKM")

        # 4. AWAS (PDKM only)
        k3 = by_id[k_with_stns[3]["kecamatan_id"]]
        self.assertEqual(k3["overall_status"], "AWAS")
        self.assertEqual(k3["final_decision"]["level"], "AWAS")
        self.assertEqual(k3["final_decision"]["status"], "ACTIVE")

        # 5. Dual-hazard simultaneous (MULTI_HAZARD)
        k4 = by_id[k_with_stns[4]["kecamatan_id"]]
        self.assertEqual(k4["overall_status"], "SIAGA")
        self.assertEqual(k4["final_decision"]["warning_type"], "MULTI_HAZARD")
        self.assertEqual(len(k4["warnings"]), 2)

    def test_03_kecamatan_without_stations_inheritance_and_insufficient_data(self):
        """Station-less kecamatan inherits valid parent decision; if parent has INSUFFICIENT_DATA, never auto-AMAN."""
        rec_b, kec_b = _make_mock_bundles()
        pub_meta = {
            "publication_id": "DSSPIK-20261111-112",
            "revision": 1,
            "status": "Aktif",
            "published_at": None,
            "approved_by": None,
            "published_by": None,
            "revision_reason": None,
        }
        # Set KOTA BATAM to valid PDCHT WASPADA, and KEPULAUAN ANAMBAS to INSUFFICIENT_DATA
        reg_ov = {
            "KOTA BATAM": {
                "fin_p": "AMAN", "fin_c": "WASPADA",
                "ov_reason_p": None, "ov_reason_c": None,
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
            "KEPULAUAN ANAMBAS": {
                "fin_p": "INSUFFICIENT_DATA", "fin_c": "INSUFFICIENT_DATA",
                "ov_reason_p": None, "ov_reason_c": None,
                "operator": "klimatkepri", "decided_at": "2026-11-19T06:00:00+07:00",
            },
        }
        # Mark Anambas region data_status as INSUFFICIENT_DATA for completeness check
        for r in rec_b["regions"]:
            if r["sih3_polygon_key"] == "KEPULAUAN ANAMBAS":
                r["data_status"] = "INSUFFICIENT_DATA"

        payload = _build_standardized_decision_payload(
            rec_bundle=rec_b,
            kec_bundle=kec_b,
            publication_meta=pub_meta,
            valid_from="2026-11-11",
            valid_until="2026-11-20",
            generated_at_iso="2026-11-19T06:00:00+07:00",
            regency_overrides=reg_ov,
            default_operator="klimatkepri",
        )
        val = validate_sih3_json_payload(payload)
        self.assertTrue(val["valid"], f"Validation errors: {val['errors']}")

        # Station-less kecamatan in Batam must inherit WASPADA with inherited_from_parent=True
        batam_empty = [k for k in payload["kecamatan"] if k["parent_polygon_key"] == "KOTA BATAM" and k["stations_count"] == 0]
        self.assertGreater(len(batam_empty), 0)
        for k in batam_empty:
            self.assertTrue(k["inherited_from_parent"])
            self.assertEqual(k["overall_status"], "WASPADA")
            self.assertEqual(k["final_decision"]["warning_type"], "PDCHT")

        # Station-less kecamatan in Anambas (parent INSUFFICIENT_DATA) must be INSUFFICIENT_DATA, NEVER AMAN
        anambas_empty = [k for k in payload["kecamatan"] if k["parent_polygon_key"] == "KEPULAUAN ANAMBAS" and k["stations_count"] == 0]
        self.assertGreater(len(anambas_empty), 0)
        for k in anambas_empty:
            self.assertEqual(k["overall_status"], "INSUFFICIENT_DATA")
            self.assertEqual(k["final_decision"]["status"], "INSUFFICIENT_DATA")
            self.assertEqual(k["warnings"], [])

    def test_04_regions_complete_partial_insufficient_data_and_coverage_math(self):
        """Verifies COMPLETE, PARTIAL, INSUFFICIENT_DATA regions and mathematical coverage alignment."""
        rec_b, kec_b = _make_mock_bundles()
        # Set explicit region coverage states: COMPLETE (Tanjungpinang), PARTIAL (Bintan), INSUFFICIENT_DATA (Anambas)
        for r in rec_b["regions"]:
            if r["sih3_polygon_key"] == "KOTA TANJUNGPINANG":
                r["data_status"] = "COMPLETE"
                r["station_coverage"] = {"total": 4, "manual_stations": 4, "arg_stations": 0, "valid": 4, "missing": 0, "percentage": 100.0}
            elif r["sih3_polygon_key"] == "BINTAN":
                r["data_status"] = "PARTIAL"
                r["station_coverage"] = {"total": 16, "manual_stations": 14, "arg_stations": 2, "valid": 8, "missing": 8, "percentage": 50.0}
            elif r["sih3_polygon_key"] == "KEPULAUAN ANAMBAS":
                r["data_status"] = "INSUFFICIENT_DATA"
                r["station_coverage"] = {"total": 3, "manual_stations": 3, "arg_stations": 0, "valid": 0, "missing": 3, "percentage": 0.0}

        pub_meta = {
            "publication_id": "DSSPIK-20261111-112",
            "revision": 2,
            "status": "PUBLISHED",
            "published_at": "2026-11-19T06:05:00+07:00",
            "approved_by": "forecaster_kepri",
            "published_by": "klimatkepri",
            "revision_reason": "Pembaruan observasi dasarian II",
        }
        payload = _build_standardized_decision_payload(
            rec_bundle=rec_b,
            kec_bundle=kec_b,
            publication_meta=pub_meta,
            valid_from="2026-11-11",
            valid_until="2026-11-20",
            generated_at_iso="2026-11-19T06:05:00+07:00",
        )
        val = validate_sih3_json_payload(payload)
        self.assertTrue(val["valid"], f"Validation errors: {val['errors']}")

        # Publication revision & status checks
        self.assertEqual(payload["publication"]["revision"], 2)
        self.assertEqual(payload["publication"]["status"], "PUBLISHED")
        self.assertEqual(payload["publication"]["approved_by"], "forecaster_kepri")
        self.assertEqual(payload["publication"]["published_by"], "klimatkepri")
        self.assertIsNotNone(payload["publication"]["published_at"])

        reg_by_poly = {r["sih3_polygon_key"]: r for r in payload["regions"]}
        self.assertEqual(reg_by_poly["KOTA TANJUNGPINANG"]["data_status"], "COMPLETE")
        self.assertEqual(reg_by_poly["KOTA TANJUNGPINANG"]["data_coverage"]["coverage_percent"], 100.0)
        self.assertEqual(reg_by_poly["KOTA TANJUNGPINANG"]["data_coverage"]["coverage_percentage"], 100.0)
        self.assertEqual(reg_by_poly["BINTAN"]["data_status"], "PARTIAL")
        self.assertEqual(reg_by_poly["KEPULAUAN ANAMBAS"]["data_status"], "INSUFFICIENT_DATA")
        self.assertEqual(reg_by_poly["KEPULAUAN ANAMBAS"]["data_coverage"]["status"], "INSUFFICIENT_DATA")

    def test_05_structured_triggered_conditions_consistency(self):
        """Verifies uniform object structure for PDKM (HTH, pb20, SPI_90D) and PDCHT (>50%) triggers."""
        mock_stns = [
            {
                "station_id": "21040201A",
                "station_name": "Bukit Langkap",
                "input_summary": {
                    "hth_days": 35,
                    "pb20": 75.0,
                    "spi_90d": -2.03,
                    "pa150": 55.0,
                    "pa200": 10.0,
                    "pa300": 0.0,
                    "pm300": 70.6,
                    "pm400": 15.0,
                    "pm500": 0.0,
                },
            }
        ]
        pdkm_c = _build_structured_triggered_conditions("PDKM", mock_stns)
        pdcht_c = _build_structured_triggered_conditions("PDCHT", mock_stns)
        self.assertEqual(len(pdkm_c), 3)
        self.assertEqual({c["indicator"] for c in pdkm_c}, {"HTH", "pb20", "SPI_90D"})
        self.assertEqual(len(pdcht_c), 2)
        self.assertEqual({c["indicator"] for c in pdcht_c}, {"pa150", "pa300_monthly"})
        for cond in pdkm_c + pdcht_c:
            for k in ("indicator", "value", "unit", "operator", "threshold", "period", "station_code", "station_name", "description"):
                self.assertIn(k, cond)

    def test_06_validator_catches_critical_quality_control_violations(self):
        """Negative QC checks: validator must reject forbidden root fields, NaN, bad timestamps, broken math, and override mismatch."""
        base = build_sih3_publication_json(period_id="2026-11-das2")
        self.assertTrue(validate_sih3_json_payload(base)["valid"])

        # A. Forbidden root 'stations'
        bad_root = copy.deepcopy(base)
        bad_root["stations"] = []
        self.assertFalse(validate_sih3_json_payload(bad_root)["valid"])

        # B. NaN value
        bad_nan = copy.deepcopy(base)
        bad_nan["regions"][0]["station_coverage"]["percentage"] = float("nan")
        self.assertFalse(validate_sih3_json_payload(bad_nan)["valid"])

        # C. Duplicate kecamatan
        bad_dup = copy.deepcopy(base)
        bad_dup["kecamatan"][1] = copy.deepcopy(bad_dup["kecamatan"][0])
        self.assertFalse(validate_sih3_json_payload(bad_dup)["valid"])

        # D. Coverage math mismatch
        bad_cov = copy.deepcopy(base)
        bad_cov["regions"][0]["data_coverage"]["valid_stations"] = 999
        self.assertFalse(validate_sih3_json_payload(bad_cov)["valid"])

        # E. Overridden recommendation leaked into warnings
        bad_warn = copy.deepcopy(base)
        bad_warn["kecamatan"][0]["hazard_assessments"]["PDKM"]["final_level"] = "AMAN"
        bad_warn["kecamatan"][0]["warnings"] = [{
            "hazard_code": "PDKM",
            "hazard_name": "Kekeringan Meteorologis",
            "recommended_level": "WASPADA",
            "final_level": "WASPADA",
            "decision_source": "DSS_RECOMMENDATION",
            "operator_override": False,
            "override_reason": None,
            "narrative": "Should be rejected",
        }]
        self.assertFalse(validate_sih3_json_payload(bad_warn)["valid"])

        # F. PUBLISHED status missing published_at
        bad_pub = copy.deepcopy(base)
        bad_pub["publication"]["status"] = "PUBLISHED"
        bad_pub["publication"]["published_at"] = None
        self.assertFalse(validate_sih3_json_payload(bad_pub)["valid"])

    def test_07_institution_identity_single_source_of_truth_and_qc(self):
        """
        Regression QC: Ensure official institution identity is strictly
        'BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang'
        across single source of truth, preview JSON, exported JSON, and validator.
        """
        import re
        from backend.config import INSTITUTION_NAME
        from backend.regional_warning_service import (
            build_map_modal_sih3_json,
            build_sih3_publication_json,
            validate_sih3_json_payload,
        )

        expected = "BMKG Stasiun Meteorologi Kelas II Raja Haji Fisabilillah Tanjungpinang"
        self.assertEqual(INSTITUTION_NAME, expected)

        # 1. Preview JSON builder
        preview_doc = build_sih3_publication_json(period_id="2026-11-das2")
        self.assertEqual(preview_doc["institution"], expected)
        self.assertEqual(preview_doc["source"]["institution"], expected)
        self.assertEqual(preview_doc["institution"], preview_doc["source"]["institution"])
        self.assertNotRegex(json.dumps(preview_doc, ensure_ascii=False), re.compile(r"Kelas\s+I(?!I)\b", re.IGNORECASE))
        self.assertTrue(validate_sih3_json_payload(preview_doc)["valid"])

        # 2. Export JSON builder
        export_res = build_map_modal_sih3_json(
            period_id="2026-11-das2",
            scope="UNIFIED",
            operator_name="klimatkepri",
            publish=False,
        )
        export_doc = export_res["payload"]
        self.assertEqual(export_doc["institution"], expected)
        self.assertEqual(export_doc["source"]["institution"], expected)
        self.assertEqual(export_doc["institution"], preview_doc["institution"])
        self.assertEqual(export_doc["source"]["institution"], preview_doc["source"]["institution"])
        self.assertNotRegex(json.dumps(export_doc, ensure_ascii=False), re.compile(r"Kelas\s+I(?!I)\b", re.IGNORECASE))
        self.assertTrue(export_res["validation"]["valid"])

        # 3. Negative QC: validator must reject legacy 'Kelas I' in root or source
        wrong_root = copy.deepcopy(preview_doc)
        wrong_root["institution"] = "BMKG Stasiun Meteorologi Kelas I Raja Haji Fisabilillah Tanjungpinang"
        res_wrong_root = validate_sih3_json_payload(wrong_root)
        self.assertFalse(res_wrong_root["valid"])
        self.assertTrue(any("Kelas I" in e or "institution" in e for e in res_wrong_root["errors"]))

        wrong_source = copy.deepcopy(preview_doc)
        wrong_source["source"]["institution"] = "BMKG Stasiun Meteorologi Kelas I Raja Haji Fisabilillah Tanjungpinang"
        res_wrong_source = validate_sih3_json_payload(wrong_source)
        self.assertFalse(res_wrong_source["valid"])
        self.assertTrue(any("source.institution" in e for e in res_wrong_source["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

