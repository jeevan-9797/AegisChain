# AegisChain — AI/ML Intelligence & Scoring Module

> **SAP Hackfest 2026** | Track: Autonomous Supply Chain Resiliency  
> **Package**: `ml/` (Self-Contained Autonomous Decision Engine)  
> **Status**: Gate 1 Fallback & LLM Adapter Layer Verified (`v1.1.0-adapter`)

---

## 1. Executive Summary & Gate 1 Fallback Rationale

In enterprise SAP BTP and Learning Hub sandbox environments, **SAP AI Core** service keys and subaccount provisioning can frequently be restricted, pending approval, or quota-limited. 

In accordance with our official **Gate 1 Fallback Plan**, the `ml/` module delivers a fully functional, deterministic, and modular machine learning package running directly inside **SAP Business Application Studio (BAS)** or any standard Node.js/Python container runtime:
- **Zero Cloud Credentials Required**: Operates independently of external API keys, service bindings, or cloud tokens via robust scikit-learn estimators and deterministic regex heuristics.
- **Local LLM Proxy (`gemini-2.5-flash`)**: Integrates Google AI Studio as a development-time proxy for live headline classification and CSCO decision memorandum generation.
- **Seamless Adapter Pattern**: When SAP AI Core credentials are provisioned, toggling `LLM_PROVIDER="sap_hub"` connects to enterprise foundation models via SAP Generative AI Hub without altering downstream CAP service interfaces, database tables, or SAP UI5 / Fiori components.

---

## 2. Architecture & Module Design

```
AegisChain/
├── .env.example          # Template for local environment variables (never committed)
├── .gitignore            # Git exclusion for .env, *.env, .venv, __pycache__
└── ml/
    ├── __init__.py       # Public API: SignalClassifier, AegisPredictiveCore, ExecutiveBriefingAgent, run_incident_evaluation
    ├── llm_client.py     # SwappableLLMClient (Google AI Studio gemini-2.5-flash + SAP AI Hub skeleton)
    ├── classifier.py     # SignalClassifier (modes: 'deterministic', 'llm_proxy', 'genai_hub')
    ├── models.py         # AegisPredictiveCore (GradientBoostingRegressor & GradientBoostingClassifier)
    ├── briefing_agent.py # ExecutiveBriefingAgent (Generates structured decision memo with sign_off_status)
    ├── engine.py         # Unified incident orchestration pipeline & JSON payload generator
    ├── eval_dataset.json # Ground-truth evaluation dataset (40 realistic test headlines)
    ├── benchmark.py      # Validation runner (Accuracy, Precision, Recall, Hallucination audit)
    ├── test_llm.py       # Standalone verification suite for LLM client, classifier, and briefing agent
    └── README.md         # Technical architecture & integration documentation
```

### Module Responsibilities

1. **`ml/llm_client.py` (`SwappableLLMClient`)**:
   - Adapter pattern decoupling downstream consumers from specific LLM providers.
   - Reads `LLM_PROVIDER` (default `"google"`) and `GEMINI_API_KEY` from local `.env`.
   - In `"google"` mode: calls `google-genai` SDK targeting model `gemini-2.5-flash` with strict structured JSON output (`response_mime_type="application/json"`).
   - In `"sap_hub"` mode: contains pre-built skeleton for `gen_ai_hub.proxy.native.openai` ready to be uncommented once SAP AI Core service keys are provisioned.

2. **`ml/classifier.py` (`SignalClassifier`)**:
   - Supports modes: `"deterministic"` (default), `"llm_proxy"`, and `"genai_hub"`.
   - In `"llm_proxy"` mode: uses `SwappableLLMClient` to parse raw feeds into standardized categories (`CHOKEPOINT`, `PORT`, `TARIFF`, `WEATHER`, `OTHER`), severities (1–3), and impacted lanes.
   - **Automatic Resilience**: If API keys are missing, network times out, or quota is exhausted, it seamlessly falls back to the deterministic regex engine (`is_fallback=True`).

3. **`ml/models.py` (`AegisPredictiveCore`)**:
   - **Lane Delay Model (`GradientBoostingRegressor`)**: Predicts net transit delay days based on `[base_days, security_risk (0-1), congestion_index (1-5), season (1-4)]`.
   - **Spoilage Risk Model (`GradientBoostingClassifier`)**: Predicts pharmaceutical viability loss probability based on `[days_over_viability, reefer_health (0-1), transshipments, mode_mix (1=sea, 2=air, 3=split)]`.
   - Evaluates rerouting options matching presentation Case **#SAP-8842** (40,000 insulin doses, \$450,000 value, 9-day thermal window).

