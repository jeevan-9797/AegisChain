# AegisChain - Operator Control Tower (frontend)

SAPUI5 freestyle app (BAS, UI5 1.154, Horizon theme). Lives in `app/controltower` of the CAP project.

## Data modes
| Mode | Source | When to use |
| --- | --- | --- |
| `mock` (default) | `webapp/model/mock.json` | Demo story (#SAP-8842), works without the backend |
| `live` | CAP service `/odata/v4/aegis` via `webapp/model/BackendAdapter.js` | Integration with the backend |

Switch with the URL parameter `?mode=live` / `?mode=mock`, or in the gear dialog ("Data source").
If the backend is unreachable, live mode falls back to mock and says so.

Field mapping and gaps: `docs/FRONTEND_MAPPING.md` (repository root).

## Run with the backend (BAS)
1. Terminal 1, repository root: `npm install` then `npm start`  (CAP on http://localhost:4004)
2. Terminal 2: `cd app/controltower`, `npm install`, `npm start`
   `ui5.yaml` proxies `/odata` to `http://localhost:4004`.
3. Open the preview and add `?mode=live` to the URL (before the `#`), or use the gear dialog.

## Decisions
Approve / Reject call `POST /odata/v4/aegis/decideRecommendation` with
`{ recommendationID, decision, decisionNote }` and show the returned `executionStatus` (`notExecuted`).
No approver or comment fields are sent; CAP records the request user and time.
In mock mode the same buttons play the simulated demo story.
