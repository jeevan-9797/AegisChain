# AegisChain Product Requirements

## Problem statement

Enterprise supply-chain teams need to understand how disruptions affect shipments and inventory, then coordinate recovery quickly. Relevant signals are often spread across operational systems and updates, making it difficult to assess impact, compare recovery options, and keep consequential actions under human control.

AegisChain is an SAP-based, AI-assisted resilience application. Its hackathon MVP will present a small, coherent supply-chain scenario in which a user can trigger or observe a disruption, review its impact and recommended recovery actions, and approve or reject a proposed action.

## Target users and actors

- **Supply-chain control tower analyst:** monitors shipments and inventory, evaluates disruption impact, and reviews recommended responses.
- **Supply-chain planner / recovery approver:** assesses operational tradeoffs and approves or rejects consequential recovery actions.
- **Demonstrator / judge:** triggers a prepared disruption scenario and observes signal classification, recommendations, and approval status.
- **AegisChain application:** ingests scenario data and signals, classifies disruption, presents recommendations, and tracks decisions. It does not independently execute consequential actions.
- **Mock S/4HANA system:** supplies representative shipment and inventory data for the initial demonstration; it is not a live enterprise integration.

## Core user workflows

### Monitor operations

1. The user opens the control-tower view.
2. The application shows the prepared shipments and inventory scenario with their current status and relevant disruption alerts.
3. The user selects a shipment, inventory item, or alert to inspect its operational context.

### Trigger and assess a disruption

1. The demonstrator selects a supported demo event (for example, a port delay or supplier interruption).
2. The application records the event and identifies affected shipments and/or inventory in the demo dataset.
3. The application classifies the signal and displays its severity, affected records, and the basis for the assessment.

### Review and approve recovery

1. The application presents one or more recovery recommendations with a concise rationale and known tradeoffs.
2. A planner reviews the affected operations and recommendation.
3. The planner approves or rejects the consequential action through the configured approval workflow.
4. The application displays the decision and workflow status. Approval records intent; execution against an external system is outside the MVP.

## MVP features

- A focused control-tower experience for a prepared, bounded demonstration dataset.
- Shipment and inventory status views backed by mock S/4HANA data.
- A small set of triggerable disruption scenarios and visible signal classification.
- Impact identification linking a disruption to affected shipment and/or inventory records.
- AI-assisted recovery recommendations with a human-readable rationale; the demonstration must remain usable if AI is unavailable by providing a clearly identified deterministic fallback.
- Human approval or rejection of consequential recommendations, with a visible status and decision record.
- Clear indication of demo/mock data and AI-generated or fallback recommendations.

## Explicitly out of scope

- Production S/4HANA connectivity, synchronization, or write-back.
- Autonomous execution of rerouting, purchasing, inventory transfer, or other consequential actions.
- Comprehensive real-time event ingestion from carriers, ports, suppliers, IoT devices, or public feeds.
- Production-grade optimization across a large network, guaranteed cost/ETA outcomes, or autonomous planning.
- Multi-tenant SaaS, broad role/identity lifecycle management, and enterprise-wide authorization design.
- Mobile-native clients, a generalized workflow designer, or a full supply-chain planning suite.
- Claims that AI recommendations are guaranteed, complete, or suitable without human review.

## Functional requirements

- **FR-1 Operations view:** The application shall show the demo shipments and inventory records, including identifiers, current status, and relevant location or quantity fields.
- **FR-2 Scenario trigger:** An authorized demo user shall be able to trigger each disruption scenario included in the MVP.
- **FR-3 Signal record:** For each triggered scenario, the application shall retain enough information to show its type, time, severity/classification, and source (demo scenario).
- **FR-4 Impact assessment:** The application shall identify and display the shipment and/or inventory records affected by a triggered scenario.
- **FR-5 Recommendations:** The application shall present at least one recovery recommendation for each supported scenario, with rationale and any known tradeoffs represented by the demo.
- **FR-6 Approval gate:** A consequential recommendation shall have a pending, approved, or rejected status and shall not be represented as executed merely because it was approved.
- **FR-7 Decision visibility:** The application shall show the approver decision and status to the user reviewing the recommendation.
- **FR-8 Resilient demo:** If the AI capability is unavailable, the application shall indicate that it is using a deterministic fallback recommendation.
- **FR-9 Data labeling:** Mock operational data and AI-generated versus fallback content shall be distinguishable in the user experience.

## Non-functional requirements

- **NFR-1 Demonstrability:** A judge shall be able to complete the primary trigger-to-recommendation-to-decision flow in a short live demonstration without connecting to a production enterprise system.
- **NFR-2 Explainability:** Each recommendation shall include a concise reason and identify its affected records; unsupported certainty or fabricated live data must not be implied.
- **NFR-3 Human control:** The system shall require an explicit human decision for consequential recovery actions and shall preserve the decision outcome for the demo session.
- **NFR-4 Failure clarity:** Failures in AI or approval-workflow integration shall be surfaced as unavailable or failed states, not silently presented as successful results.
- **NFR-5 Maintainability:** The initial implementation shall use SAP CAP Node.js conventions, keep domain/service responsibilities clear, and support SQLite local development and SAP HANA Cloud as the production database target.
- **NFR-6 Security baseline:** Secrets and credentials shall not be committed to the repository. Production identity, authorization, and data protection requirements must be defined before production use.

## MVP acceptance criteria

The MVP is acceptable when all of the following can be demonstrated against the prepared dataset:

1. A user can open the application and identify that its operational records are demo data.
2. Shipment and inventory records are visible with enough status/context to inspect a disruption's impact.
3. A user can trigger each documented MVP disruption scenario and see a recorded, classified signal.
4. For each scenario, the application identifies the expected affected records in the prepared dataset and displays them with the signal.
5. The user sees at least one relevant recovery recommendation, its rationale, and whether it came from AI or fallback logic.
6. A recommendation starts in a pending state; a planner can approve or reject it, and the resulting decision/status is visible.
7. Approval does not falsely imply that an action was carried out in S/4HANA or another external system.
8. If AI or approval integration is unavailable, the application shows a clear failure/unavailable state and the demo remains understandable; the deterministic recommendation path is explicitly labeled.
9. Local setup and run instructions allow a developer to launch the implemented demo using the documented SQLite/local workflow without production SAP credentials.

The exact scenario names, fields, and expected affected records should be fixed in the implementation's demo data and verified by automated tests when those features are built.
