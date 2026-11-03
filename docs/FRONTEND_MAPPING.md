# Frontend ↔ CAP field mapping (AegisService, `/odata/v4/aegis`)

Status: **proposal for review**. The frontend adapter (`app/controltower/webapp/model/BackendAdapter.js`) already implements every ✅ and 🔄 row against the current backend (`b8185a8`) and was tested end to end against a local `npm start` (read, `decideRecommendation`, 409 handling, backend-down fallback). Nothing below requires an API change unless marked 🟡.

| Legend | Meaning |
| --- | --- |
| ✅ Direct | Field exists in the CAP model and is shown as-is |
| 🔄 Derived | Frontend computes it from existing CAP fields; no backend change |
| 🟡 Needs backend | No equivalent yet; proposed MVP representation below. Shown as `-` in live mode |
| ⚪ Mock-only | Agreed to stay on `mock.json` for now |

## 1. Incident (Overview list + Incidents tab), one per `DisruptionSignals` row

Read with `GET /DisruptionSignals?$expand=shipmentImpacts($expand=shipment),inventoryImpacts($expand=inventoryItem),recommendations&$orderby=occurredAt desc`

| UI field | CAP source | Status | Notes |
| --- | --- | --- | --- |
| `title` | `DisruptionSignals.description` | ✅ | |
| `severity` (label) / `severityState` | `DisruptionSignals.severity` | 🔄 | `critical`→Error, `high`→Warning, `medium`→Information, `low`→None; unknown strings shown uppercase. Needs agreed enum values |
| `id` (display number, e.g. `#SAP-8842`) | `DisruptionSignals.ID` | 🔄 | First 8 chars of the UUID. A human-readable number would need a field 🟡 |
| `destination` | `shipmentImpacts.shipment.destination` | ✅ | Comma-joined if several shipments |
| `delta` (affected shipments line) | `shipmentImpacts.shipment.{shipmentNumber,status,currentLocation}` | ✅ | |
| `cargo` | `inventoryImpacts.inventoryItem.{description,quantity,unitOfMeasure}` | 🔄 | Shipments have no cargo field; the inventory impact is used instead |
| `value` (USD) | n/a | 🟡 | Proposal: `Shipments.valueAmount : Decimal(15,2)` + `valueCurrency : String(3)` |
| `viability` (days) | n/a | 🟡 | Proposal: `Shipments.viabilityDays : Integer` (min of packaging hold time and remaining shelf life) |
| `status` / `statusState` | `recommendations.approvalStatus` | 🔄 | No recs → "No recommendation yet"; any `pending` → "Awaiting approval"; otherwise approved/rejected → "decision recorded, not executed" |
| `stages` (SENSE…REBALANCE) | signal + `recommendations.approvalStatus` | 🔄 | SENSE = signal exists; SIMULATE = recs exist; VERIFY = pending/decided; **REROUTE/REBALANCE never complete** (`executionStatus: notExecuted`) |
| `urgency` banner | n/a | 🔄 | Live mode shows a fixed note that cost/delay/spoilage/gates are not in the backend yet |

## 2. Options table: one row per `Recommendations` row of the signal

| UI field | CAP source | Status | Notes |
| --- | --- | --- | --- |
| `recId` | `Recommendations.ID` | ✅ | Passed to `decideRecommendation` |
| `name` | `Recommendations.action` | ✅ | |
| `route` | `Recommendations.tradeoffs` | ✅ | Shown in the route column until a route field exists |
| approval column | `approvalStatus`, `decidedBy` | ✅ | |
| `source` | `Recommendations.source` (`ai`/`fallback`) | ✅ | Shown as the actor in the audit trail |
| default selection | first `pending` recommendation | 🔄 | There is no "recommended" flag; see 🟡 below |
| `delay` | n/a | 🟡 | `delayDays : Decimal(5,1)` |
| `extraCost` | n/a | 🟡 | `extraCostAmount : Decimal(15,2)` (+ currency) |
| `spoilage` (band) | n/a | 🟡 | `spoilageRiskMin : Decimal(5,2)`, `spoilageRiskMax : Decimal(5,2)` (0–1) |
| `expectedLoss` + bar | n/a | 🟡 | `expectedLossAmount : Decimal(15,2)`; bar is derived from it |
| `gate` / `gateState` | n/a | 🟡 | `gateResult : String enum { pass; needsApproval; blocked }` + `gateReason : String(200)` |
| recommended flag | n/a | 🟡 | `isRecommended : Boolean` (or `rank : Integer`) |

