# AegisChain — AI/ML Intelligence & Scoring Module

> **SAP Hackfest 2026** | Track: Autonomous Supply Chain Resiliency
> **Package**: `ml/` (Self-Contained Autonomous Decision Engine)
> **Status**: Gate 1 Fallback Approved (`v1.0.0-gate1`)

---

## 1. Executive Summary & Gate 1 Fallback Rationale

In enterprise SAP BTP and Learning Hub sandbox environments, **SAP AI Core** service keys and subaccount provisioning can frequently be restricted, pending approval, or quota-limited.

In accordance with our official **Gate 1 Fallback Plan**, the `ml/` module delivers a fully functional, deterministic, and modular machine learning package running directly inside **SAP Business Application Studio (BAS)** or any standard Node.js/Python container runtime:
- **Zero Cloud Credentials Required**: Operates independently of external API keys, service bindings, or cloud tokens.
- **Identical Downstream Contract**: Exposes the exact same JSON schema and evaluation contract to the SAP Cloud Application Programming Model (CAP) backend as the cloud-hosted SAP Generative AI Hub will.
- **Zero-Friction Transition**: When SAP AI Core credentials are provisioned, toggling `mode="genai_hub"` connects to foundation models (e.g., GPT-4o, Gemini 1.5 Pro) without altering CAP service interfaces, database tables, or SAP UI5 / Fiori components.

---

## 2. Architecture & Module Design

```
AegisChain/ml/
│
├── __init__.py           # Public API: SignalClassifier, AegisPredictiveCore, run_incident_evaluation
├── classifier.py         # SignalClassifier (deterministic heuristic parser + genai_hub toggle)
├── models.py             # AegisPredictiveCore (GradientBoostingRegressor & GradientBoostingClassifier)
├── engine.py             # Unified incident orchestration pipeline & JSON payload generator
├── eval_dataset.json     # Ground-truth evaluation dataset (40 realistic test headlines)
├── benchmark.py          # Validation runner (Accuracy, Precision, Recall, Hallucination audit)
└── README.md             # Technical architecture & integration documentation
```

### Module Responsibilities

1. **`ml/classifier.py` (`SignalClassifier`)**:
   - Parses unstructured maritime disruption alerts, port notices, tariff announcements, and weather bulletins.
   - Detects critical chokepoints (`BAB_EL_MANDEB`, `SUEZ`, `HORMUZ`, `PANAMA_CANAL`, `MALACCA`).
   - Identifies port bottlenecks (`MOMBASA / MBA`, `KILINDINI`, `ROTTERDAM`, `JEBEL ALI`).
   - Tags tariff hikes, medical API import bans, and regulatory clearance delays.
   - Outputs standardized disruption dicts with severity levels (1 to 3), confidence scores, and impacted freight corridors.
   - Guarantees **0.0% hallucinated lanes** on noise articles.

2. **`ml/models.py` (`AegisPredictiveCore`)**:
   - **Lane Delay Model (`GradientBoostingRegressor`)**: Predicts net transit delay days based on `[base_days, security_risk (0-1), congestion_index (1-5), season (1-4)]`.
   - **Spoilage Risk Model (`GradientBoostingClassifier`)**: Predicts pharmaceutical viability loss probability based on `[days_over_viability, reefer_health (0-1), transshipments, mode_mix (1=sea, 2=air, 3=split)]`.
   - Evaluates rerouting options matching presentation Case **#SAP-8842** (40,000 insulin doses, $450,000 value, 9-day thermal window).

3. **`ml/engine.py` (`run_incident_evaluation`)**:
   - Ingests feeds, classifies signals, executes multi-scenario predictive scoring, and identifies the mathematically optimal response with lowest net economic impact.
   - Emits a structured JSON payload ready for CAP consumption and SAP UI5 Control Tower visualization.

---

## 3. Case Study #SAP-8842: Mathematical Proof

### Scenario Context
- **Consignment**: 40,000 Insulin Glargine doses ($450,000 invoice replacement value)
- **Active Incident**: Houthi missile strikes near Bab el-Mandeb; southern Red Sea corridor closed
- **Thermal Preservation Window**: 9 days passive thermal buffer in Credo VIP shippers
- **Formulae**:
  $$\text{Expected Cargo Loss} = \text{Spoilage Probability} \times \text{Cargo Value (\$450,000)}$$
  $$\text{Net Economic Impact} = \text{Extra Freight Cost} + \text{Expected Cargo Loss}$$

### Scenario Comparison Table

| Scenario Key | Description | Delay Days | Spoilage Risk | Extra Freight | Cargo Loss | Net Economic Impact | Viability Status | Recommendation |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`OPTION_A_CAPE`** | Cape of Good Hope Detour | **+17.9 d** | **92.0%** | \$14,000 | \$414,000 | **\$428,000** | **BREACHED** (+8.9d over budget) | Unacceptable Loss |
| **`OPTION_B_AIR`** | Full Air Charter | **+1.5 d** | **1.9%** | \$95,000 | \$8,640 | **\$103,640** | **SECURE** (-7.5d under budget) | Budget Cap Exceeded |
| **`OPTION_C_SPLIT`** | **Sea-Air Hybrid (Jebel Ali)** | **+2.4 d** | **2.9%** | **\$38,500** | **\$12,915** | **\$51,415** | **SECURE** (-6.6d under budget) | **OPTIMAL DISPATCH** |

### Decision Delta
- **Savings vs. Cape Maritime Detour**: Saves **\$376,585.00** by preventing catastrophic insulin spoilage.
- **Savings vs. Full Air Charter**: Saves **\$52,225.00** over expensive air chartering while keeping the cold-chain strictly within its 9-day thermal envelope.

