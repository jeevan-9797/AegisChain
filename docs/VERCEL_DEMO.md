# AegisChain Control Tower — Vercel Demo (Mock Mode)

This document describes the standalone frontend deployment of the **AegisChain Operator Control Tower** on Vercel running in mock mode.

- **Live Production URL**: [https://aegischain-control-tower.vercel.app](https://aegischain-control-tower.vercel.app)
- **Deployment Mode**: Standalone SAPUI5 Frontend (Mock Mode)
- **CDN Bootstrap**: SAPUI5 v1.154.0 via SAP CDN (`https://ui5.sap.com/1.154.0/resources/sap-ui-core.js`)

---

## Architecture Overview

The Vercel deployment hosts the compiled SAPUI5 frontend independently of the SAP BTP / CAP backend:
1. **Mock Data Source**: All shipment statuses, predictive risk signals, disruption incidents, what-if simulations, and audit logs are powered by `model/mock.json`.
2. **Standalone Bootstrap**: `index.html` loads the official SAPUI5 runtime from the SAP CDN and initializes the component directly using `sap/ui/core/ComponentSupport`.
3. **Interactive Map**: Renders live global shipment routes and disruption zones via Leaflet.js and OpenStreetMap tiles.
4. **No Backend Required**: Runs completely client-side in standard modern web browsers.

---

## Exact Build & Deployment Steps

Follow these steps from the repository root to reproduce the standalone build and deploy to Vercel:

### 1. Build the UI5 Frontend
```bash
cd app/controltower
npm install
npx.cmd ui5 build --clean-dest --dest dist
```

### 2. Configure Standalone CDN Bootstrap in `dist/index.html`
Update the bootstrap script tag in `dist/index.html` to point to the SAP CDN:
```html
<script id="sap-ui-bootstrap"
    src="https://ui5.sap.com/1.154.0/resources/sap-ui-core.js"
    data-sap-ui-theme="sap_horizon"
    data-sap-ui-resource-roots='{ "com.aegis.controltower": "./" }'
    data-sap-ui-on-init="module:sap/ui/core/ComponentSupport"
    data-sap-ui-compat-version="edge"
    data-sap-ui-async="true"
    data-sap-ui-frame-options="trusted">
</script>
```

### 3. Add `dist/vercel.json`
Create `dist/vercel.json` to handle single-page routing and security headers:
```json
{
  "rewrites": [
    { "source": "/", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ]
}
```

### 4. Test Locally
Run a local static server:
```bash
npx.cmd serve dist -l 5055
```
Open `http://localhost:5055/index.html` and verify:
- Control Tower loads with no console errors (excluding favicon 404)
- All 5 tabs render: Overview, Signals, Incidents, What-if, Audit
- Global disruption map renders with Leaflet panes
- Status bar displays `MOCK · demo data`

### 5. Deploy to Vercel
```bash
npx.cmd vercel deploy dist --prod --yes --name aegischain-control-tower
```

---

## Verification Checklist

| Check | Localhost (`:5055`) | Production (`vercel.app`) | Status |
|---|---|---|---|
| HTTP 200 on `/`, `/index.html`, `/manifest.json`, `/model/mock.json` | Passed | Passed | ✅ OK |
| Console errors (excluding favicon 404) | 0 errors | 0 errors | ✅ OK |
| Overview, Signals, Incidents, What-if, Audit tabs | 5/5 rendered | 5/5 rendered | ✅ OK |
| Global interactive map (Leaflet) | 7 panes rendered | 7 panes rendered | ✅ OK |
| Mode label | `MOCK · demo data` | `MOCK · demo data` | ✅ OK |
