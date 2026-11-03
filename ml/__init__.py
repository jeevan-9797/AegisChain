"""AegisChain AI/ML Intelligence & Scoring Module.

Autonomous pharma cold-chain disruption response platform for SAP Hackfest 2026.
Designed for zero-credential resilience in SAP BTP / Learning Hub sandbox environments
under the official Gate 1 Fallback Plan.

Public API:
    - SignalClassifier: Ingestion & categorization of maritime, port, tariff, and weather alerts.
    - AegisPredictiveCore: Scikit-learn estimators for lane transit delays and cold-chain spoilage.
    - run_incident_evaluation: Orchestration entry point producing UI/CAP-ready decision payloads.
"""

from ml.classifier import SignalClassifier
from ml.engine import run_incident_evaluation
from ml.models import AegisPredictiveCore

__version__ = "1.0.0-gate1"
__all__ = [
    "SignalClassifier",
    "AegisPredictiveCore",
    "run_incident_evaluation",
]
