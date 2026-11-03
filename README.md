# AegisChain: Intelligent Resilient Supply Chain Control Tower

[![SAP CAP](https://img.shields.io/badge/SAP-CAP%20%28Node.js%29-blue.svg)](https://cap.cloud.sap/)
[![SAPUI5](https://img.shields.io/badge/SAPUI5-Fiori-orange.svg)](https://ui5.sap.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)](LICENSE)

**AegisChain** is an enterprise-grade, prescriptive supply chain risk intelligence platform. Built for SAP environments, it bridges the gap between raw external disruption signals (geopolitical events, extreme weather, port strikes) and real-time operational execution inside SAP ERP systems.

Unlike standard visibility dashboards that merely report status indicators (Red/Yellow/Green), AegisChain provides **closed-loop autonomous triage**: identifying impacted Purchase Orders and Shipments, assessing cost-to-serve trade-offs, and generating actionable mitigation proposals ready for human sign-off.

---

## Architecture Overview

AegisChain couples the rigor of the **SAP Cloud Application Programming (CAP)** model with a specialized **Python ML/LLM intelligence pipeline** and an **SAPUI5 Analytical Control Tower**.

```
  +-------------------------------------------------------------------------+
  |                        External Signals Stream                          |
  |             (News feeds, port congestion, weather telemetry)            |
  +------------------------------------+------------------------------------+
                                       |
                                       v
  +-------------------------------------------------------------------------+
  |                       Python Intelligence Engine (/ml)                  |
  |  - classifier.py       : Lightweight triage & severity scoring          |
  |  - briefing_agent.py   : Synthesizes risk reports & mitigation strategy |
  |  - llm_client.py       : Structured schema enforcement (Pydantic/JSON)  |
  +------------------------------------+------------------------------------+
                                       | OData v4 / REST Actions
                                       v
  +-------------------------------------------------------------------------+
  |                     SAP CAP Backend Engine (/srv, /db)                  |
  |  - schema.cds          : Relational models (PO, Shipments, Nodes, Risks)|
  |  - service.cds         : OData v4 endpoints, triage actions, draft logic|
  +------------------------------------+------------------------------------+
                                       | OData Model Bindings
                                       v
  +-------------------------------------------------------------------------+
  |                  SAPUI5 Analytical Control Tower (/app)                 |
  |  - ControlTower.view   : High-density operations cockpit & triage cards |
  |  - ControlTower.ctrl   : Human-in-the-loop review, approval & execution |
  +-------------------------------------------------------------------------+
```

---

## Key Features

1. **Autonomous Disruption Triage & Linking**
   * Correlates unstructured textual alerts to exact master and transactional entities (Purchase Orders, Shipments, Carriers, and Vendors).
2. **Schema-Grounded LLM Reasoning**
   * Enforces zero-hallucination policies using strict JSON schema boundaries. AI recommendations strictly reference approved vendors, alternative carrier lanes, and valid warehouse nodes in the CDS model.
3. **Prescriptive Action Generation**
   * Generates concrete mitigation packages: rebooking expedited freight, initiating stock transfer orders, or drafting supplier communications.
4. **Human-in-the-Loop (HITL) Governance**
   * High-value or high-cost recommendations require explicit operational approval from the SAPUI5 Control Tower before triggering SAP ERP updates.
5. **Integrated Benchmark & Evaluation Suite**
   * Built-in benchmarking utilities (`ml/benchmark.py`) against standard test datasets (`eval_dataset.json`) to validate classification accuracy, latency, and schema compliance.

---

## Directory Structure

```text
AegisChain-research/
├── app/
│   └── controltower/           # SAPUI5 / SAP Fiori analytical application
│       ├── webapp/
│       │   ├── controller/     # View controllers (ControlTower.controller.js)
│       │   ├── view/           # XML views and cards
│       │   ├── model/          # UI state, mock data, and bindings
│       │   └── manifest.json   # SAPUI5 app descriptor & data sources
│       └── ui5.yaml            # UI5 build & tooling configuration
├── db/
│   ├── schema.cds              # Core data entities (PO, Suppliers, Events, Risks)
│   └── data/                   # Initial CSV / JSON seed records
├── srv/
│   ├── service.cds             # OData v4 service definitions & custom actions
│   └── service.js              # Business logic handlers and event listeners
├── ml/
│   ├── classifier.py           # Severity & category disruption classification
│   ├── briefing_agent.py       # Context-aware executive mitigation synthesis
│   ├── llm_client.py           # Unified client wrapper with structured output validation
│   ├── models.py               # Pydantic schemas and typed data definitions
│   ├── benchmark.py            # Latency, accuracy, and compliance evaluation runner
│   └── eval_dataset.json       # Ground-truth test scenarios
├── package.json                # Node.js dependencies & CAP scripts
└── README.md                   # Project documentation
```

---

## Getting Started

### Prerequisites
* **Node.js**: v18.x or v20.x LTS
* **Python**: v3.10 or higher
* **SAP CDS Development Kit**: `@sap/cds-dk` installed globally (`npm i -g @sap/cds-dk`)
* **API Credentials**: OpenAI, Anthropic, or an SAP AI Core deployment key

### 1. Backend & SAP CAP Setup

1. Install Node.js dependencies from the repository root:
   ```bash
   npm install
   ```

2. Start the CAP mock server (SQLite in-memory):
   ```bash
   cds watch
   ```
   The OData service will be available at `http://localhost:4004`.

### 2. Frontend Control Tower Setup

1. Navigate to the UI5 application directory:
   ```bash
   cd app/controltower
   npm install
   ```

2. Start the local UI5 development server:
   ```bash
   npm run start
   ```
   Open `http://localhost:8080/index.html` to access the Control Tower interface.

### 3. Machine Learning & Agent Pipeline Setup

1. Navigate to the `ml` folder:
   ```bash
   cd ml
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp ../.env.example .env
   # Add your LLM API keys and backend service endpoints to .env
   ```

5. Run the evaluation benchmark to test LLM readiness:
   ```bash
   python benchmark.py
   ```

---

## Running Scenarios & End-to-End Flow

1. **Ingest Signal**: Run a simulated external event via `python ml/engine.py --simulate`.
2. **Triage & Classification**: `classifier.py` parses the alert, scores risk severity, and tags impacted transportation corridors.
3. **Enrichment**: The ML agent queries the CAP OData service for active Purchase Orders touching the corridor.
4. **Prescriptive Synthesis**: `briefing_agent.py` evaluates rerouting costs vs. delay penalties, generating a mitigation draft.
5. **Operational Review**: Open the SAPUI5 Control Tower, review the synthesized impact card, and approve the recommended mitigation action.

---

## Hackathon Pitch Highlights

* **Enterprise Integration First**: Designed natively around SAP CAP, CDS definitions, and Fiori design principles.
* **Deterministic AI Guardrails**: Strict schema adherence guarantees that generative recommendations never violate enterprise master data rules.
* **Quantifiable ROI**: Directly targets reduction in **Decision Latency** and minimizes **Cost-to-Serve** leakage during major supply chain exceptions.