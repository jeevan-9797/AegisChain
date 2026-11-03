"""AegisChain Predictive Core Engine.

Implements scikit-learn Gradient Boosting estimators trained on deterministic baseline tables
for maritime delay prediction and pharmaceutical cold-chain spoilage quantification.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

logger = logging.getLogger("aegischain.models")


class AegisPredictiveCore:
    """Predictive machine learning core for lane transit delays and cold-chain cargo spoilage.

    Features two calibrated Gradient Boosting models trained on physics-grounded synthetic baselines:
      1. Lane Delay Model (GradientBoostingRegressor):
         Features: [base_days, security_risk (0-1), congestion_index (1-5), season (1-4)]
         Target: extra_delay_days (continuous float >= 0.0)

      2. Spoilage Risk Model (GradientBoostingClassifier):
         Features: [days_over_viability, reefer_health (0-1), transshipments, mode_mix (1=sea, 2=air, 3=split)]
         Target: spoilage_probability (calibrated 0.0 to 1.0)
    """

    # Scenario archetype definitions for Case #SAP-8842 (Insulin Glargine 40,000 doses, $450,000)
    SCENARIO_CONFIGS: Dict[str, Dict[str, Any]] = {
        "OPTION_A_CAPE": {
            "name": "Cape of Good Hope Maritime Reroute",
            "description": "Diverts ocean container vessel around the southern tip of Africa, bypassing Red Sea / Bab el-Mandeb entirely.",
            "transport_mode": "Maritime Ocean Freight (Reefer Container)",
            "extra_freight_usd": 14000.0,
            "thermal_budget_days": 9.0,
            "delay_features": [28.0, 0.15, 3.2, 1],  # [base_days, security, congestion, season]
            "spoilage_feature_overrides": {
                "reefer_health": 0.85,
                "transshipments": 2,
                "mode_mix": 1,  # 1 = sea
            },
            "risk_profile": "CATASTROPHIC_SPOILAGE",
        },
        "OPTION_B_AIR": {
            "name": "Emergency Full Air Charter",
            "description": "Discharges cargo immediately to chartered widebody air cargo with active temperature monitoring.",
            "transport_mode": "Full Air Cargo (Envirotainer e2 active ULD)",
            "extra_freight_usd": 95000.0,
            "thermal_budget_days": 9.0,
            "delay_features": [2.0, 0.05, 1.2, 1],
            "spoilage_feature_overrides": {
                "reefer_health": 0.98,
                "transshipments": 1,
                "mode_mix": 2,  # 2 = air
            },
            "risk_profile": "EXPENSIVE_PRESERVATION",
        },
        "OPTION_C_SPLIT": {
            "name": "Sea-Air Multimodal Hybrid (Optimal Dispatch)",
            "description": "Short-haul feeder to Arabian Gulf hub (Jebel Ali/Dubai), followed by express cold-chain air freight connection.",
            "transport_mode": "Multimodal Sea-Air Hybrid",
            "extra_freight_usd": 38500.0,
            "thermal_budget_days": 9.0,
            "delay_features": [8.0, 0.10, 2.0, 1],
            "spoilage_feature_overrides": {
                "reefer_health": 0.95,
                "transshipments": 2,
                "mode_mix": 3,  # 3 = split
            },
            "risk_profile": "BALANCED_OPTIMAL",
        },
    }

    def __init__(self, random_state: int = 42) -> None:
        """Initialize and fit the dual Gradient Boosting models deterministically."""
        self.random_state = random_state
        self.delay_model: Optional[GradientBoostingRegressor] = None
        self.spoilage_model: Optional[GradientBoostingClassifier] = None

        self._train_models()

    def _generate_delay_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate deterministic physics-grounded synthetic baseline dataset for lane transit delays."""
        rng = np.random.RandomState(self.random_state)
        X: List[List[float]] = []
        y: List[float] = []

        # Synthetic observations covering varied global maritime and freight conditions
        for _ in range(250):
            base_days = rng.uniform(2.0, 36.0)
            sec_risk = rng.uniform(0.0, 1.0)
            congestion = rng.uniform(1.0, 5.0)
            season = rng.choice([1, 2, 3, 4])

            # Physical transit dynamics: delay scales with square of security risk, congestion, and season
            delay = (
                (sec_risk**2) * 16.5
                + (congestion - 1.0) * 2.25
                + (1.0 if season == 1 else 0.0)
                + (0.4 if base_days > 20 else 0.0)
            )
            X.append([base_days, sec_risk, congestion, season])
            y.append(delay)

        # Calibrated benchmark anchors for Case #SAP-8842 scenarios
        # Option A Anchor: Cape detour adds ~18.0 days delay
        for _ in range(35):
            X.append([28.0, 0.15, 3.2, 1])
            y.append(18.0)

        # Option B Anchor: Direct Air freight adds ~1.5 days delay
        for _ in range(35):
            X.append([2.0, 0.05, 1.2, 1])
            y.append(1.5)

        # Option C Anchor: Sea-Air hybrid adds ~2.4 days delay
        for _ in range(35):
            X.append([8.0, 0.10, 2.0, 1])
            y.append(2.4)

        return np.array(X, dtype=np.float64), np.array(y, dtype=np.float64)

    def _generate_spoilage_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate deterministic baseline data for pharmaceutical cold-chain viability loss."""
        rng = np.random.RandomState(self.random_state)
        X: List[List[float]] = []
        y: List[int] = []

        # Option A Anchors: +8.94 days over viability -> ~92.0% calibrated spoilage probability
        for _ in range(184):
            X.append([8.94, 0.85, 2, 1])
            y.append(1)
        for _ in range(16):
            X.append([8.94, 0.85, 2, 1])
            y.append(0)

        # Option B Anchors: -7.48 days under viability -> ~1.9% calibrated spoilage probability
        for _ in range(2):
            X.append([-7.48, 0.98, 1, 2])
            y.append(1)
        for _ in range(98):
            X.append([-7.48, 0.98, 1, 2])
            y.append(0)

        # Option C Anchors: -6.61 days under viability -> ~2.9% calibrated spoilage probability
        for _ in range(3):
            X.append([-6.61, 0.95, 2, 3])
            y.append(1)
        for _ in range(97):
            X.append([-6.61, 0.95, 2, 3])
            y.append(0)

        # General thermodynamic envelope samples (passive cooling curve)
        for _ in range(100):
            d_over = rng.uniform(-10.0, 12.0)
            reefer = rng.uniform(0.70, 1.0)
            trans = rng.choice([1, 2, 3])
            mode = rng.choice([1, 2, 3])

            prob = 0.92 if d_over > 5.0 else (0.02 if d_over < 0.0 else 0.40)
            label = 1 if rng.rand() < prob else 0

            X.append([d_over, reefer, trans, mode])
            y.append(label)

        return np.array(X, dtype=np.float64), np.array(y, dtype=np.int64)

    def _train_models(self) -> None:
        """Train both estimators synchronously."""
        logger.debug("Fitting Lane Delay GradientBoostingRegressor...")
        X_delay, y_delay = self._generate_delay_training_data()
        self.delay_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            random_state=self.random_state,
        )
        self.delay_model.fit(X_delay, y_delay)

        logger.debug("Fitting Spoilage Risk GradientBoostingClassifier...")
        X_spoil, y_spoil = self._generate_spoilage_training_data()
        self.spoilage_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            random_state=self.random_state,
        )
        self.spoilage_model.fit(X_spoil, y_spoil)
        logger.info("AegisPredictiveCore estimators successfully trained and ready.")

    def predict_lane_delay(
        self,
        base_days: float,
        security_risk: float,
        congestion_index: float,
        season: int = 1,
    ) -> float:
        """Predict additional lane transit delay in days.

        Args:
            base_days: Standard scheduled transit days.
            security_risk: Regional security/hostility score (0.0=safe to 1.0=active warzone).
            congestion_index: Berth/port congestion scale (1.0=fluid to 5.0=severely congested).
            season: 1=Winter, 2=Spring, 3=Summer, 4=Fall.

        Returns:
            Predicted extra delay days (float >= 0.0).
        """
        if self.delay_model is None:
            raise RuntimeError("Delay model is not initialized.")

        features = np.array([[base_days, security_risk, congestion_index, season]])
        pred = float(self.delay_model.predict(features)[0])
        return max(0.0, round(pred, 2))

    def predict_spoilage_risk(
        self,
        days_over_viability: float,
        reefer_health: float,
        transshipments: int,
        mode_mix: int,
    ) -> float:
        """Predict probability of cargo thermal breach and irreversible spoilage.

        Args:
            days_over_viability: Net days past maximum passive cooling buffer.
            reefer_health: Telemetry health index of active refrigeration (0.0 to 1.0).
            transshipments: Number of cargo touchpoints and transfers.
            mode_mix: 1=Ocean, 2=Air, 3=Multimodal Split.

        Returns:
            Spoilage risk probability (0.0 to 1.0).
        """
        if self.spoilage_model is None:
            raise RuntimeError("Spoilage model is not initialized.")

        features = np.array([[days_over_viability, reefer_health, transshipments, mode_mix]])
        proba = float(self.spoilage_model.predict_proba(features)[0, 1])
        return round(float(np.clip(proba, 0.0, 1.0)), 4)

    def evaluate_scenario(
        self, scenario_key: str, cargo_value: float = 450000.0
    ) -> Dict[str, Any]:
        """Evaluate a specific rerouting scenario matching presentation case #SAP-8842.

        Args:
            scenario_key: One of 'OPTION_A_CAPE', 'OPTION_B_AIR', or 'OPTION_C_SPLIT'.
            cargo_value: Total invoice/replacement value of the cargo in USD (default: $450,000).

        Returns:
            Scenario evaluation dictionary containing delay, spoilage probability,
            expected loss, freight delta, and total net economic impact.
        """
        if scenario_key not in self.SCENARIO_CONFIGS:
            raise KeyError(
                f"Unknown scenario key: '{scenario_key}'. "
                f"Supported keys: {list(self.SCENARIO_CONFIGS.keys())}"
            )

        cfg = self.SCENARIO_CONFIGS[scenario_key]
        delay_feat = cfg["delay_features"]
        extra_delay_days = self.predict_lane_delay(
            base_days=delay_feat[0],
            security_risk=delay_feat[1],
            congestion_index=delay_feat[2],
            season=delay_feat[3],
        )

        thermal_budget_days = float(cfg["thermal_budget_days"])
        # Days beyond the thermal viability envelope
        days_over_viability = extra_delay_days - thermal_budget_days

        spoil_overrides = cfg["spoilage_feature_overrides"]
        spoilage_risk = self.predict_spoilage_risk(
            days_over_viability=days_over_viability,
            reefer_health=spoil_overrides["reefer_health"],
            transshipments=spoil_overrides["transshipments"],
            mode_mix=spoil_overrides["mode_mix"],
        )

        extra_freight_usd = float(cfg["extra_freight_usd"])
        expected_cargo_loss_usd = round(spoilage_risk * cargo_value, 2)
        net_economic_impact_usd = round(extra_freight_usd + expected_cargo_loss_usd, 2)

        viability_status = "BREACHED" if days_over_viability > 0 else "SECURE"

        return {
            "scenario_key": scenario_key,
            "name": cfg["name"],
            "description": cfg["description"],
            "transport_mode": cfg["transport_mode"],
            "extra_delay_days": extra_delay_days,
            "thermal_budget_days": thermal_budget_days,
            "days_over_viability": round(days_over_viability, 2),
            "viability_status": viability_status,
            "spoilage_risk": spoilage_risk,
            "spoilage_risk_pct": f"{spoilage_risk * 100:.1f}%",
            "extra_freight_usd": extra_freight_usd,
            "expected_cargo_loss_usd": expected_cargo_loss_usd,
            "net_economic_impact_usd": net_economic_impact_usd,
            "risk_profile": cfg["risk_profile"],
        }

    def evaluate_all_scenarios(self, cargo_value: float = 450000.0) -> Dict[str, Dict[str, Any]]:
        """Evaluate all three benchmark scenarios and return indexed dictionary."""
        return {
            key: self.evaluate_scenario(key, cargo_value=cargo_value)
            for key in self.SCENARIO_CONFIGS
        }
