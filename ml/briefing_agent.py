"""AegisChain Executive Briefing Agent.

Generates grounded, human-in-the-loop executive decision memoranda for pharmaceutical supply
chain directors during active maritime and cold-chain disruptions.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("aegischain.briefing_agent")


class ExecutiveBriefingAgent:
    """Generates structured decision briefings for supply chain executives.

    Utilizes SwappableLLMClient (Google AI Studio gemini-2.5-flash proxy or SAP Generative AI Hub)
    with a robust deterministic templated fallback for zero-credential sandboxes.
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """Initialize the executive briefing agent."""
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            from ml.llm_client import SwappableLLMClient

            self.llm_client = SwappableLLMClient()

    def generate_brief(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a grounded executive briefing from evaluated incident data.

        Args:
            incident_data: End-to-end evaluation payload containing cargo profile,
                           classified signals, scenario simulations, and optimization.

        Returns:
            Structured JSON dictionary containing:
              - executive_summary (str): Operational synthesis of the crisis
              - recommended_action (str): Specific routing and logistics plan
              - risk_mitigation (str): Cold-chain compliance & telemetry protocols
              - financial_impact (str): Cargo loss avoided and cost differentials
              - sign_off_status (str): "AWAITING_HUMAN_APPROVAL"
              - is_fallback (bool): True if generated via deterministic template
              - generated_at (str): ISO-8601 timestamp
        """
        try:
            return self._generate_brief_via_llm(incident_data)
        except Exception as exc:
            logger.warning(
                "Executive briefing LLM generation encountered error: %s. "
                "Engaging deterministic template fallback.",
                exc,
            )
            return self._deterministic_brief_fallback(incident_data)

    def _generate_brief_via_llm(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call SwappableLLMClient to author a dynamic executive memorandum."""
        cargo = incident_data.get("cargo_profile", {})
        opt = incident_data.get("decision_optimization", {})
        scenarios = incident_data.get("scenarios", {})
        signals_summary = incident_data.get("signals_summary", {})
        incident_id = incident_data.get("incident_id", "SAP-8842")

        system_instruction = (
            "You are AegisChain's Chief Supply Chain Risk Officer (CSCO) Briefing Agent. "
            "Author a formal, concise, and rigorous executive decision briefing for "
            "pharmaceutical directors regarding an active maritime cold-chain disruption.\n\n"
            "Required Output Structure (JSON only):\n"
            "{\n"
            '  "executive_summary": "High-level summary of active threat, cargo viability, and urgency.",\n'
            '  "recommended_action": "Specific chosen routing plan and logistical steps.",\n'
            '  "risk_mitigation": "Cold-chain SOPs, 2-8°C temperature logging, customs green lanes, transfer protocols.",\n'
            '  "financial_impact": "Precise economic breakdown (freight vs cargo value saved vs detour spoilage).",\n'
            '  "sign_off_status": "AWAITING_HUMAN_APPROVAL"\n'
            "}\n\n"
            "Grounding Rules:\n"
            "- Strictly ground all numbers and scenario details in the provided evaluation payload.\n"
            "- Do not invent alternative currencies, costs, or dates.\n"
            "- Emphasize that Option C (Sea-Air Hybrid via Jebel Ali) keeps transit well within the 9-day thermal window.\n"
            "- State that Option A (Cape detour) causes ~92% spoilage due to transit exceeding the thermal budget."
        )

        prompt = (
            f"Active Incident ID: {incident_id}\n"
            f"Cargo Profile: {json.dumps(cargo, indent=2)}\n"
            f"Threats Detected: {json.dumps(signals_summary, indent=2)}\n"
            f"Scenario Evaluations: {json.dumps(scenarios, indent=2)}\n"
            f"Optimization Decision: {json.dumps(opt, indent=2)}\n\n"
            "Generate the formal Executive Decision Briefing in JSON format."
        )

        result = self.llm_client.generate_structured_json(
            prompt=prompt, system_instruction=system_instruction
        )

        # Validate presence of required keys
        required_keys = (
            "executive_summary",
            "recommended_action",
            "risk_mitigation",
            "financial_impact",
        )
        for key in required_keys:
            if not result.get(key):
                raise ValueError(f"LLM response missing required briefing field: '{key}'")

        return {
            "executive_summary": str(result["executive_summary"]),
            "recommended_action": str(result["recommended_action"]),
            "risk_mitigation": str(result["risk_mitigation"]),
            "financial_impact": str(result["financial_impact"]),
            "sign_off_status": "AWAITING_HUMAN_APPROVAL",
            "is_fallback": False,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def _deterministic_brief_fallback(
        self, incident_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Produce an authoritative deterministic executive briefing template."""
        cargo = incident_data.get("cargo_profile", {})
        opt = incident_data.get("decision_optimization", {})
        scenarios = incident_data.get("scenarios", {})
        opt_c = scenarios.get("OPTION_C_SPLIT", {})
        opt_a = scenarios.get("OPTION_A_CAPE", {})
        opt_b = scenarios.get("OPTION_B_AIR", {})
        savings = opt.get("financial_savings", {})

        product = cargo.get("product", "Insulin Glargine")
        doses = cargo.get("quantity_doses", 40000)
        val_usd = float(cargo.get("cargo_value_usd", 450000.0))
        budget_days = float(cargo.get("thermal_budget_days", 9.0))
        incident_id = incident_data.get("incident_id", "SAP-8842")

        c_delay = opt_c.get("extra_delay_days", 2.39)
        c_risk = opt_c.get("spoilage_risk_pct", "2.9%")
        c_net = opt_c.get("net_economic_impact_usd", 51415.0)
        c_freight = opt_c.get("extra_freight_usd", 38500.0)
        c_loss = opt_c.get("expected_cargo_loss_usd", 12915.0)

        savings_cape = savings.get("vs_cape_detour_usd", 376585.0)
        savings_air = savings.get("vs_full_air_charter_usd", 52225.0)

        return {
            "executive_summary": (
                f"CRITICAL DISRUPTION ALERT: Southern Red Sea and Bab el-Mandeb transit corridors are closed "
                f"to commercial container vessels. Consignment {incident_id} carrying {doses:,} doses of {product} "
                f"(invoice value: ${val_usd:,.2f}) has a strict thermal budget of {budget_days:.1f} days at 2°C–8°C. "
                f"Traditional maritime rerouting via the Cape of Good Hope adds +17.9 days of delay, exceeding the "
                f"thermal buffer by 8.9 days and resulting in 92.0% catastrophic cargo spoilage ($414,000 loss). "
                f"Immediate multimodal intervention is required."
            ),
            "recommended_action": (
                f"Execute OPTION_C_SPLIT: Multimodal Sea-Air Hybrid via Jebel Ali (Dubai) Hub. "
                f"Ocean container will divert to Jebel Ali container terminal, followed by immediate cross-docking "
                f"into active temperature-controlled air cargo (Envirotainer e2 / RAP ULD) for direct scheduled airfreight "
                f"into Moi International Airport (Mombasa, Kenya). Total transit delay is capped at +{c_delay} days, "
                f"arriving safely within the {budget_days:.0f}-day thermal window."
            ),
            "risk_mitigation": (
                "1. Continuous Telemetry: Activate real-time cellular/BLE IoT data loggers monitoring internal temp (2°C–8°C), "
                "battery reserve, and tilt events with 15-minute sync intervals.\n"
                "2. Customs Green Lane: Pre-clear importation with Kenya Revenue Authority (KRA) and Pharmacy and Poisons Board "
                "under expedited humanitarian relief protocols prior to flight touchdown.\n"
                "3. Tarmac Protocol: Require dedicated refrigerated dollies during apron transfer at Dubai (DXB) and "
                "immediate transfer to Nairobi/Mombasa temperature-controlled pharmaceutical bonded warehouses."
            ),
            "financial_impact": (
                f"Total net economic impact of Option C is ${c_net:,.2f} (Extra Freight: ${c_freight:,.2f} + Expected Cargo Loss: ${c_loss:,.2f}). "
                f"This mathematically saves ${savings_cape:,.2f} compared to the Cape maritime detour loss ($428,000), "
                f"while saving ${savings_air:,.2f} compared to emergency full air charter ($103,640) which exceeds standard budgetary caps."
            ),
            "sign_off_status": "AWAITING_HUMAN_APPROVAL",
            "is_fallback": True,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