4. **`ml/briefing_agent.py` (`ExecutiveBriefingAgent`)**:
   - Authors grounded, human-in-the-loop executive decision memoranda for CSCOs and logistics directors.
   - Returns structured JSON containing:
     * `executive_summary`: Operational synthesis of the crisis and cargo vulnerability.
     * `recommended_action`: Logistical justification for Option C (Sea-Air Hybrid via Jebel Ali).
     * `risk_mitigation`: Telemetry SOPs (2°C–8°C), customs green lanes, and tarmac reefer handoffs.
     * `financial_impact`: Cargo value saved (\$376,585 vs Cape) and freight comparisons.
     * `sign_off_status`: Always set to `"AWAITING_HUMAN_APPROVAL"`.
   - Built-in deterministic templated fallback ensures zero crashes in offline/sandbox runtimes.

5. **`ml/engine.py` (`run_incident_evaluation`)**:
   - Orchestration entry point: ingests feeds, classifies signals, scores predictive scenarios, selects the mathematically optimal route, and generates the executive briefing.
   - Emits structured JSON matching SAP CAP and SAP UI5 Control Tower contracts.

---

## 3. Case Study #SAP-8842: Mathematical Proof

### Scenario Context
- **Consignment**: 40,000 Insulin Glargine doses (\$450,000 invoice replacement value)
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

## 4. SAP CAP / Node.js Integration Pattern

The SAP CAP backend executes evaluations via a clean Node.js child process wrapper or local microservice endpoint.

### Node.js / CAP Service Implementation (`srv/incident-service.js`)

```javascript
const { spawn } = require('child_process');
const path = require('path');

/**
 * Invokes the local AegisChain predictive ML engine.
 * @param {Array<Object>} feedItems - Unstructured news or IoT alerts
 * @param {number} cargoValueUsd - Consignment invoice value (default: 450000)
 * @returns {Promise<Object>} Formatted evaluation payload
 */
function evaluateIncidentML(feedItems, cargoValueUsd = 450000.0) {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const scriptPath = path.resolve(__dirname, '../ml/engine.py');

    const pyProcess = spawn(pythonPath, [scriptPath, '-']);
    let stdoutData = '';
    let stderrData = '';

    pyProcess.stdout.on('data', (chunk) => { stdoutData += chunk; });
    pyProcess.stderr.on('data', (chunk) => { stderrData += chunk; });

    pyProcess.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`ML Engine failed (code ${code}): ${stderrData}`));
      }
      try {
        const payload = JSON.parse(stdoutData);
        resolve(payload);
      } catch (err) {
        reject(new Error(`Failed to parse ML JSON payload: ${err.message}`));
      }
    });

    // Stream input feed items as JSON via stdin
    pyProcess.stdin.write(JSON.stringify(feedItems));
    pyProcess.stdin.end();
  });
}

module.exports = { evaluateIncidentML };
```

---

## 5. Transitioning to SAP Generative AI Hub

The module is architected with complete interface symmetry:

1. In your SAP BTP Subaccount, provision an instance of the `aicore` service.
2. Bind the instance or generate a service key in Business Application Studio (`.env`):
   ```bash
   LLM_PROVIDER="sap_hub"
   BTP_AICORE_CLIENT_ID="<clientid>"
   BTP_AICORE_CLIENT_SECRET="<clientsecret>"
   BTP_AICORE_AUTH_URL="<url>"
   BTP_AICORE_BASE_URL="<serviceurls.AI_API_URL>"
   BTP_AICORE_RESOURCE_GROUP="default"
   AI_HUB_MODEL_DEPLOYMENT_ID="<deployment_id>"
   ```
3. Install the SAP GenAI client:
   ```bash
   pip install generative-ai-hub
   ```
4. Uncomment `_call_sap_genai_hub` in `ml/llm_client.py`.
   *No changes to downstream CAP handlers or UI bindings are required.*

---

## 6. Benchmarks & Verification Commands

### Benchmark Suite (Gate 1 Validation)
```bash
python ml/benchmark.py
```
- **Accuracy**: 100.0% (Target: >= 90.0%)
- **Hallucinated Lanes**: 0.0%
- **Throughput**: > 6,000 items/second

### LLM Adapter & Executive Briefing Test Suite
```bash
python ml/test_llm.py
```
- Tests `SwappableLLMClient` JSON parsing and provider resolution.
- Tests `SignalClassifier` in `llm_proxy` mode with live or graceful fallback.
- Tests `ExecutiveBriefingAgent` generation and Case #SAP-8842 data grounding.
- Confirms end-to-end orchestration payload has `"executive_briefing"` attached.
