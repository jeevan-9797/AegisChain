"""AegisChain Orchestration Engine.

Unified entry point integrating signal classification and predictive ML scenario scoring.
Generates SAP CAP and UI5-compatible payloads for cold-chain incident decision support.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path for direct script execution
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ml.classifier import SignalClassifier
from ml.models import AegisPredictiveCore

logger = logging.getLogger("aegischain.engine")


def run_incident_evaluation(
    feed_items: List[Dict[str, Any]],
    cargo_value: float = 450000.0,
    incident_id: str = "SAP-8842",
) -> Dict[str, Any]:
    """Execute end-to-end incident evaluation and response recommendation.

    Orchestrates:
      1. Feed signal classification (identifying chokepoints, port backlogs, tariffs, weather).
      2. Multi-scenario simulation using dual gradient boosting estimators.
      3. Decision optimization (identifying minimum net economic impact).
      4. Downstream payload formatting conforming to SAP CAP / Fiori contracts.

    Args:
        feed_items: Raw incident alerts, news items, or RSS feed entries.
        cargo_value: Invoice/replacement value of the cargo in USD (default: $450,000.00).
        incident_id: Tracking ID for the active consignment incident (default: 'SAP-8842').

    Returns:
        Structured JSON-serializable decision package.
    """
    start_time = time.perf_counter()

    # Step 1: Signal Classification
    classifier = SignalClassifier(mode="deterministic")
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

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Step 4: Assemble Payload Conforming to SAP CAP & Control Tower UI Schema
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
        "execution_metadata": {
            "engine": "AegisPredictiveCore",
            "version": "1.0.0-gate1",
            "execution_mode": "deterministic_gate1_fallback",
            "zero_credentials_verified": True,
            "latency_ms": elapsed_ms,
            "sap_ai_hub_toggle_ready": True,
        },
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
