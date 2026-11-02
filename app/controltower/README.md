# AegisChain - Operator Control Tower (frontend)

SAPUI5 freestyle app built in SAP Business Application Studio. Runs on mock data
(`webapp/model/mock.json`) until the CAP backend is connected.

## Run
- In BAS: right-click `webapp` -> Preview Application
- Locally: `npm install` then `npm start`

## Connect the backend later
Replace the default model in `webapp/manifest.json` with the CAP OData V4 service,
and replace `_executePlan` in `webapp/controller/ControlTower.controller.js` with a call
to the backend `decide` action. Tabs, bindings and layout stay the same.