---

## 4. Standalone Python CLI Protocol

`ml.cli` provides a versioned JSON stdin/stdout boundary around the existing
`run_incident_evaluation()` function. It does not change evaluator behavior or
persist CAP records. The protocol intentionally contains no CAP shipment or
inventory IDs.

Run it from the repository root:

```bash
python -m ml.cli < request.json
```

The input must be one JSON object with exactly these fields:

```json
{
  "schemaVersion": 1,
  "feed_items": [
    {
      "id": "SIG-8842-01",
      "text": "Houthi missile barrage strikes a vessel off Bab el-Mandeb."
    }
  ],
  "cargo_value": 450000,
  "incident_id": "SAP-8842"
}
```

On success, stdout contains one JSON line with the evaluator's existing result.
Invalid envelopes and evaluator failures write diagnostics to stderr and exit
nonzero; empty stdin never triggers the engine's built-in sample feed. Cargo
and feed-entry validation remains in `run_incident_evaluation()`.

This CLI is the Python-side protocol only. A CAP process adapter, timeout and
process management, response validation, and CAP persistence remain future work.

---

## 5. Transitioning to SAP Generative AI Hub

The module is architected with complete interface symmetry. To activate SAP Generative AI Hub:

1. In your SAP BTP Subaccount, provision an instance of the `aicore` service.
2. Bind the instance or generate a service key:
   ```json
   {
     "clientid": "<YOUR_CLIENT_ID>",
     "clientsecret": "<YOUR_CLIENT_SECRET>",
     "url": "https://<SUBACCOUNT>.authentication.eu10.hana.ondemand.com",
     "serviceurls": {
       "AI_API_URL": "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com"
     }
   }
   ```
3. Set the environment variables in Business Application Studio (`.env`):
   ```bash
   BTP_AICORE_CLIENT_ID="<clientid>"
   BTP_AICORE_CLIENT_SECRET="<clientsecret>"
   BTP_AICORE_AUTH_URL="<url>"
   BTP_AICORE_BASE_URL="<serviceurls.AI_API_URL>"
   BTP_AICORE_RESOURCE_GROUP="default"
   AI_HUB_MODEL_DEPLOYMENT_ID="<deployment_id>"
   ```
4. Initialize the classifier with `mode="genai_hub"`:
   ```python
   from ml import SignalClassifier
   classifier = SignalClassifier(mode="genai_hub")
   ```
   *No changes to downstream CAP handlers or UI bindings are required.*

---

## 6. Benchmarks & Validation Results

### Local setup and unit tests

From the repository root, install the pinned runtime dependencies and run the
standard-library unit tests:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s ml/tests -v
```

The direct runtime dependencies are pinned in `requirements.txt`. The public
`run_incident_evaluation()` function requires `cargo_value` to be numeric,
finite, and greater than zero. Feed entries must be mappings; invalid values
raise `ValueError` with the offending field or entry index.

The benchmark suite evaluates `SignalClassifier` against a ground-truth dataset of 40 diverse headlines (`ml/eval_dataset.json`):
- **15 Maritime Disruption Events**: Bab el-Mandeb missile strikes, Suez groundings, Hormuz seizures, Mombasa port strikes (MBA), Kilindini gantry failures, Rotterdam walkouts, Jebel Ali power outages.
- **10 Tariff & Trade Sanctions**: API countervailing tariffs, biologic import embargoes, Section 301 duties on medical glass vials, cold-chain regulatory inspections.
- **5 Marine Weather Events**: Category 4 cyclones, Super Typhoons, North Atlantic winter gales, Arabian Sea monsoons.
- **10 Irrelevant Noise Items**: Sports results, consumer electronics, movies, astronomy, culinary arts, fashion.

### Reproduction Command
```bash
python ml/benchmark.py
```

### Verified Benchmark Scorecard
```
================================================================================
        AEGISCHAIN AI/ML BENCHMARK - SAP HACKFEST 2026 GATE 1 AUDIT
================================================================================
Dataset: 40 Ground-Truth Disruption & Noise Items
Runtime Mode: Deterministic Local Fallback (scikit-learn / Regex Engine)
Target: Overall Accuracy >= 90.0% | Hallucinated Lanes == 0.0%
--------------------------------------------------------------------------------

Category       | Support  | Precision  | Recall     | F1-Score
--------------------------------------------------------------
CHOKEPOINT     | 10       |    100.0% |    100.0% |    100.0%
PORT           | 5        |    100.0% |    100.0% |    100.0%
TARIFF         | 10       |    100.0% |    100.0% |    100.0%
WEATHER        | 5        |    100.0% |    100.0% |    100.0%
OTHER          | 10       |    100.0% |    100.0% |    100.0%
--------------------------------------------------------------
TOTAL / MACRO  | 40       |    100.0% |    100.0% |    100.0%

================================================================================
                     EXECUTIVE SCORECARD & GATE 1 METRICS
================================================================================
Overall Category Accuracy : 100.00% (Target: >= 90.0%)  [PASS]
Severity Classification   : 100.00% (MAE: 0.00)
Total Lanes Evaluated     : 46 Predicted / 46 Ground Truth
Lane Match Precision      : 100.00%
Lane Retrieval Recall     : 100.00%
Hallucinated Lanes        : 0  (0.00%)            [PASS]
Noise Lane False Positives: 0  (0.00%)            [PASS]
Inference Latency         : 0.100 ms/item (4.0 ms total batch)
Throughput                : 10,011 items/second
================================================================================

>> GATE 1 AUDIT STATUS: APPROVED FOR PRODUCTION CAP INTEGRATION <<
```
