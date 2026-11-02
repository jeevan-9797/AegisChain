# AegisChain CAP API

## Local connection

Start the CAP server from the repository root:

```sh
npm install
npm start
```

The OData v4 service root is `http://localhost:4004/odata/v4/aegis`. With the current local CAP configuration, the service starts against SQLite in memory and initializes the mock shipments and inventory from `db/data/`. No live SAP credentials are needed. The data is reset when the local process restarts.

Use the service document at `/odata/v4/aegis/` or metadata at `/odata/v4/aegis/$metadata` to inspect the deployed contract. Local CAP uses mocked authentication; it is for the demo only.

## Read operations

| Resource | Method | Purpose |
| --- | --- | --- |
| `/Shipments` | GET | Read mock shipment records; read-only. |
| `/InventoryItems` | GET | Read mock inventory records; read-only. |
| `/DisruptionSignals` | GET | Read disruption signals and their affected records. |
| `/Recommendations` | GET | Read recommendations, source, rationale, approval state, and decision fields. |

The service supports normal OData query options such as `$filter`, `$select`, `$orderby`, `$top`, and `$expand`. For example, use `GET /DisruptionSignals?$expand=shipmentImpacts($expand=shipment),inventoryImpacts($expand=inventoryItem),recommendations` to retrieve a signal with its impacted operations and recommendations. Each impact association can be expanded to its corresponding shipment or inventory item.

Shipment and inventory records include `dataSource: "mockS4HANA"` to identify demonstration data. Recommendation `source` is `ai` or `fallback`; this phase does not generate recommendations.

## Create a disruption signal and its impacts

`POST /DisruptionSignals` accepts a CAP deep insert. A signal must include its type, description, occurrence timestamp, severity/classification, source `demoScenario`, and at least one existing shipment or inventory impact. The service does not infer which records a signal affects; the caller supplies the links. Type and severity remain open strings.

```json
{
  "type": "portDelay",
  "description": "Demonstration port delay",
  "occurredAt": "2026-11-02T10:00:00Z",
  "severity": "high",
  "source": "demoScenario",
  "shipmentImpacts": [
    { "shipment_ID": "11111111-1111-4111-8111-111111111111" }
  ],
  "inventoryImpacts": [
    { "inventoryItem_ID": "33333333-3333-4333-8333-333333333333" }
  ]
}
```

A successful create returns `201 Created` and the signal representation, including the impact links. Missing impacts or a non-demo source returns `400 Bad Request`. Invalid referenced IDs are rejected by database referential integrity.

## Create an advisory recommendation

`POST /Recommendations` creates a recommendation linked to an existing signal. Required fields are `signal_ID`, `action`, `rationale`, and `source` (`ai` or `fallback`). `tradeoffs` is optional. New recommendations always start as `pending`; decision fields are cleared by the service. Supplying another approval status returns `400 Bad Request`.

Approval decisions are recorded on the recommendation (`approvalStatus`, `decidedBy`, `decidedAt`, and optional `decisionNote`). There is one decision per recommendation; a separate decision history resource is not provided.

## Record approval or rejection

`POST /decideRecommendation` records a decision for an existing pending recommendation:

```json
{
  "recommendationID": "<recommendation UUID>",
  "decision": "approved",
  "decisionNote": "Reviewed by the demo planner"
}
```

Set `decision` to `approved` or `rejected`. A successful call returns `200 OK` with:

```json
{
  "recommendationID": "<recommendation UUID>",
  "decision": "approved",
  "executionStatus": "notExecuted"
}
```

The caller cannot supply the decision actor or timestamp. CAP records its current request user and the current time. The action only records the approval decision; it does not execute or transmit the proposed recovery action. The same recommendation cannot be decided again: an already decided item returns `409 Conflict`. An unknown ID returns `404 Not Found`, and invalid or missing decision inputs return `400 Bad Request`.

Direct `PATCH`/`PUT` updates to `/Recommendations` are rejected with `405 Method Not Allowed`; use the decision action to change approval state. No dashboard summary endpoint is needed for the documented MVP because the frontend can query the existing resources and use OData expansion/filtering. No separate audit endpoint is needed for the single-decision MVP because the decision fields are retained on each recommendation.

## Current boundaries

- The API provides mock S/4HANA operational records only. It does not read from or write to a live SAP system.
- Recommendation creation stores caller-provided advisory content; there is no AI provider or deterministic recommendation generator in this backend phase.
- The decision actor is the CAP request user under local mocked authentication. Production identity, authorization, and approver roles are not configured.
- No BPA workflow is invoked, and `executionStatus: "notExecuted"` is not an execution tracker.
- Data in the local in-memory SQLite database is lost when the server stops.
