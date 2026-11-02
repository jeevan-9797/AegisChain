sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/MessageToast",
    "sap/m/MessageBox",
    "sap/m/Dialog",
    "sap/m/Button",
    "sap/m/TextArea",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
    "sap/ui/dom/includeScript",
    "sap/ui/dom/includeStylesheet",
    "com/aegis/controltower/model/BackendAdapter"
], function (Controller, MessageToast, MessageBox, Dialog, Button, TextArea, Filter, FilterOperator, includeScript, includeStylesheet, BackendAdapter) {
    "use strict";

    // Leaflet (open-source map library) is loaded from a CDN - a "regular tool" fallback,
    // because OpenUI5 has no map control.
    var LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist/";

    return Controller.extend("com.aegis.controltower.controller.ControlTower", {

        /* ---------------------------------------------------------------
         * STARTUP
         * ------------------------------------------------------------- */
        onInit: function () {
            this._leafletReady = Promise.all([
                includeStylesheet({ url: LEAFLET + "leaflet.css", id: "leaflet-css" }),
                includeScript({ url: LEAFLET + "leaflet.js", id: "leaflet-js" })
            ]);

            // Data source: mock.json (default) or Jeevan's CAP service (see model/BackendAdapter.js)
            var oModel = this.getOwnerComponent().getModel();
            oModel.dataLoaded().then(function () {
                this._mockSnapshot = JSON.parse(JSON.stringify(oModel.getData()));
                if (BackendAdapter.getMode() === "live") { this._loadLive(); }
            }.bind(this));
        },

        /* ---------------------------------------------------------------
         * DATA MODE  (mock <-> live CAP backend)
         * ------------------------------------------------------------- */
        _isLive: function () {
            return this.getView().getModel().getProperty("/Meta/mode") === "live";
        },

        _loadLive: function () {
            var oModel = this.getView().getModel() || this.getOwnerComponent().getModel();
            return BackendAdapter.loadLive(this._mockSnapshot).then(function (oData) {
                oModel.setData(oData);
                this.byId("incidentDetail").bindElement("/Incidents/0");
                BackendAdapter.setMode("live");
            }.bind(this)).catch(function (oErr) {
                BackendAdapter.setMode("mock");
                this._loadMock();
                MessageBox.warning("The CAP backend is not reachable, so the app switched back to mock data.\n\n"
                    + "Start it from the repository root with: npm start\n\nDetails: " + oErr.message);
            }.bind(this));
        },

        _loadMock: function () {
            var oModel = this.getView().getModel() || this.getOwnerComponent().getModel();
            oModel.setData(JSON.parse(JSON.stringify(this._mockSnapshot)));
            this.byId("incidentDetail").bindElement("/Incidents/0");
        },

        onModeChange: function (oEvent) {
            var sMode = oEvent.getParameter("item").getKey();
            BackendAdapter.setMode(sMode);
            if (sMode === "live") {
                this._loadLive().then(function () {
                    if (this._isLive()) { MessageToast.show("Live CAP data loaded"); }
                }.bind(this));
            } else {
                this._loadMock();
                MessageToast.show("Mock demo data loaded");
            }
        },

        _selectedOption: function () {
            var oItem = this.byId("optionsTable").getSelectedItem();
            return oItem ? oItem.getBindingContext().getObject() : null;
        },

        _decideLive: function (sDecision, sNote) {
            var oOpt = this._selectedOption();
            if (!oOpt || !oOpt.recId) { MessageToast.show("Select a recommendation in the table first"); return; }
            if (oOpt.approvalStatus !== "pending") { MessageToast.show("This recommendation has already been decided"); return; }
            BackendAdapter.decide(oOpt.recId, sDecision, sNote).then(function (oRes) {
                MessageBox.success("Decision recorded: " + oRes.decision
                    + "\nexecutionStatus: " + oRes.executionStatus
                    + "\n\nThe recovery action has NOT been executed - the backend only records the decision.");
                return this._loadLive();
            }.bind(this)).catch(function (oErr) {
                MessageBox.error(oErr.status === 409
                    ? "This recommendation was already decided by someone else. Refreshing."
                    : "Could not record the decision: " + oErr.message);
                this._loadLive();
            }.bind(this));
        },

        /* ---------------------------------------------------------------
         * MAP  (Overview tab)
         * ------------------------------------------------------------- */
        onMapRendered: function () {
            if (this._map) {                     // already drawn: just fix its size
                this._map.invalidateSize();
                return;
            }
            this._leafletReady.then(this._drawMap.bind(this)).catch(function () {
                var oDom = this.byId("mapHtml").getDomRef();
                if (oDom) { oDom.innerHTML = "<p style='padding:1rem'>Map library could not load (no internet).</p>"; }
            }.bind(this));
        },

        _drawMap: function () {
            var oDom = this.byId("mapHtml").getDomRef();
            if (!oDom || !window.L || this._map) { return; }
            var L = window.L;
            var oData = this.getView().getModel().getData();

            var map = L.map(oDom, { worldCopyJump: true }).setView([10, 30], 3);
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "&copy; OpenStreetMap contributors", maxZoom: 8
            }).addTo(map);

            var COLORS = { OPEN: "#256F3A", DEGRADED: "#E76500", CLOSED: "#AA0808" };
            var DASH = { SEA: "8 6", AIR: "2 6", ROAD: null };

            (oData.Lanes || []).forEach(function (lane) {
                L.polyline(lane.path, {
                    color: COLORS[lane.status] || "#0070F2",
                    weight: lane.status === "CLOSED" ? 4 : 3,
                    dashArray: DASH[lane.mode]
                }).bindTooltip(lane.name + " (" + lane.status + ")").addTo(map);
            });
            (oData.Nodes || []).forEach(function (n) {
                L.circleMarker([n.lat, n.lon], { radius: 5, color: "#0B2545", fillOpacity: 0.9 })
                    .bindTooltip(n.name).addTo(map);
            });
            (oData.Consignments || []).forEach(function (c) {
                L.circleMarker([c.lat, c.lon], {
                    radius: 9, color: c.status === "AT RISK" ? "#AA0808" : "#256F3A", weight: 3, fillOpacity: 0.3
                }).bindTooltip(c.id + " · " + c.status, { permanent: true, direction: "right" }).addTo(map);
            });
            this._map = map;
        },

        onTabSelect: function (oEvent) {
            // Leaflet needs a size refresh when its tab becomes visible again
            if (oEvent.getParameter("key") === "overview" && this._map) {
                setTimeout(function () { this._map.invalidateSize(); }.bind(this), 50);
            }
        },

        /* ---------------------------------------------------------------
         * NAVIGATION between tabs
         * ------------------------------------------------------------- */
        onGoTab: function (oEvent) {
            this.byId("tabs").setSelectedKey(oEvent.getSource().data("tab"));
        },

        onIncidentPress: function (oEvent) {
            // Show the clicked incident on the Incidents tab
            var sPath = oEvent.getSource().getBindingContext().getPath();
            this.byId("incidentDetail").bindElement(sPath);
            this.byId("tabs").setSelectedKey("incidents");
        },

        /* ---------------------------------------------------------------
         * SIGNALS tab: search + category filter
         * ------------------------------------------------------------- */
        onSignalFilter: function () {
            var sQuery = this.byId("signalSearch").getValue();
            var sCat = this.byId("signalCategory").getSelectedKey();
            var aFilters = [];
            if (sQuery) { aFilters.push(new Filter("headline", FilterOperator.Contains, sQuery)); }
            if (sCat && sCat !== "All") { aFilters.push(new Filter("category", FilterOperator.EQ, sCat)); }
            this.byId("signalsTable").getBinding("items").filter(aFilters);
        },

        onConfirmSignal: function (oEvent) {
            var oCtx = oEvent.getSource().getBindingContext();
            oCtx.getModel().setProperty(oCtx.getPath() + "/status", "Watching");
            MessageToast.show("Signal confirmed by analyst - now monitored");
        },

        onDismissSignal: function (oEvent) {
            var oCtx = oEvent.getSource().getBindingContext();
            oCtx.getModel().setProperty(oCtx.getPath() + "/status", "Ignored");
            MessageToast.show("Signal dismissed");
        },

        /* ---------------------------------------------------------------
         * APPROVE / REJECT  (Incidents tab)
         * Live mode : POST /odata/v4/aegis/decideRecommendation (records the decision only,
         *             executionStatus "notExecuted").
         * Mock mode : simulated story for the demo (_executePlan).
         * ------------------------------------------------------------- */
        onApprove: function () {
            var oCtx = this.byId("incidentDetail").getBindingContext();
            var oComment = new TextArea({ width: "100%", rows: 3, placeholder: "Comment for the audit trail (optional)" });
            var oDialog = new Dialog({
                title: "Approve plan for #" + oCtx.getProperty("id") + "?",
                contentWidth: "420px",
                content: [oComment],
                beginButton: new Button({
                    text: "Approve", type: "Emphasized",
                    press: function () {
                        if (this._isLive()) { this._decideLive("approved", oComment.getValue()); }
                        else { this._executePlan(oCtx, oComment.getValue()); }
                        oDialog.close();
                    }.bind(this)
                }),
                endButton: new Button({ text: "Cancel", press: function () { oDialog.close(); } }),
                afterClose: function () { oDialog.destroy(); }
            });
            this.getView().addDependent(oDialog);
            oDialog.open();
        },

        onReject: function () {
            var oCtx = this.byId("incidentDetail").getBindingContext();
            MessageBox.confirm("Reject the recommended plan? The incident goes back to the planner.", {
                onClose: function (sAction) {
                    if (sAction !== MessageBox.Action.OK) { return; }
                    if (this._isLive()) { this._decideLive("rejected", null); return; }
                    var oModel = oCtx.getModel();
                    oModel.setProperty(oCtx.getPath() + "/status", "Rejected - back to planner");
                    oModel.setProperty(oCtx.getPath() + "/statusState", "Error");
                    this._audit("HUMAN", "Error", "Plan rejected by HK - Director");
                    MessageToast.show("Plan rejected and logged");
                }.bind(this)
            });
        },

        _executePlan: function (oCtx, sComment) {
            var oModel = oCtx.getModel();
            var sPath = oCtx.getPath();

            // 1. Status + all 5 stages done
            oModel.setProperty(sPath + "/status", "Executed - approved by HK (simulated in mock mode)");
            oModel.setProperty(sPath + "/statusState", "Success");
            oModel.getProperty(sPath + "/stages").forEach(function (s, i) {
                oModel.setProperty(sPath + "/stages/" + i + "/state", "Success");
                oModel.setProperty(sPath + "/stages/" + i + "/icon", "sap-icon://accept");
            });

            // 2. Audit trail (Agent C actions follow the human approval)
            this._audit("HUMAN", "Success", "Approved by HK - Director" + (sComment ? ": " + sComment : ""));
            this._audit("AGENT C", "Information", "Air booking for 11,200 doses BRU > NBO");
            this._audit("AGENT C", "Information", "Container rerouted via Cape of Good Hope");
            this._audit("AGENT C", "Information", "Stock transfer Nairobi > Mombasa 3,000 doses");
            this._audit("AGENT C", "Information", "Purchase requisition created (simulated ERP write)");
            this._audit("AGENT C", "Information", "Consignee notified");

            // 3. Actions table
            oModel.setProperty("/Actions", [
                { type: "Air booking", ref: "AWB-176-2231", status: "Done" },
                { type: "Reroute", ref: "Cape route", status: "Done" },
                { type: "Stock transfer", ref: "STO-4500012", status: "Done" },
                { type: "Purchase requisition", ref: "PR-10004471", status: "Simulated ERP write" },
                { type: "Notification", ref: "Mombasa store", status: "Done" }
            ]);

            // 4. KPIs + map marker
            oModel.setProperty("/Kpis/openIncidents", "1");
            oModel.setProperty("/Kpis/decisionsNote", "of 2 decisions");
            oModel.setProperty("/Kpis/notifications", "2");

            MessageToast.show("Plan approved - agents are executing");
            this.byId("tabs").setSelectedKey("audit");
        },

        _audit: function (sActor, sState, sAction) {
            // Demo-only: a random short hash. The backend computes the real hash chain.
            var oModel = this.getView().getModel();
            var aLog = oModel.getProperty("/AuditLog").slice();
            aLog.push({
                time: new Date().toTimeString().slice(0, 8),
                actor: sActor, actorState: sState, action: sAction,
                hash: Math.random().toString(16).slice(2, 10)
            });
            oModel.setProperty("/AuditLog", aLog);
        },

        /* ---------------------------------------------------------------
         * WHAT-IF tab  (simple modeled maths for the demo;
         * LATER: call backend  POST /odata/v4/aegis/whatIf)
         * ------------------------------------------------------------- */
        onRunWhatIf: function () {
            var oModel = this.getView().getModel();
            var duty = Number(oModel.getProperty("/WhatIf/duty")) / 100;
            var bAll = oModel.getProperty("/WhatIf/scope") === "ALL";
            var exposure = bAll ? 1200000 : 450000;            // value of affected orders (USD)

            var rows = [
                { option: "Absorb the change", landed: exposure * duty, lead: "0 d", risk: "Low" },
                { option: "Re-source from India (WHO-PQ)", landed: 46000 + exposure * 0.06, lead: "+5 d", risk: "Medium" },
                { option: "Split origin 50 / 50", landed: exposure * duty / 2 + 20000, lead: "+2 d", risk: "Low" },
                { option: "Delay purchase 30 days", landed: exposure * 0.25, lead: "+30 d", risk: "High (stock-outs)" }
            ];
            var max = Math.max.apply(null, rows.map(function (r) { return r.landed; })) || 1;
            var best = rows.reduce(function (a, b) { return b.landed < a.landed ? b : a; });
            var bestValue = best.landed;

            rows.forEach(function (r) {
                r.lossPct = Math.round(r.landed / max * 100);
                r.loss = "$" + Math.round(r.landed / 1000) + "K";
                r.highlight = r === best ? "Information" : "None";
                r.barState = r === best ? "Information" : "None";
                r.landed = "+$" + Math.round(r.landed).toLocaleString("en-US");
            });

            oModel.setProperty("/WhatIf/results", rows);
            oModel.setProperty("/WhatIf/ordersAffected", bAll ? "6" : "1");
            oModel.setProperty("/WhatIf/landedCostChange", String(Math.round(exposure * duty / 1000)));
            oModel.setProperty("/WhatIf/bestSaving", String(Math.max(0, Math.round((exposure * duty - bestValue) / 1000))));
            MessageToast.show("Simulation finished - nothing was executed");
        },

        /* ---------------------------------------------------------------
         * AUDIT REPORT  (printable page built from the audit data)
         * ------------------------------------------------------------- */
        onAuditReport: function () {
            var oData = this.getView().getModel().getData();
            var rows = oData.AuditLog.map(function (e, i) {
                return "<tr><td>" + (i + 1) + "</td><td>" + e.time + "</td><td>" + e.actor + "</td><td>" + e.action + "</td><td><code>" + e.hash + "</code></td></tr>";
            }).join("");
            var acts = oData.Actions.map(function (a) {
                return "<tr><td>" + a.type + "</td><td>" + a.ref + "</td><td>" + a.status + "</td></tr>";
            }).join("") || "<tr><td colspan='3'>No actions executed yet</td></tr>";
            var html = "<html><head><title>AegisChain audit report</title><style>" +
                "body{font-family:Arial,sans-serif;margin:32px;color:#131E29}h1{color:#0070F2;font-size:22px}" +
                "h2{font-size:15px;border-bottom:1px solid #0070F2;padding-bottom:4px;margin-top:24px}" +
                "table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #D9DEE3;padding:6px;text-align:left}" +
                "th{background:#F5F6F7}</style></head><body>" +
                "<h1>AegisChain - Decision Audit Report</h1><p>Generated " + new Date().toLocaleString() +
                " &middot; " + (oData.Meta && oData.Meta.mode === "live"
                    ? "Source: live CAP backend &middot; decisions recorded, not executed &middot; no hash chain yet"
                    : "Chain verified: YES (demo) &middot; Figures are modeled") + "</p>" +
                "<h2>Decision trail</h2><table><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Hash</th></tr>" + rows + "</table>" +
                "<h2>Actions executed</h2><table><tr><th>Type</th><th>Reference</th><th>Status</th></tr>" + acts + "</table>" +
                "<p style='margin-top:32px;font-size:11px'>Confidential - generated by AegisChain</p>" +
                "<script>window.print()<\/script></body></html>";
            var w = window.open("", "_blank");
            if (!w) { MessageToast.show("Allow pop-ups to open the report"); return; }
            w.document.write(html);
            w.document.close();
        },

        /* ---------------------------------------------------------------
         * HEADER: bell + gear
         * ------------------------------------------------------------- */
        onOpenNotifications: function (oEvent) {
            this.byId("notifPopover").openBy(oEvent.getSource());
        },

        onOpenPolicies: function () {
            this.byId("policyDialog").open();
        },

        onClosePolicies: function () {
            this.byId("policyDialog").close();
        },

        onResetDemo: function () {
            if (this._isLive()) {
                this.byId("policyDialog").close();
                this._loadLive().then(function () { MessageToast.show("Live data refreshed (the CAP in-memory data resets when the server restarts)"); });
                return;
            }
            var oModel = this.getView().getModel();
            oModel.loadData(sap.ui.require.toUrl("com/aegis/controltower/model/mock.json")).then(function () {
                this._mockSnapshot = JSON.parse(JSON.stringify(oModel.getData()));
                this.byId("incidentDetail").bindElement("/Incidents/0");
                this.byId("tabs").setSelectedKey("overview");
                this.byId("policyDialog").close();
                MessageToast.show("Demo reset");
            }.bind(this));
        }
    });
});
