/**
 * BackendAdapter - maps Jeevan's CAP service (/odata/v4/aegis) onto the view model
 * that the Control Tower screens already use (the same shape as model/mock.json).
 *
 * Two modes:
 *   "mock" - everything comes from model/mock.json (default, always works offline)
 *   "live" - incidents, signals, recommendations, decisions and derived KPIs come from CAP.
 *            Anything the backend does not provide yet stays on the mock value or shows "-".
 *
 * Switch: URL parameter ?mode=live / ?mode=mock, or the toggle in the gear (Policies) dialog.
 * The choice is remembered in this browser (localStorage).
 *
 * Field mapping: see docs/FRONTEND_MAPPING.md
 */
sap.ui.define([], function () {
    "use strict";

    var SERVICE = "/odata/v4/aegis/";
    var STORAGE_KEY = "aegis.dataMode";

    var SEVERITY = {
        critical: { label: "CRITICAL", state: "Error" },
        high: { label: "HIGH", state: "Warning" },
        medium: { label: "MEDIUM", state: "Information" },
        low: { label: "LOW", state: "None" }
    };

    var APPROVAL = {
        pending: { text: "Awaiting approval", state: "Warning" },
        approved: { text: "Approved - decision recorded, not executed", state: "Success" },
        rejected: { text: "Rejected - decision recorded", state: "Error" }
    };

    function dash(v) { return (v === null || v === undefined || v === "") ? "-" : v; }

    function shortId(uuid) { return uuid ? uuid.slice(0, 8).toUpperCase() : "-"; }

    function time(ts) {
        if (!ts) { return "-"; }
        var d = new Date(ts);
        return isNaN(d) ? ts : d.toTimeString().slice(0, 8);
    }

    function stage(name, state) {
        var icons = { Success: "sap-icon://accept", Warning: "sap-icon://pending", None: "sap-icon://circle-task" };
        return { name: name, state: state, icon: icons[state] };
    }

    /* ---------- mapping: one CAP DisruptionSignal -> one UI incident ---------- */
    function toIncident(sig) {
        var sev = SEVERITY[(sig.severity || "").toLowerCase()] || { label: String(sig.severity || "-").toUpperCase(), state: "None" };
        var recs = sig.recommendations || [];
        var ships = (sig.shipmentImpacts || []).map(function (i) { return i.shipment; }).filter(Boolean);
        var items = (sig.inventoryImpacts || []).map(function (i) { return i.inventoryItem; }).filter(Boolean);
        var pending = recs.filter(function (r) { return r.approvalStatus === "pending"; });
        var decided = recs.filter(function (r) { return r.approvalStatus !== "pending"; });

        var status, statusState;
        if (!recs.length) { status = "No recommendation yet"; statusState = "None"; }
        else if (pending.length) { status = "Awaiting approval"; statusState = "Warning"; }
        else { var a = APPROVAL[decided[0].approvalStatus]; status = a.text; statusState = a.state; }

        // Stages are derived. REROUTE/REBALANCE never complete: backend reports executionStatus "notExecuted".
        var stages = [
            stage("SENSE", "Success"),
            stage("SIMULATE", recs.length ? "Success" : "Warning"),
            stage("VERIFY", !recs.length ? "None" : (pending.length ? "Warning" : "Success")),
            stage("REROUTE", "None"),
            stage("REBALANCE", "None")
        ];

        var firstPendingId = pending.length ? pending[0].ID : null;
        var options = recs.map(function (r) {
            var ap = APPROVAL[r.approvalStatus] || { text: r.approvalStatus, state: "None" };
            return {
                recId: r.ID,
                name: r.action,
                route: dash(r.tradeoffs),
                delay: "-", extraCost: "-", spoilage: "-", expectedLoss: "-",   // not in backend yet
                lossPct: 0, barState: "None",
                gate: ap.text + (r.decidedBy ? " (" + r.decidedBy + ")" : ""),
                gateState: ap.state,
                approvalStatus: r.approvalStatus,
                source: r.source,
                highlight: r.ID === firstPendingId ? "Information" : "None"
            };
        });

        var first = pending[0] || recs[0];
        var cargo = items.length
            ? items.map(function (i) { return i.description + " (" + Number(i.quantity) + " " + i.unitOfMeasure + ")"; }).join(", ")
            : "-";

        return {
            id: shortId(sig.ID),
            signalId: sig.ID,
            title: sig.description,
            severity: sev.label,
            severityState: sev.state,
            cargo: cargo,
            value: "-",                                         // not in backend yet
            destination: ships.length ? ships.map(function (s) { return s.destination; }).join(", ") : "-",
            viability: "-",                                     // not in backend yet
            status: status,
            statusState: statusState,
            urgency: "Live CAP data. Delay, cost, spoilage, expected loss and policy gates are not provided by the backend yet.",
            urgencyType: "Information",
            delta: ships.length
                ? "Affected shipments: " + ships.map(function (s) { return s.shipmentNumber + " (" + s.status + ", now at " + dash(s.currentLocation) + ")"; }).join("; ")
                : "No shipment impacts linked",
            stages: stages,
            options: options,
            gates: [],                                          // needs backend policy modeling
            brief: {
                headline: first ? first.action : "No recommendation yet",
                why: first ? first.rationale : "-",
                mustCheck: first && first.tradeoffs ? [{ text: first.tradeoffs }] : [],
                consigneeMessage: "-"
            }
        };
    }

    /* ---------- mapping: CAP DisruptionSignal -> Signals tab row ---------- */
    function toSignal(sig) {
        var sev = (sig.severity || "").toLowerCase();
        return {
            time: time(sig.occurredAt),
            source: sig.source,
            headline: sig.description,
            category: sig.type,
            severity: sev === "critical" ? "3" : sev === "high" ? "2" : "1",
            lanes: "-",                                         // not in backend yet
            confidence: 100,                                    // demo signals are entered by a planner
            status: (sig.recommendations || []).length ? "Incident created" : "Watching"
        };
    }

    /* ---------- derived audit trail from managed fields + decision fields ---------- */
    function toAudit(signals) {
        var rows = [];
        signals.forEach(function (sig) {
            rows.push({ ts: sig.createdAt, actor: "SIGNAL", actorState: "Information", action: "Signal recorded: " + sig.description + " (" + sig.createdBy + ")" });
            (sig.recommendations || []).forEach(function (r) {
                rows.push({ ts: r.createdAt, actor: r.source === "ai" ? "AI" : "FALLBACK", actorState: "Warning", action: "Recommendation created: " + r.action });
                if (r.decidedAt) {
                    rows.push({ ts: r.decidedAt, actor: "HUMAN", actorState: r.approvalStatus === "approved" ? "Success" : "Error",
                        action: r.approvalStatus + " by " + r.decidedBy + (r.decisionNote ? ": " + r.decisionNote : "") + " - not executed" });
                }
            });
        });
        rows.sort(function (a, b) { return new Date(a.ts) - new Date(b.ts); });
        return rows.map(function (r) {
            return { time: time(r.ts), actor: r.actor, actorState: r.actorState, action: r.action, hash: "-" };
        });
    }

    function readJSON(path) {
        return fetch(SERVICE + path, { headers: { Accept: "application/json" }, credentials: "include" })
            .then(function (res) {
                if (!res.ok) { throw new Error("GET " + path + " failed: HTTP " + res.status); }
                return res.json();
            });
    }

    // CSRF token: not needed for local CAP, required behind an SAP approuter. Harmless if unsupported.
    function fetchCsrf() {
        return fetch(SERVICE, { method: "HEAD", headers: { "X-CSRF-Token": "Fetch" }, credentials: "include" })
            .then(function (res) { return res.headers.get("X-CSRF-Token"); })
            .catch(function () { return null; });
    }

    return {
        getMode: function () {
            var p = new URLSearchParams(window.location.search).get("mode");
            if (p === "live" || p === "mock") { return p; }
            try { return window.localStorage.getItem(STORAGE_KEY) || "mock"; } catch (e) { return "mock"; }
        },

        setMode: function (sMode) {
            try { window.localStorage.setItem(STORAGE_KEY, sMode); } catch (e) { /* storage unavailable */ }
        },

        /**
         * Reads CAP and returns a full view model. Fields the backend lacks keep their mock values
         * (map geography, policies, what-if, notifications) or show "-".
         */
        loadLive: function (oMockData) {
            var expand = "DisruptionSignals?$expand=shipmentImpacts($expand=shipment),"
                + "inventoryImpacts($expand=inventoryItem),recommendations&$orderby=occurredAt desc";
            return readJSON(expand).then(function (res) {
                var signals = res.value || [];
                var incidents = signals.map(toIncident);
                var openInc = incidents.filter(function (i) { return i.status === "Awaiting approval"; }).length;
                var shipIds = {};
                var decided = 0;
                signals.forEach(function (s) {
                    (s.shipmentImpacts || []).forEach(function (i) { shipIds[i.shipment_ID] = true; });
                    (s.recommendations || []).forEach(function (r) { if (r.approvalStatus !== "pending") { decided++; } });
                });

                var data = JSON.parse(JSON.stringify(oMockData));   // keep mock-only parts
                data.Incidents = incidents;
                data.Signals = signals.map(toSignal);
                data.AuditLog = toAudit(signals);
                data.Actions = [];                                  // backend executes nothing yet
                data.Kpis = {
                    openIncidents: String(openInc),
                    atRisk: String(Object.keys(shipIds).length),
                    lossAvoided: "0",                               // not in backend yet
                    llmCalls: "0",                                  // no AI provider in this backend phase
                    autoDecisions: "0",
                    decisionsNote: "of " + decided + " decisions (all human)",
                    notifications: String(openInc)
                };
                data.Notifications = incidents.filter(function (i) { return i.status === "Awaiting approval"; }).map(function (i) {
                    return { title: "Approval needed - " + i.title, description: i.brief.headline, icon: "sap-icon://alert", time: "", state: "Warning" };
                });
                data.Meta = { mode: "live", modeLabel: "LIVE · CAP backend", modeState: "Success", chainVerified: false };
                return data;
            });
        },

        /** Calls decideRecommendation exactly as documented in docs/API.md. */
        decide: function (sRecommendationId, sDecision, sNote) {
            return fetchCsrf().then(function (token) {
                var headers = { "Content-Type": "application/json", Accept: "application/json" };
                if (token) { headers["X-CSRF-Token"] = token; }
                return fetch(SERVICE + "decideRecommendation", {
                    method: "POST",
                    headers: headers,
                    credentials: "include",
                    body: JSON.stringify({ recommendationID: sRecommendationId, decision: sDecision, decisionNote: sNote || null })
                });
            }).then(function (res) {
                return res.json().catch(function () { return {}; }).then(function (body) {
                    if (!res.ok) {
                        var msg = (body && body.error && body.error.message) || ("HTTP " + res.status);
                        var err = new Error(msg);
                        err.status = res.status;
                        throw err;
                    }
                    return body;   // { recommendationID, decision, executionStatus: "notExecuted" }
                });
            });
        }
    };
});