**MVP proposal for options:** add the 8 fields above to `Recommendations` (all optional, so current creates keep working). If they are null, the UI keeps showing `-`.

## 3. Decision brief

| UI field | CAP source | Status |
| --- | --- | --- |
| `brief.headline` | `Recommendations.action` (selected/first pending) | ✅ |
| `brief.why` | `Recommendations.rationale` | ✅ |
| `brief.mustCheck` | `Recommendations.tradeoffs` | ✅ |
| `brief.consigneeMessage` | n/a | 🟡 optional `partnerMessage : String(500)` |

The label "AI-written" is shown only in mock mode; live mode says "Rationale as stored on the recommendation".

## 4. Signals tab, one row per `DisruptionSignals` row

| UI field | CAP source | Status | Notes |
| --- | --- | --- | --- |
| `time` | `occurredAt` | ✅ | |
| `source` | `source` | ✅ | Always `demoScenario` today |
| `headline` | `description` | ✅ | |
| `category` | `type` | ✅ | Category filter buttons expect Chokepoint/Port/Weather/Tariff; needs agreed `type` values |
| `severity` (1–3) | `severity` | 🔄 | critical→3, high→2, else 1 |
| `status` | has recommendations? | 🔄 | "Incident created" / "Watching" |
| `lanes` | n/a | 🟡 | `affectedLanes : String(200)` (comma list) |
| `confidence` + analyst queue | n/a | 🟡 | `confidence : Decimal(3,2)`. Live mode shows 100% (planner-entered demo signals), so the analyst queue is empty |
| source URL | n/a | 🟡 optional `sourceUrl : String(500)` (needed once live RSS/API feeds exist) |

## 5. Decisions

| UI action | CAP call | Status |
| --- | --- | --- |
| Approve | `POST /decideRecommendation` `{ recommendationID, decision: "approved", decisionNote }` | ✅ |
| Reject | same with `decision: "rejected"`, `decisionNote: null` | ✅ |
| Result message | response `executionStatus` (`notExecuted`), shown verbatim: "the recovery action has NOT been executed" | ✅ |
| 409 already decided | message + refresh | ✅ |
| approver / comment | not sent; CAP records request user and time | ✅ as agreed |

## 6. Audit tab

| UI field | CAP source | Status | Notes |
| --- | --- | --- | --- |
| Decision trail rows | `DisruptionSignals.createdAt/createdBy`, `Recommendations.createdAt/source`, `decidedAt/decidedBy/decisionNote` | 🔄 | Built client-side, sorted by time |
| `hash` | n/a | ⚪ | Shown as `-` in live mode; header says "hash chain not in backend yet" |
| Actions executed | n/a | 🔄 | Always empty in live mode ("Nothing executed - executionStatus: notExecuted") |
| Audit report | derived trail | 🔄 | Report header says the source is live CAP and that nothing was executed |

## 7. KPIs, notifications, policies, map, what-if

| UI element | Status | Live-mode value |
| --- | --- | --- |
| Open incidents | 🔄 | signals with ≥1 pending recommendation |
| Consignments at risk | 🔄 | distinct impacted shipments |
| Auto-executed decisions | 🔄 | `0` (all decisions are human), note shows decided count |
| Expected loss avoided | ⚪ | `0` until expected-loss fields exist |
| LLM calls today | ⚪ | `0` (no AI provider in this backend phase) |
| Notifications (bell) | 🔄 | one per incident awaiting approval |
| Policies & guardrails | ⚪ | mock values (read-only); later `Policies` entity (key/value) 🟡 |
| Map: nodes, lanes, positions | ⚪ | static demo geography. Shipments have no coordinates; proposal `Shipments.latitude/longitude` 🟡 |
| What-if | ⚪ | client-side simulation only |

## 8. Questions for the backend

1. Agreed **enum values** for `DisruptionSignals.type` and `severity`? Proposal: type ∈ {chokepointClosure, portDelay, weather, tariffChange, supplierOutage, reeferFailure}; severity ∈ {critical, high, medium, low}.
2. Add the optional **option metrics** to `Recommendations` (section 2) as the MVP, or keep them in `tradeoffs` text for the demo?
3. **#SAP-8842 seed**: once 1–2 are agreed, a CSV seed (signal + 4 recommendations + shipment with value/viability) lets live mode tell the same story as the mock.
4. Behind an approuter, CSRF tokens will be required. The adapter already sends `X-CSRF-Token: Fetch`; nothing needed in CAP.
