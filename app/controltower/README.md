# AegisChain - Operator Control Tower (frontend)

SAPUI5 freestyle app (BAS, UI5 1.154, Horizon theme). Lives in `app/controltower` of the CAP project.

## Data modes
| Mode | Source | When to use |
| --- | --- | --- |
| `mock` (default) | `webapp/model/mock.json` | Demo story (#SAP-8842), works without the backend |
| `live` | CAP service `/odata/v4/aegis` via `webapp/model/BackendAdapter.js` | Create a demo signal and pending fallback recommendation, then persist approval/rejection decisions |

Switch with the URL parameter `?mode=live` / `?mode=mock`, or in the gear dialog ("Data source").
If the backend is unreachable, live mode falls back to mock and says so.

In live mode, use **Create live disruption** on the Signals tab. Choose at least one existing shipment or inventory item explicitly; the app does not infer impacts from the description. The planner enters a fallback action and rationale, and CAP stores the signal, impact links, linked pending recommendation, and `executionStatus: "notExecuted"` before the UI refreshes from persisted records.

Signal and recommendation creation use two CAP requests. If the signal saves but its recommendation fails, the app reports the persisted signal ID, closes the form, and refreshes. Review that signal before starting a separate creation; the app does not retry the same signal automatically.

Field mapping and gaps: `docs/FRONTEND_MAPPING.md` (repository root).

## Run the live demo locally (Windows PowerShell)

Use separate terminals. The live-demo UI5 configs proxy `/odata` to CAP on port 4404.

1. Terminal 1, repository root:

   ```powershell
   $env:PORT = '4404'
   $env:AEGISCHAIN_PYTHON = 'C:\Users\jeeva\AppData\Local\Python\bin\python.exe'
   npm start
   ```

2. Terminal 2:

   ```powershell
   Set-Location app/controltower
   npm start -- --port 8081
   ```

3. Open `http://localhost:8081/index.html?mode=live`. CAP should respond at `http://localhost:4404/odata/v4/aegis`; its metadata should include `evaluateIncident` and `decideRecommendation`.

The existing CAP service on port 4004 is a legacy instance with stale metadata. It is left running and is not used by either Fiori startup script. Do not stop or restart it if it may contain demo data. Mock mode remains available at `http://localhost:8081/index.html?mode=mock` and does not require CAP.

For a different machine, set `AEGISCHAIN_PYTHON` to the installed Python interpreter that has the dependencies from the repository's `requirements.txt`.

## Decisions
Approve / Reject call `POST /odata/v4/aegis/decideRecommendation` with
`{ recommendationID, decision, decisionNote }` and show the returned `executionStatus` (`notExecuted`).
No approver or comment fields are sent; CAP records the request user and time.
In mock mode the same buttons play the simulated demo story.
