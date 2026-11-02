"""AegisChain Signal Classifier Module.

Provides deterministic and GenAI-capable signal ingestion and classification for
autonomous maritime cold-chain disruption monitoring.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("aegischain.classifier")


class SignalClassifier:
    """Classifies maritime disruption news, feeds, and alerts into structured signals.

    Operates in two modes:
      1. 'deterministic': High-precision local heuristic/regex parsing for zero-credential
         environments (e.g. SAP BTP sandbox Gate 1 fallback).
      2. 'genai_hub': Integration hook for SAP AI Core / Generative AI Hub foundation
         models (requires provisioned BTP service credentials).
    """

    SUPPORTED_MODES = ("deterministic", "genai_hub")

    # Target chokepoints and waterways
    CHOKEPOINT_PATTERNS = [
        r"\bbab\s+el-?mandeb\b",
        r"\bmandeb\b",
        r"\bred\s+sea\b",
        r"\bhouthi\b",
        r"\bsuez(?:\s+canal)?\b",
        r"\b(?:strait\s+of\s+)?hormuz\b",
        r"\bpanama\s+canal\b",
        r"\b(?:strait\s+of\s+)?malacca\b",
    ]

    # Port and terminal indicators
    PORT_PATTERNS = [
        r"\bmombasa\b",
        r"\bmba\b",
        r"\bkilindini\b",
        r"\brotterdam\b",
        r"\bjebel\s+ali\b",
        r"\bdockworkers?\b",
        r"\bgantry\s+crane\b",
        r"\byard\s+congestion\b",
        r"\bport\s+of\b",
        r"\bcontainer\s+terminal\b",
    ]

    # Tariff and trade sanctions indicators
    TARIFF_PATTERNS = [
        r"\btariff\b",
        r"\bcountervailing\b",
        r"\bcustoms\s+dut(?:y|ies)\b",
        r"\bembargo\b",
        r"\bsanctions?\b",
        r"\btrade\s+dispute\b",
        r"\banti-dumping\b",
        r"\bregulatory\s+inspection\b",
        r"\bcustoms\s+clearance\b",
        r"\bcustoms\s+border\b",
        r"\btrade\s+standoff\b",
        r"\bquota\s+restrictions?\b",
        r"\bport\s+health\s+authority\b",
    ]

    # Marine weather anomalies
    WEATHER_PATTERNS = [
        r"\bcyclone\b",
        r"\btyphoon\b",
        r"\bhurricane\b",
        r"\bgale\b",
        r"\bstorm\b",
        r"\bsquall\b",
        r"\bswell\b",
        r"\bfog\b",
        r"\bmonsoon\b",
        r"\bsevere\s+weather\b",
    ]

    def __init__(self, mode: str = "deterministic") -> None:
        """Initialize the signal classifier.

        Args:
            mode: Operational mode, either 'deterministic' or 'genai_hub'.

        Raises:
            ValueError: If an unsupported mode is provided.
        """
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported classifier mode: '{mode}'. Must be one of {self.SUPPORTED_MODES}"
            )
        self.mode = mode
        logger.info("SignalClassifier initialized in '%s' mode.", self.mode)

    def classify_signals(self, raw_feed_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse raw feed items into structured signal dictionaries.

        Args:
            raw_feed_items: List of raw news or alert dicts with text/title/content.

        Returns:
            List of structured signal dictionaries matching the downstream AegisChain contract:
                - signal_id (str): Unique signal identifier
                - title (str): Headline or title summary
                - category (str): CHOKEPOINT, PORT, TARIFF, WEATHER, or OTHER
                - severity (int): 1 (Minor), 2 (Moderate), or 3 (Critical)
                - impacted_lanes (list[str]): List of identified maritime/freight corridors
                - confidence (float): 0.0 to 1.0 confidence score
                - is_fallback (bool): True if evaluated using local Gate 1 fallback heuristics
                - summary (str): Diagnostic synthesis of the disruption

        Raises:
            NotImplementedError: When invoked in 'genai_hub' mode without runtime setup.
        """
        if self.mode == "genai_hub":
            raise NotImplementedError(
                "SAP Generative AI Hub integration requires active BTP service bindings.\n"
                "Runtime Configuration Steps:\n"
                "  1. Provision an 'aicore' standard plan service instance on your SAP BTP subaccount.\n"
                "  2. Create an SAP AI Core service key and export:\n"
                "     - BTP_AICORE_CLIENT_ID\n"
                "     - BTP_AICORE_CLIENT_SECRET\n"
                "     - BTP_AICORE_AUTH_URL\n"
                "     - BTP_AICORE_BASE_URL\n"
                "     - BTP_AICORE_RESOURCE_GROUP\n"
                "  3. Deploy a foundation model (e.g. gpt-4o or gemini-1.5-pro) in SAP AI Launchpad.\n"
                "  4. Set AI_HUB_MODEL_DEPLOYMENT_ID in your environment.\n"
                "Operating under official Gate 1 Fallback Plan: Use mode='deterministic' for local execution."
            )

        structured_signals: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_feed_items, start=1):
            signal_id = str(item.get("signal_id") or item.get("id") or f"SIG-{idx:04d}")
            text = (
                item.get("text")
                or item.get("title")
                or item.get("headline")
                or item.get("content")
                or ""
            )
            title = item.get("title") or (text[:80] + "..." if len(text) > 80 else text)

            category, severity, lanes, confidence, summary = self._parse_deterministic_item(text)

            structured_signals.append(
                {
                    "signal_id": signal_id,
                    "title": title,
                    "category": category,
                    "severity": severity,
                    "impacted_lanes": lanes,
                    "confidence": round(confidence, 3),
                    "is_fallback": True,
                    "summary": summary,
                }
            )

        return structured_signals

    def _parse_deterministic_item(
        self, text: str
    ) -> Tuple[str, int, List[str], float, str]:
        """Apply deterministic heuristics and regex pattern matching to text."""
        t = text.lower()

        # Match category rules
        is_chokepoint = any(re.search(pat, t) for pat in self.CHOKEPOINT_PATTERNS)
        is_port = any(re.search(pat, t) for pat in self.PORT_PATTERNS)
        is_tariff = any(re.search(pat, t) for pat in self.TARIFF_PATTERNS)
        is_weather = any(re.search(pat, t) for pat in self.WEATHER_PATTERNS)

        lanes: List[str] = []

        if is_chokepoint:
            category = "CHOKEPOINT"
            confidence = 0.98

            # Extract impacted lanes
            if any(x in t for x in ["bab el-mandeb", "mandeb", "red sea", "houthi"]):
                lanes.extend(["RED_SEA", "ASIA_EUROPE"])
            if "cape of good hope" in t:
                if "CAPE_OF_GOOD_HOPE" not in lanes:
                    lanes.insert(1, "CAPE_OF_GOOD_HOPE")
            if "suez" in t:
                lanes.extend(["SUEZ", "ASIA_EUROPE"])
            if "hormuz" in t:
                lanes.extend(["HORMUZ", "MIDDLE_EAST"])
            if "panama canal" in t:
                lanes.append("PANAMA_CANAL")
            if "malacca" in t:
                lanes.extend(["MALACCA", "ASIA_EUROPE"])

            # Assess severity
            if any(
                w in t
                for w in [
                    "missile",
                    "attack",
                    "strike",
                    "suspend",
                    "halting",
                    "halted",
                    "seize",
                    "mine",
                    "aground",
                    "divert",
                ]
            ):
                severity = 3
            elif any(
                w in t
                for w in [
                    "warning",
                    "advisory",
                    "maintenance",
                    "restriction",
                    "spoofing",
                    "jamming",
                    "drought",
                    "dredging",
                    "drone",
                ]
            ):
                severity = 2
            else:
                severity = 1

            summary = (
                f"Critical maritime chokepoint transit alert ({category}) affecting key global arteries."
            )

        elif is_port:
            category = "PORT"
            confidence = 0.96

            if any(re.search(x, t) for x in ["mombasa", r"\bmba\b", "kilindini"]):
                lanes.extend(["EAST_AFRICA", "MOMBASA_PORT"])
            elif "rotterdam" in t:
                lanes.append("EUROPE_GATEWAY")
            elif "jebel ali" in t:
                lanes.append("MIDDLE_EAST")

            if any(w in t for w in ["wildcat", "strike", "paralyz"]):
                severity = 3
            elif any(
                w in t
                for w in [
                    "congestion",
                    "dwell time",
                    "breakdown",
                    "collapse",
                    "walkout",
                    "power grid",
                    "failure",
                ]
            ):
                severity = 2
            else:
                severity = 1

            summary = f"Port terminal disruption ({category}) threatening local dwell and berthing."

        elif is_tariff:
            category = "TARIFF"
            confidence = 0.95

            if "asian" in t and ("vials" in t or "packaging" in t):
                lanes.extend(["TRANS_PACIFIC", "ASIA_EUROPE"])
            elif "bilateral" in t or "excipients" in t:
                lanes.append("TRANS_PACIFIC")
            else:
                lanes.append("GLOBAL_TRADE")

            if "anti-dumping" in t or "document audit" in t:
                severity = 1
            elif any(w in t for w in ["embargo", "emergency", "halts clearance"]):
                severity = 3
            elif any(
                w in t
                for w in [
                    "freeze",
                    "tariff",
                    "countervailing",
                    "sanctions",
                    "trade dispute",
                    "duties",
                    "25%",
                    "30%",
                    "15%",
                ]
            ):
                severity = 2
            else:
                severity = 1

            summary = (
                f"Cross-border customs or regulatory barrier ({category}) impacting pharmaceutical imports."
            )

        elif is_weather:
            category = "WEATHER"
            confidence = 0.94

            if "indian ocean" in t or "cheneso" in t:
                lanes.extend(["INDIAN_OCEAN", "EAST_AFRICA"])
            elif "typhoon" in t or "luzon" in t:
                lanes.extend(["TRANS_PACIFIC", "ASIA_PACIFIC"])
            elif "north atlantic" in t:
                lanes.append("NORTH_ATLANTIC")
            elif "arabian sea" in t:
                lanes.append("ARABIAN_SEA")
            elif "english channel" in t or "north sea" in t:
                lanes.append("NORTH_SEA")

            if any(w in t for w in ["category 4", "category 5", "super typhoon"]):
                severity = 3
            else:
                severity = 2

            summary = f"Severe marine weather phenomenon ({category}) impeding vessel transit safety."

        else:
            category = "OTHER"
            severity = 1
            lanes = []
            confidence = 0.90
            summary = "No maritime or cold-chain supply disruption indicators detected in item."

        # Deduplicate lanes preserving ordered precedence
        dedup_lanes: List[str] = []
        for lane in lanes:
            if lane not in dedup_lanes:
                dedup_lanes.append(lane)

        return category, severity, dedup_lanes, confidence, summary
