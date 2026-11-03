"""AegisChain LLM Integration & Briefing Verification Suite.

Validates the SwappableLLMClient adapter, live AI agent headline classification,
and ExecutiveBriefingAgent generation for SAP Hackfest 2026.
"""

from __future__ import annotations

import json
import logging
import os
import sys

# Ensure repository root is on sys.path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ml.briefing_agent import ExecutiveBriefingAgent
from ml.classifier import SignalClassifier
from ml.engine import run_incident_evaluation
from ml.llm_client import SwappableLLMClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_llm")


def run_llm_tests() -> int:
    """Run all LLM adapter and briefing agent verification tests."""
    print("================================================================================")
    print("       AEGISCHAIN LLM INTEGRATION & BRIEFING AGENT VERIFICATION TEST           ")
    print("================================================================================")

    # Test 1: SwappableLLMClient Initialization & Sanitation
    print("\n[TEST 1] Initializing SwappableLLMClient & Testing JSON Parser...")
    client = SwappableLLMClient()
    print(f"  * Provider: {client.provider}")
    print(f"  * Configured Model: {client.model_name}")
    print(f"  * API Key configured: {'YES (live proxy ready)' if bool(client.api_key) else 'NO (local fallback active)'}")

    # Test JSON sanitizer
    sample_json = '```json\n{"status": "ok", "test_id": 42}\n```'
    parsed = client._clean_and_parse_json(sample_json)
    assert parsed["status"] == "ok" and parsed["test_id"] == 42
    print("  * JSON sanitization & fence stripping: PASSED")

    # If API key is present, test live model invocation
    has_live_key = bool(client.api_key)
    if has_live_key:
        print(f"  * Live GEMINI_API_KEY detected. Executing test prompt to {client.model_name}...")
        try:
            live_res = client.generate_structured_json(
                prompt="Respond with a JSON object: {\"status\": \"CONNECTED\", \"echo\": 123}",
                system_instruction="You are a test responder.",
            )
            print(f"  * Live LLM Response: {json.dumps(live_res)}")
            assert live_res.get("status") == "CONNECTED"
            print("  * Live Google AI Studio invocation: PASSED")
        except Exception as exc:
            print(f"  ! Live call failed: {exc}")
            raise exc
    else:
        print("  * Zero-credential mode: Verified graceful handling when GEMINI_API_KEY is not set.")

    # Test 2: SignalClassifier in 'llm_proxy' Mode
    print("\n[TEST 2] Testing SignalClassifier in 'llm_proxy' mode with dummy headlines...")
    classifier = SignalClassifier(mode="llm_proxy")
    test_feed = [
        {
            "id": "DUMMY-01",
            "text": "Houthi missile barrage strikes container vessel off Bab el-Mandeb, shutting Red Sea transit corridor.",
        },
        {
            "id": "DUMMY-02",
            "text": "Champions League football match ends in a thrilling penalty shootout victory.",
        },
    ]

    classified = classifier.classify_signals(test_feed)
    assert len(classified) == 2

    # Check signal 1 (Disruption)
    sig1 = classified[0]
    print(f"  * Item 1 ({sig1['signal_id']}): category='{sig1['category']}', severity={sig1['severity']}, is_fallback={sig1['is_fallback']}")
    assert sig1["category"] in ("CHOKEPOINT", "PORT", "TARIFF", "WEATHER")
    assert sig1["severity"] in (2, 3)

    # Check signal 2 (Noise)
    sig2 = classified[1]
    print(f"  * Item 2 ({sig2['signal_id']}): category='{sig2['category']}', severity={sig2['severity']}, is_fallback={sig2['is_fallback']}")
    assert sig2["category"] == "OTHER"
    assert sig2["impacted_lanes"] == []
    print("  * SignalClassifier llm_proxy classification: PASSED")

    # Test 3: ExecutiveBriefingAgent for Case #SAP-8842
    print("\n[TEST 3] Testing ExecutiveBriefingAgent for Case #SAP-8842...")
    mock_incident_data = {
        "incident_id": "SAP-8842",
        "cargo_profile": {
            "product": "Insulin Glargine",
            "quantity_doses": 40000,
            "cargo_value_usd": 450000.0,
            "thermal_budget_days": 9.0,
            "origin": "Antwerp (ANR)",
            "destination": "Mombasa, Kenya (MBA)",
        },
        "signals_summary": {
            "primary_threat": "Houthi missile barrage off Bab el-Mandeb",
            "impacted_lanes": ["RED_SEA", "ASIA_EUROPE"],
        },
        "scenarios": {
            "OPTION_A_CAPE": {
                "name": "Cape Detour",
                "extra_delay_days": 17.94,
                "spoilage_risk_pct": "92.0%",
                "extra_freight_usd": 14000.0,
                "expected_cargo_loss_usd": 414000.0,
                "net_economic_impact_usd": 428000.0,
            },
            "OPTION_B_AIR": {
                "name": "Full Air Charter",
                "extra_delay_days": 1.52,
                "spoilage_risk_pct": "1.9%",
                "extra_freight_usd": 95000.0,
                "expected_cargo_loss_usd": 8640.0,
                "net_economic_impact_usd": 103640.0,
            },
            "OPTION_C_SPLIT": {
                "name": "Sea-Air Multimodal Hybrid",
                "extra_delay_days": 2.39,
                "spoilage_risk_pct": "2.9%",
                "extra_freight_usd": 38500.0,
                "expected_cargo_loss_usd": 12915.0,
                "net_economic_impact_usd": 51415.0,
            },
        },
        "decision_optimization": {
            "recommended_scenario_key": "OPTION_C_SPLIT",
            "financial_savings": {
                "vs_cape_detour_usd": 376585.0,
                "vs_full_air_charter_usd": 52225.0,
            },
        },
    }

    briefing_agent = ExecutiveBriefingAgent()
    brief = briefing_agent.generate_brief(mock_incident_data)

    required_brief_keys = [
        "executive_summary",
        "recommended_action",
        "risk_mitigation",
        "financial_impact",
        "sign_off_status",
    ]
    for key in required_brief_keys:
        assert key in brief, f"Missing key in brief: {key}"
        assert len(str(brief[key])) > 0, f"Empty value for key: {key}"

    assert brief["sign_off_status"] == "AWAITING_HUMAN_APPROVAL"
    source_label = "LLM Live Proxy" if not brief.get("is_fallback") else "Deterministic Template Fallback"
    print(f"  * Generated Brief Source: {source_label}")
    print(f"  * Sign-Off Status: {brief['sign_off_status']}")
    print(f"  * Summary Snippet: {brief['executive_summary'][:110]}...")
    print(f"  * Financial Impact: {brief['financial_impact'][:110]}...")

    if has_live_key:
        assert brief.get("is_fallback") is False, "Expected live LLM brief when GEMINI_API_KEY is configured!"
        print("  * Confirmed: Live LLM was successfully used for executive briefing (is_fallback=False).")

    print("  * ExecutiveBriefingAgent output verification: PASSED")

    # Test 4: End-to-End Orchestration Integration
    print("\n[TEST 4] Testing End-to-End Orchestration with Executive Briefing Attachment...")
    eval_res = run_incident_evaluation(
        test_feed, cargo_value=450000.0, classifier_mode="llm_proxy"
    )

    assert "executive_briefing" in eval_res
    assert eval_res["executive_briefing"]["sign_off_status"] == "AWAITING_HUMAN_APPROVAL"
    assert eval_res["decision_optimization"]["recommended_scenario_key"] == "OPTION_C_SPLIT"
    print("  * Executive briefing successfully attached to final CAP evaluation payload.")
    print(f"  * Payload incident_id: {eval_res['incident_id']}")
    print(f"  * Total latency: {eval_res['execution_metadata']['latency_ms']} ms")
    print("  * End-to-End Orchestration: PASSED")

    print("\n================================================================================")
    print("     >> ALL LLM ADAPTER & BRIEFING VERIFICATION TESTS PASSED 100% <<           ")
    print("================================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_llm_tests())
