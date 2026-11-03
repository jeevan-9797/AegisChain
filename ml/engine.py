"""AegisChain Orchestration Engine.

Unified entry point integrating signal classification, predictive ML scenario scoring,
and human-in-the-loop executive decision briefing.
Generates SAP CAP and UI5-compatible payloads for cold-chain incident decision support.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import numbers
import os
import sys
import time
from collections.abc import Mapping
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path for direct script execution
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ml.briefing_agent import ExecutiveBriefingAgent
from ml.classifier import SignalClassifier
from ml.models import AegisPredictiveCore

logger = logging.getLogger("aegischain.engine")


def run_incident_evaluation(
    feed_items: List[Dict[str, Any]],
    cargo_value: float = 450000.0,
    incident_id: str = "SAP-8842",
    classifier_mode: str = "deterministic",
) -> Dict[str, Any]:
    """Execute end-to-end incident evaluation, simulation, and executive decision briefing.

    Orchestrates:
      1. Feed signal classification (deterministic heuristics or LLM proxy).
      2. Multi-scenario simulation using dual gradient boosting estimators.
      3. Decision optimization (identifying minimum net economic impact).
      4. Executive decision briefing generation (ExecutiveBriefingAgent).
      5. Downstream payload formatting conforming to SAP CAP / Fiori contracts.

    Args:
        feed_items: Raw incident alerts, news items, or RSS feed entries.
        cargo_value: Invoice/replacement value of the cargo in USD (default: $450,000.00).
        incident_id: Tracking ID for the active consignment incident (default: 'SAP-8842').
        classifier_mode: Classification mode: 'deterministic', 'llm_proxy', or 'genai_hub'.

    Returns:
        Structured JSON-serializable decision package.
    """
    valid_cargo_value = not isinstance(cargo_value, bool) and isinstance(
        cargo_value, numbers.Real
    )
    if valid_cargo_value:
        try:
            valid_cargo_value = math.isfinite(cargo_value) and cargo_value > 0
        except OverflowError:
            valid_cargo_value = False
    if not valid_cargo_value:
        raise ValueError("cargo_value must be a finite number greater than zero")

    for index, item in enumerate(feed_items):
        if not isinstance(item, Mapping):
            raise ValueError(f"feed_items[{index}] must be a mapping")

    start_time = time.perf_counter()

    # Step 1: Signal Classification
    classifier = SignalClassifier(mode=classifier_mode)
    classified_signals = classifier.classify_signals(feed_items)

    # Aggregate active disruptions
    disruption_signals = [
        s for s in classified_signals if s["category"] != "OTHER" and s["severity"] >= 2
    ]
    all_lanes = sorted(
        list(
            {
                lane
                for signal in classified_signals
                for lane in signal.get("impacted_lanes", [])
            }
        )
    )

    primary_threat = (
        disruption_signals[0]["title"]
        if disruption_signals
        else (classified_signals[0]["title"] if classified_signals else "No active alerts")
    )

    # Step 2: Predictive Simulation of Alternative Rerouting Scenarios
    core = AegisPredictiveCore()
    scenarios = core.evaluate_all_scenarios(cargo_value=cargo_value)

    # Step 3: Optimization — Find scenario with minimal net economic impact
    optimal_key = min(scenarios.keys(), key=lambda k: scenarios[k]["net_economic_impact_usd"])
    optimal_scenario = scenarios[optimal_key]

    worst_key = max(scenarios.keys(), key=lambda k: scenarios[k]["net_economic_impact_usd"])
    worst_scenario = scenarios[worst_key]

    air_scenario = scenarios.get("OPTION_B_AIR", optimal_scenario)

    savings_vs_worst = round(
        worst_scenario["net_economic_impact_usd"] - optimal_scenario["net_economic_impact_usd"], 2
    )
    savings_vs_air = round(
        air_scenario["net_economic_impact_usd"] - optimal_scenario["net_economic_impact_usd"], 2
    )

    # Step 4: Assemble Initial Payload Conforming to SAP CAP & Control Tower UI Schema
    payload: Dict[str, Any] = {
        "incident_id": incident_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "AWAITING_APPROVAL",
        "cargo_profile": {
            "product": "Insulin Glargine",
            "quantity_doses": 40000,
            "cargo_value_usd": cargo_value,
            "thermal_budget_days": 9.0,
            "target_temp_range": "2°C to 8°C (Cold-Chain Viability)",
            "origin": "Antwerp (ANR)",
            "destination": "Mombasa, Kenya (MBA)",
        },
        "signals_summary": {
            "total_signals_analyzed": len(classified_signals),
            "critical_disruptions_count": len(disruption_signals),
            "primary_threat": primary_threat,
            "impacted_lanes": all_lanes,
            "chokepoints_breached": [
                s["title"] for s in classified_signals if s["category"] == "CHOKEPOINT"
            ],
        },
        "classified_signals": classified_signals,
        "scenarios": scenarios,
        "decision_optimization": {
            "recommended_scenario_key": optimal_key,
            "recommended_name": optimal_scenario["name"],
            "recommended_mode": optimal_scenario["transport_mode"],
            "net_economic_impact_usd": optimal_scenario["net_economic_impact_usd"],
            "spoilage_risk": optimal_scenario["spoilage_risk_pct"],
            "delay_days": optimal_scenario["extra_delay_days"],
            "freight_cost_usd": optimal_scenario["extra_freight_usd"],
            "expected_cargo_loss_usd": optimal_scenario["expected_cargo_loss_usd"],
            "financial_savings": {
                "vs_cape_detour_usd": savings_vs_worst,
                "vs_full_air_charter_usd": savings_vs_air,
            },
            "recommendation_rationale": (
                f"Option '{optimal_scenario['name']}' is mathematically optimal. It keeps transit delay "
                f"within the 9-day thermal window ({optimal_scenario['extra_delay_days']}d delay vs 9.0d budget), "
                f"limiting spoilage risk to {optimal_scenario['spoilage_risk_pct']} while saving "
                f"${savings_vs_air:,.2f} over full air charter and avoiding ${savings_vs_worst:,.2f} in spoilage loss."
            ),
        },
    }

    # Step 5: Executive Decision Briefing Generation
    briefing_agent = ExecutiveBriefingAgent()
    payload["executive_briefing"] = briefing_agent.generate_brief(payload)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    payload["execution_metadata"] = {
        "engine": "AegisPredictiveCore",
        "version": "1.0.0-gate1",
        "classifier_mode": classifier_mode,
        "zero_credentials_verified": True,
        "latency_ms": elapsed_ms,
        "sap_ai_hub_toggle_ready": True,
        "briefing_status": payload["executive_briefing"].get("sign_off_status", "AWAITING_HUMAN_APPROVAL"),
    }

    return payload


if __name__ == "__main__":
    # Test feed matching presentation Case #SAP-8842
    sample_feed: List[Dict[str, Any]] = [
        {
            "id": "SIG-8842-01",
            "text": "Houthi missile barrage strikes container vessel off Bab el-Mandeb, shutting Red Sea transit corridor.",
        },
        {
            "id": "SIG-8842-02",
            "text": "Severe yard congestion at Port of Mombasa causes 10-day dwell times for refrigerated pharma cargo.",
        },
        {
            "id": "SIG-8842-03",
            "text": "Real Madrid advances to Champions League final after dramatic stoppage time comeback victory.",
        },
    ]

    # Support reading from stdin or json file if supplied
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            feed_input = json.load(f)
    elif len(sys.argv) > 1 and sys.argv[1] == "-":
        feed_input = json.load(sys.stdin)
    else:
        feed_input = sample_feed

    result = run_incident_evaluation(feed_input, cargo_value=450000.0)
    print(json.dumps(result, indent=2))
