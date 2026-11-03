# AegisChain — AI/ML Intelligence & Scoring Module

> **SAP Hackfest 2026** | Track: Autonomous Supply Chain Resiliency
> **Package**: `ml/` (Self-Contained Autonomous Decision Engine)
> **Status**: Gate 1 Fallback Approved (`v1.0.0-gate1`)

---

## 1. Executive Summary & Gate 1 Fallback Rationale

In enterprise SAP BTP and Learning Hub sandbox environments, **SAP AI Core** service keys and subaccount provisioning can frequently be restricted, pending approval, or quota-limited.

In accordance with our official **Gate 1 Fallback Plan**, the `ml/` module delivers a fully functional, deterministic, and modular machine learning package running directly inside **SAP Business Application Studio (BAS)** or any standard Node.js/Python container runtime:
- **Deterministic local mode**: Runs without external credentials; optional provider modes require their own configuration.
- **CAP evaluator boundary**: Produces structured JSON consumed by the CAP adapter, which validates explicit impact IDs and owns persistence.
- **Provider boundaries**: Google GenAI is optional; SAP Generative AI Hub remains a placeholder until its SDK, service bindings, and runtime configuration are implemented.

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

The CAP backend supports local subprocess and optional authenticated HTTP remote evaluator modes. CAP validates explicit impact IDs, maps one active evaluator result into a signal and linked pending recommendation, and persists them without executing recovery actions.

## Standalone HTTP service prototype

`ml.http_service` exposes the same evaluator request and response over HTTP. It
uses only the Python standard library for HTTP and does not persist CAP records.
Run locally from the repository root:

```bash
python -m pip install -r requirements.txt
python -m ml.http_service
```

The service listens on `HOST` (default `127.0.0.1` locally and `0.0.0.0` when
running under Cloud Foundry) and `PORT` (default `8082`, Cloud Foundry supplies
`PORT`). It provides `GET /healthz`, `GET /readyz`, and
`POST /internal/v1/evaluate`. The POST body is the same exact `schemaVersion: 1`
envelope described above; the response is the evaluator's existing JSON result.
Errors use `{ "error": { "code": "...", "message": "..." } }`. Invalid
JSON/envelopes return 400, evaluator input validation returns 422, oversized
requests return 413, evaluator failures return a generic 500, and a full
two-request evaluation capacity returns 503. The service never emits stack
traces or evaluator exception details for unexpected failures.

`runtime.txt` declares `python-3.13.x`, a runtime listed for the SAP BTP Cloud
Foundry Python buildpack. A future standalone CF app manifest must set the
command to `python -m ml.http_service`. The checked-in `requirements.txt` pins
NumPy, scikit-learn, and their runtime dependency set to the versions verified
in the available local Python 3.14 environment. Python 3.13 installation still
needs to be confirmed in the target buildpack/space.

The evaluator endpoint requires a shared bearer secret injected out of band.
Set `AEGISCHAIN_EVALUATOR_TOKEN` on the Python service and the same value as
`AEGISCHAIN_ML_TOKEN` on CAP. Both require at least 32 UTF-8 bytes and reject
line breaks. Generate a random secret and use the platform's secret/environment binding
mechanism rather than storing it in source, deployment descriptors, or logs.
The evaluator compares tokens in constant time and does not log authorization
headers. `GET /healthz` and `GET /readyz` remain public for platform health
probes and reveal only generic status; only `POST /internal/v1/evaluate` is
authenticated. CAP requires HTTPS for remote evaluator URLs except loopback
URLs used for local development. Keep the service route private as an additional
network control.

This is an isolated shared-secret seam, not OAuth/XSUAA integration. The repo
does not yet contain XSUAA service configuration, scopes, or a deployed CF
binding. Replace or front this seam with OAuth2 client credentials once the
team selects and provisions that BTP setup; CAP's remote adapter is the
outbound credential attachment point.

CAP remains in local subprocess mode by default. To explicitly select the HTTP
service, configure CAP with:

```text
AEGISCHAIN_ML_MODE=remote
AEGISCHAIN_ML_URL=https://<private-evaluator-route>/internal/v1/evaluate
AEGISCHAIN_ML_TOKEN=<same-secret-injected-into-evaluator>
AEGISCHAIN_ML_TIMEOUT_MS=15000
```

Remote mode fails during CAP service initialization if the URL is missing or
invalid; it never falls back to Python subprocess execution. The same timeout
setting applies to local and remote evaluation. CAP continues to validate
shipment/inventory IDs and owns all record creation and approval state.

---

## 5. Provider status

The optional llm_proxy classifier can use the Google GenAI SDK when installed
and configured. CAP currently calls the evaluator with its deterministic
classifier default. The genai_hub classifier mode is a placeholder that raises
NotImplementedError; SAP AI Core/Generative AI Hub credentials, deployment
bindings, scopes, and runtime integration are not configured in this repository.

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

>> Upstream benchmark report: local 40-item dataset only; not production validation <<
```
## Optional LLM classification and briefing

The integrated evaluator keeps deterministic classification as its default. The
upstream classifier_mode="llm_proxy" option uses the optional Google GenAI
client and falls back to deterministic classification on provider errors. The
engine also attaches an executive briefing; it uses a deterministic template
when no LLM credentials are configured or generation fails. These additions do
not approve or execute recovery actions and do not change CAP persistence.

ml/llm_client.py reads LLM_PROVIDER, GEMINI_MODEL, and GEMINI_API_KEY. The
committed .env.example is a placeholder template; copy/configure it only in a
local .env, which Git ignores. python-dotenv is required to load that file.
Install google-genai separately only when enabling the Google provider; it is
not part of the deterministic/local evaluator dependency set. SAP Generative
AI Hub remains an unprovisioned integration seam.

Provider calls can exceed the CAP evaluator timeout. Keep the deterministic
default for the live demo unless the timeout, credentials, and external call
behavior have been deliberately configured and tested.
