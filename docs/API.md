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

`POST /DisruptionSignals` accepts a CAP deep insert. A manually entered signal uses source `demoScenario`; it must include its type, description, occurrence timestamp, severity/classification, and at least one existing shipment or inventory impact. The service does not infer which records a signal affects; the caller supplies the links. Type and severity remain open strings.

The required signal fields must be nonblank. Every impact link must contain an explicit `shipment_ID` or `inventoryItem_ID` that exists in the corresponding CAP entity; duplicate links within either impact collection are rejected. Missing, duplicate, or unknown impact IDs return `400 Bad Request`.

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

Required recommendation fields must be nonblank, and `signal_ID` must identify an existing signal. If the signal is created but recommendation creation fails, the signal remains persisted; clients should report its ID and must not silently retry the whole creation flow.

Every created recommendation stores `executionStatus: "notExecuted"`. Other execution states are rejected; approval and rejection only update the decision fields.

## Evaluate a disruption feed and persist one advisory recommendation

The OData action POST /evaluateIncident runs the Python evaluator through the configured local subprocess or authenticated remote HTTP adapter, maps its result, then writes one signal, its explicit impact links, and one linked pending recommendation in a single CAP deep insert. CAP classification remains deterministic; the evaluator may attach an optional LLM-generated briefing when credentials are configured.

Example request:

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
  "incident_id": "SAP-8842",
  "shipmentIDs": ["<existing shipment UUID>"],
  "inventoryItemIDs": []
}
```

Successful response (`200 OK`):

```json
{
  "signalID": "<created signal UUID>",
  "recommendationID": "<created recommendation UUID>",
  "category": "Chokepoint",
  "severity": "critical",
  "scenarioKey": "OPTION_C_SPLIT",
  "approvalStatus": "pending",
  "executionStatus": "notExecuted"
}
```

Mapping rules: `CHOKEPOINT`, `PORT`, `TARIFF`, and `WEATHER` become the UI categories `Chokepoint`, `Port`, `Tariff`, and `Weather`. Evaluator severities 3/2/1 become CAP/UI `critical`/`medium`/`low`; only active signals at severity 2 or 3 can produce a recommendation. The signal source is `mlEvaluation`. The recommendation source is `fallback`, because the integrated evaluator runs its deterministic Gate 1 implementation. Its action names the evaluator's selected scenario; rationale and tradeoffs retain evaluator output.

An empty feed is rejected with `400`. `OTHER` or otherwise unsupported-only classifications, multiple active classifications in one request, and feeds with no active moderate-or-higher disruption are rejected with `422`; none creates CAP records. Invalid impact IDs return `400`. In local mode, missing Python returns `503`, evaluator timeout returns `504`, and process/schema failures return `502`. CAP uses local subprocess mode by default (`AEGISCHAIN_ML_MODE=local`); set `AEGISCHAIN_PYTHON` to the Python executable and optionally `AEGISCHAIN_ML_TIMEOUT_MS` to the timeout in milliseconds. To explicitly select the HTTP prototype, configure `AEGISCHAIN_ML_MODE=remote`, `AEGISCHAIN_ML_URL` to the evaluator's full `/internal/v1/evaluate` endpoint, and `AEGISCHAIN_ML_TOKEN` to the injected shared bearer secret. Missing or weak remote credentials fail CAP initialization; CAP never falls back to subprocess mode. Remote errors map connection failures to `503`, timeouts to `504`, invalid evaluator requests (`400`/`422`) to CAP `400`, authentication rejection (`401`/`403`) to `502`, and other upstream or response failures to `502`. Install the pinned Python runtime dependencies from `requirements.txt` before using either mode.

The Python evaluator requires the same secret in `AEGISCHAIN_EVALUATOR_TOKEN`; secrets must be at least 32 UTF-8 bytes and must be injected outside source control. `GET /healthz` and `GET /readyz` are public and return only generic status for platform probes; `POST /internal/v1/evaluate` requires `Authorization: Bearer <token>`. CAP requires HTTPS for non-loopback evaluator URLs to protect the bearer credential in transit. Remote mode requires Node.js 18 or newer for the built-in Fetch API. Python accepts only the versioned evaluator envelope and does not receive CAP shipment or inventory IDs.

This first integration persists one supported active classification per request. Submit separate calls for separate active incidents. The evaluator's scenario model is the documented SAP-8842 demonstration model; its economics are not shipment-specific merely because caller-supplied impact IDs are attached. Evaluation, creation, approval, and rejection never execute recovery actions or write to external SAP systems. The existing frontend manual live creation flow and mock mode are unchanged.

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
- Manual recommendation creation stores caller-provided advisory content. The evaluateIncident action creates its advisory recommendation from the evaluator scenario. The upstream LLM additions can classify or generate a briefing only when explicitly selected/configured; the CAP action currently uses deterministic classification. Neither path executes actions.
- The decision actor is the CAP request user under local mocked authentication. Production identity, authorization, and approver roles are not configured.
- No BPA workflow is invoked, and `executionStatus: "notExecuted"` is not an execution tracker.
- Data in the local in-memory SQLite database is lost when the server stops.
