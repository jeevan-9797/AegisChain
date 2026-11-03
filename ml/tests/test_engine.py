import math
import unittest

from ml import SignalClassifier, run_incident_evaluation


SAP_8842_FEED = [
    {
        "id": "SIG-8842-01",
        "text": (
            "Houthi missile barrage strikes container vessel off Bab el-Mandeb, "
            "shutting Red Sea transit corridor."
        ),
    },
    {
        "id": "SIG-8842-02",
        "text": (
            "Severe yard congestion at Port of Mombasa causes 10-day dwell times "
            "for refrigerated pharma cargo."
        ),
    },
    {
        "id": "SIG-8842-03",
        "text": (
            "Real Madrid advances to Champions League final after dramatic "
            "stoppage time comeback victory."
        ),
    },
]


class IncidentEvaluationTests(unittest.TestCase):
    def test_identical_input_has_deterministic_results(self):
        first = run_incident_evaluation(SAP_8842_FEED)
        second = run_incident_evaluation(SAP_8842_FEED)

        # Timestamp and measured execution latency are intentionally runtime-dependent.
        for result in (first, second):
            result.pop("timestamp")
            result["execution_metadata"].pop("latency_ms")
            result["executive_briefing"].pop("generated_at")
        self.assertEqual(first, second)

    def test_classifier_categories_and_severities_match_demo_feed(self):
        classified = SignalClassifier(mode="deterministic").classify_signals(
            SAP_8842_FEED
        )
        self.assertEqual(
            [(signal["category"], signal["severity"]) for signal in classified],
            [("CHOKEPOINT", 3), ("PORT", 2), ("OTHER", 1)],
        )

    def test_sap_8842_selects_split_sea_air_scenario(self):
        result = run_incident_evaluation(SAP_8842_FEED)
        self.assertEqual(
            result["decision_optimization"]["recommended_scenario_key"],
            "OPTION_C_SPLIT",
        )
        self.assertEqual(
            result["scenarios"]["OPTION_C_SPLIT"]["net_economic_impact_usd"],
            51415.0,
        )

    def test_empty_feed_returns_no_active_alerts_and_still_evaluates_scenarios(self):
        result = run_incident_evaluation([])
        self.assertEqual(result["classified_signals"], [])
        self.assertEqual(result["signals_summary"]["primary_threat"], "No active alerts")
        self.assertIn("OPTION_C_SPLIT", result["scenarios"])

    def test_malformed_feed_entries_are_rejected(self):
        classifier = SignalClassifier(mode="deterministic")
        for feed_item in (None, "not a feed object", 42):
            with self.subTest(feed_item=feed_item):
                with self.assertRaisesRegex(ValueError, r"feed_items\[0\] must be a mapping"):
                    run_incident_evaluation([feed_item])

        # A mapping without any recognized text field is accepted as an OTHER signal.
        result = classifier.classify_signals([{}])
        self.assertEqual(result[0]["category"], "OTHER")
        self.assertEqual(result[0]["severity"], 1)

    def test_invalid_cargo_values_are_rejected(self):
        invalid_values = (
            -1.0,
            math.nan,
            math.inf,
            -math.inf,
            "450000",
            None,
            True,
            10**400,
        )
        for cargo_value in invalid_values:
            with self.subTest(cargo_value=cargo_value):
                with self.assertRaisesRegex(
                    ValueError, "cargo_value must be a finite number greater than zero"
                ):
                    run_incident_evaluation([], cargo_value=cargo_value)


if __name__ == "__main__":
    unittest.main()
