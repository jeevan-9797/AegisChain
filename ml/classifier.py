"""AegisChain Signal Classifier Module.

Provides deterministic, LLM proxy, and GenAI-capable signal ingestion and classification for
autonomous maritime cold-chain disruption monitoring.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("aegischain.classifier")


class SignalClassifier:
    """Classifies maritime disruption news, feeds, and alerts into structured signals.

    Operates in three modes:
      1. 'deterministic': High-precision local heuristic/regex parsing for zero-credential
         environments (e.g. SAP BTP sandbox Gate 1 fallback).
      2. 'llm_proxy': Live AI agent classification via SwappableLLMClient (Google AI Studio proxy)
         with automatic, seamless fallback to the deterministic regex engine.
      3. 'genai_hub': Integration hook for SAP AI Core / Generative AI Hub foundation
         models (requires provisioned BTP service credentials).
    """

    SUPPORTED_MODES = ("deterministic", "genai_hub", "llm_proxy")

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
            mode: Operational mode: 'deterministic', 'llm_proxy', or 'genai_hub'.

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
                "Operating under official Gate 1 Fallback Plan: Use mode='deterministic' or 'llm_proxy'."
            )

        if self.mode == "llm_proxy":
            try:
                return self._classify_via_llm(raw_feed_items)
            except Exception as exc:
                logger.warning(
                    "LLM Proxy classification encountered error: %s. Engaging deterministic fallback.",
                    exc,
                )
                return self._classify_deterministic(raw_feed_items, is_fallback=True)

        return self._classify_deterministic(raw_feed_items, is_fallback=True)

    def _classify_via_llm(
        self, raw_feed_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Classify signals using SwappableLLMClient with structured JSON schema."""
        from ml.llm_client import SwappableLLMClient

        client = SwappableLLMClient()

        # Format input items for prompt
        prepared_items = []
        for idx, item in enumerate(raw_feed_items, start=1):
            s_id = str(item.get("signal_id") or item.get("id") or f"SIG-{idx:04d}")
            text = (
                item.get("text")
                or item.get("title")
                or item.get("headline")
                or item.get("content")
                or ""
            )
            prepared_items.append({"signal_id": s_id, "text": text})

        system_instruction = (
            "You are AegisChain's autonomous maritime & pharmaceutical supply chain disruption classifier. "
            "Analyze each news headline/feed item and classify it into structured signals.\n\n"
            "Classification Rules:\n"
            "1. category: Exactly one of ['CHOKEPOINT', 'PORT', 'TARIFF', 'WEATHER', 'OTHER']\n"
            "   - CHOKEPOINT: Maritime transit straits/canals (Bab el-Mandeb, Red Sea, Suez, Hormuz, Panama, Malacca, Cape route).\n"
            "   - PORT: Terminal strikes, dockworker walkouts, container yard congestion (Mombasa/MBA, Kilindini, Rotterdam, Jebel Ali).\n"
            "   - TARIFF: Customs duties, API tariffs, export bans, sanitary/pharma regulatory embargoes, Section 301.\n"
            "   - WEATHER: Cyclones, typhoons, gales, severe storms, ocean swell impeding vessels.\n"
            "   - OTHER: Unrelated news, sports, entertainment, tech gadgets, general consumer finance.\n\n"
            "2. severity: Integer 1 (Minor/Advisory), 2 (Moderate/Disruption), 3 (Critical/Closure/Missile Strike/Paralysis/Embargo)\n\n"
            "3. impacted_lanes: List of strings chosen strictly from: "
            "['RED_SEA', 'ASIA_EUROPE', 'SUEZ', 'HORMUZ', 'MIDDLE_EAST', 'EAST_AFRICA', 'MOMBASA_PORT', "
            "'PANAMA_CANAL', 'MALACCA', 'EUROPE_GATEWAY', 'TRANS_PACIFIC', 'ASIA_PACIFIC', 'NORTH_ATLANTIC', "
            "'ARABIAN_SEA', 'NORTH_SEA', 'GLOBAL_TRADE', 'CAPE_OF_GOOD_HOPE']. For OTHER items, use empty list [].\n\n"
            "4. confidence: Float between 0.85 and 1.0.\n"
            "5. summary: Concise 1-sentence diagnostic summary.\n\n"
            "Return JSON matching this exact structure:\n"
            "{\n"
            '  "signals": [\n'
            '    {"signal_id": "string", "title": "string", "category": "string", "severity": 1, '
            '"impacted_lanes": ["string"], "confidence": 0.95, "summary": "string"}\n'
            "  ]\n"
            "}"
        )

        prompt = (
            f"Please classify the following {len(prepared_items)} feed items:\n"
            f"{json.dumps(prepared_items, indent=2)}"
        )

        response_dict = client.generate_structured_json(
            prompt=prompt, system_instruction=system_instruction
        )

        signals_raw = response_dict.get("signals") or response_dict.get("items") or []
        if not isinstance(signals_raw, list):
            raise ValueError(f"LLM did not return a signals list: {response_dict}")

        # Index signals by ID for robust mapping
        signals_by_id = {str(s.get("signal_id", "")): s for s in signals_raw}

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

            llm_item = signals_by_id.get(signal_id)
            if not llm_item and idx - 1 < len(signals_raw):
                llm_item = signals_raw[idx - 1]

            if llm_item and llm_item.get("category") in (
                "CHOKEPOINT",
                "PORT",
                "TARIFF",
                "WEATHER",
                "OTHER",
            ):
                category = str(llm_item["category"])
                severity = int(llm_item.get("severity", 1))
                lanes = list(llm_item.get("impacted_lanes", []))
                confidence = float(llm_item.get("confidence", 0.95))
                summary = str(llm_item.get("summary", title))

                structured_signals.append(
                    {
                        "signal_id": signal_id,
                        "title": title,
                        "category": category,
                        "severity": severity,
                        "impacted_lanes": lanes,
                        "confidence": round(confidence, 3),
                        "is_fallback": False,
                        "summary": summary,
                    }
                )
            else:
                # Individual item fallback if LLM omitted or corrupted this item
                cat, sev, lanes, conf, summ = self._parse_deterministic_item(text)
                structured_signals.append(
                    {
                        "signal_id": signal_id,
                        "title": title,
                        "category": cat,
                        "severity": sev,
                        "impacted_lanes": lanes,
                        "confidence": round(conf, 3),
                        "is_fallback": True,
                        "summary": summ,
                    }
                )

        return structured_signals

    def _classify_deterministic(
        self, raw_feed_items: List[Dict[str, Any]], is_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """Apply deterministic heuristics and regex pattern matching to all feed items."""
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
                    "is_fallback": is_fallback,
                    "summary": summary,
                }
            )

        return structured_signals

    def _parse_deterministic_item(
        self, text: str
    ) -> Tuple[str, int, List[str], float, str]:
        """Apply deterministic heuristics and regex pattern matching to a single text item."""
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
