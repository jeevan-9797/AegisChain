"""AegisChain AI/ML Intelligence & Scoring Module.

Autonomous pharma cold-chain disruption response platform for SAP Hackfest 2026.
Designed for zero-credential resilience in SAP BTP / Learning Hub sandbox environments
under the official Gate 1 Fallback Plan, with modular Google AI Studio / SAP AI Hub proxies.

Public API:
    - SignalClassifier: Ingestion & categorization of maritime, port, tariff, and weather alerts.
    - AegisPredictiveCore: Scikit-learn estimators for lane transit delays and cold-chain spoilage.
    - ExecutiveBriefingAgent: CSCO human-in-the-loop decision brief authoring agent.
    - SwappableLLMClient: Adapter pattern for Google AI Studio proxy and SAP Generative AI Hub.
    - run_incident_evaluation: Orchestration entry point producing UI/CAP-ready decision payloads.
"""

from ml.briefing_agent import ExecutiveBriefingAgent
from ml.classifier import SignalClassifier
from ml.engine import run_incident_evaluation
from ml.llm_client import SwappableLLMClient
from ml.models import AegisPredictiveCore

__version__ = "1.1.0-adapter"
__all__ = [
    "SignalClassifier",
    "AegisPredictiveCore",
    "ExecutiveBriefingAgent",
    "SwappableLLMClient",
    "run_incident_evaluation",
]
