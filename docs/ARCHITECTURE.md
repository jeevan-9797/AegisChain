# AegisChain Intended Architecture

## Architecture goals

The hackathon MVP uses SAP technologies as its application foundation, keeps operational data and business rules in a CAP service, and makes AI recommendations and human decisions visible as separate steps. External enterprise systems are represented by a mock integration until a real interface is explicitly designed and authorized.

## Logical components

```text
SAP Fiori / UI5 frontend
        | OData or CAP-supported API
        v
SAP CAP Node.js backend
   |         |          |
   |         |          +--> SAP Build Process Automation
   |         |                approval request and decision status
   |         +-------------> SAP AI Launchpad / Generative AI Hub
   |                          disruption classification and recommendations
   +-----------------------> SQLite (local) / SAP HANA Cloud (production)
   |
   +-----------------------> Mock S/4HANA adapter (initial demo)
```

The diagram shows intended logical integrations. It does not imply that credentials, destinations, deployed instances, or working connectors are already present in this scaffold.

## Component responsibilities

### SAP Fiori / UI5 frontend

- Provide the control-tower view for shipments, inventory, disruption signals, recommendations, and approval status.
- Allow a demonstrator to trigger the bounded demo scenarios.
- Make data provenance, recommendation origin, and workflow state visible.
- Request and display business data through the CAP service API; it should not connect directly to the database or AI provider.

### SAP CAP Node.js backend

- Own the AegisChain domain model, service API, and business validations.
- Coordinate scenario ingestion, impact assessment, recommendation requests, and approval state.
- Enforce that consequential actions require explicit approval and distinguish approval from execution.
- Encapsulate integrations behind service/adaptor boundaries so the mock S/4HANA implementation can later be replaced deliberately.
- Keep provider errors and unavailable states explicit to the UI.

### Persistence: SQLite and SAP HANA Cloud

- **Local development:** SQLite supports a low-friction local CAP workflow and demo data.
- **Production target:** SAP HANA Cloud is the intended production database for persistent business data.
- The CAP model should remain database-portable where practical; HANA-specific behavior should be isolated and documented.
- No production persistence, migration, backup, or retention configuration exists yet.

### SAP AI Launchpad / Generative AI Hub

- Intended provider path for AI-assisted signal classification and recovery recommendations.
- The CAP backend should send only the scenario and relevant context needed for a recommendation and validate/shape the response before returning it.
- Recommendation output should include rationale and source metadata. It remains advisory and subject to human review.
- A deterministic fallback is required for reliable demos when the AI service is unavailable; the application must label the fallback.
- Model choice, prompt design, grounding, credentials, deployment, quotas, and safety evaluation are implementation decisions that remain open.

### SAP Build Process Automation

- Intended to route a consequential recovery recommendation to a human approver and return the decision/status to CAP.
- The approval outcome is recorded in the AegisChain experience and must not be confused with action execution.
- The initial demo may use a controlled local/mock workflow if a BPA tenant or integration is not available, provided the mock is clearly identified. A live BPA integration is not assumed by this documentation.

### Mock S/4HANA integration

- Supplies a fixed, representative set of shipment and inventory records for the initial demonstration.
- Supports the planned scenario-to-record mapping needed to show disruption impact.
- Is read-only from the perspective of the demo. No live SAP S/4HANA connection or write-back is included in the MVP.
- A future real integration requires a separately specified API, authentication, authorization, error handling, and data ownership design.

## Primary request flow

1. The UI requests the current demo operations data from CAP.
2. A user triggers a demo disruption; CAP records the signal and resolves its affected demo records through the scenario/mock adapter.
3. CAP requests AI analysis where configured, validates the result, and falls back to a deterministic recommendation if the provider is unavailable.
4. CAP exposes the signal, impact, and recommendation with provenance to the UI.
5. The user submits an approval decision. CAP coordinates with BPA when integrated, or with a clearly labeled demo workflow, then presents the returned decision state.
6. No external recovery action is executed as part of approval in the MVP.

## Initial deployment boundary

The first working demonstration should be runnable locally using CAP and SQLite, with deterministic mock operational data. SAP AI Launchpad/Generative AI Hub and SAP Build Process Automation are target integrations and may require separately provisioned SAP services. SAP HANA Cloud is the production database target, not a prerequisite for the local demo. Integration availability and mock fallbacks must be visible to the user.

## Decisions still to make during implementation

- Exact CAP entities and API shapes for shipments, inventory, disruptions, recommendations, and decisions.
- UI5 app template, navigation, and authentication approach suitable for the demo.
- The bounded scenario list and deterministic impact/recommendation rules.
- Whether to connect to provisioned AI/BPA services during the hackathon or demonstrate their flows with labeled local adapters.
- Deployment target, environment configuration, and production security controls.
