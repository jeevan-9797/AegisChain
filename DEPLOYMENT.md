# AegisChain SAP BTP Deployment Guide

This guide describes how to build, configure, and deploy **AegisChain** as a Multi-Target Application (MTA) to **SAP Business Technology Platform (SAP BTP) Cloud Foundry**, integrating with **SAP HANA Cloud**, **SAP XSUAA**, **HTML5 Application Repository**, and **SAP Build Work Zone (Standard Edition)**.

---

## 1. Prerequisites

### Local / Development Environment (or SAP Business Application Studio)
- **Node.js**: `v20.x` or `v22.x` (LTS recommended)
- **Cloud MTA Build Tool (MBT)**: version `1.2.x` or higher
  ```bash
  npm install -g mbt
  ```
- **SAP Cloud Development Kit (`@sap/cds-dk`)**: version `10.x` (already included in devDependencies)
- **Cloud Foundry CLI (`cf`)**: version `8.x` or higher
- **Cloud Foundry MultiApps Plugin**:
  ```bash
  cf add-plugin-repo CF-Community https://plugins.cloudfoundry.org
  cf install-plugin multiapps
  ```
- **Make Tooling** (if building MTA on Windows locally; already available by default in SAP Business Application Studio and Linux/macOS environments).

---

## 2. Required SAP BTP Entitlements and Services

Before deployment, ensure your SAP BTP subaccount has the following entitlements assigned in the **SAP BTP Cockpit** (`Entitlements` > `Configure Entitlements` > `Add Service Plans`):

| Service Name | Service Identifier | Required Plan | Purpose |
| :--- | :--- | :--- | :--- |
| **SAP HANA Cloud** | `hana-cloud` | `hana` | Production database instance |
| **SAP HANA Schemas & HDI Containers** | `hana` | `hdi-shared` | HDI container instance for database tables, views, and data |
| **Authorization and Trust Management** | `xsuaa` | `application` | OAuth2 / JWT authentication, role templates, and scopes |
| **Destination Service** | `destination` | `lite` | Routing destinations between Approuter/Work Zone and CAP backend |
| **HTML5 Application Repository** | `html5-apps-repo` | `app-host`, `app-runtime` | Storage and runtime serving of the UI5 application bundle |
| **SAP Build Work Zone, standard edition** | `SAPLaunchpad` / `workzone` | `standard` (Application) | Fiori Launchpad portal hosting the Control Tower tile |
| **Cloud Foundry Runtime** | `APPLICATION_RUNTIME` | Memory Quota (at least 1–2 GB) | Runtime for CAP Node.js backend and deployment jobs |

---

## 3. SAP HANA Cloud Setup

> [!IMPORTANT]
> This step requires SAP BTP Cockpit administrator access.

1. In your SAP BTP Subaccount, navigate to **Services** > **Instances and Subscriptions**.
2. If not already created, create an instance of **SAP HANA Cloud**:
   - Choose **SAP HANA Cloud** > **SAP HANA Database**.
   - Set the instance name (e.g. `aegischain-db`).
   - Configure the administrator password and ensure the instance is running.
3. **Map the SAP HANA instance to your Cloud Foundry Org and Space**:
   - In SAP HANA Cloud central, verify that the instance is mapped to your target Cloud Foundry organization and space.
   - Under **Instance Connections**, ensure **Allow all IP addresses** or your organization's allowed IP range is selected so Cloud Foundry applications can establish connections.

---

## 4. Cloud Foundry Authentication and Target Space

Log in to your SAP BTP Cloud Foundry environment using the Cloud Foundry CLI:

```bash
cf login -a <CF_API_ENDPOINT>
```
*Example endpoints: `https://api.cf.eu10.hana.ondemand.com` or `https://api.cf.us10-001.hana.ondemand.com`.*

Select your target **Organization** and **Space**:
```bash
cf target -o <YOUR_ORG> -s <YOUR_SPACE>
```

Verify that the target space has available memory quota:
```bash
cf space <YOUR_SPACE>
```

---

## 5. Security Descriptor and Role Collections (`xs-security.json`)

The application defines fine-grained security scopes based on the core business actors:

- **Scopes**:
  - `$XSAPPNAME.Viewer`: Read-only access to shipments, inventory, disruption signals, alerts, and recommendations.
  - `$XSAPPNAME.Operator`: Permission to trigger disruption evaluations (`evaluateIncident`) and record signals.
  - `$XSAPPNAME.Approver`: Permission to approve or reject recovery recommendations (`decideRecommendation`).
  - `$XSAPPNAME.Admin`: Full administrative control over the application.
- **Role Collections** automatically created upon deployment:
  - `AegisChain_Viewer`
  - `AegisChain_Operator`
  - `AegisChain_Approver`
  - `AegisChain_Admin`

### User Assignment in BTP Cockpit:
1. Navigate to **Security** > **Users** in the BTP Subaccount Cockpit.
2. Select your user (or team members).
3. Under **Role Collections**, click **Assign Role Collection**.
4. Assign `AegisChain_Admin` (or specific roles as appropriate) to test live approvals and incident evaluations.

---

## 6. MTA Architecture Overview

AegisChain uses the modern **SAP BTP Managed Application Router** pattern, optimized for **SAP Build Work Zone, standard edition**:

```
+---------------------------------------------------------------+
|              SAP Build Work Zone (Standard Edition)          |
|                  (Managed Application Router)                 |
+-------------------------------+-------------------------------+
                                |
         +----------------------+----------------------+
         |                                             |
         v                                             v
+------------------------+                  +--------------------+
| HTML5 App Repository   |                  | Destination Service|
| (UI5 Control Tower)    |                  | aegischain-srv-api |
+------------------------+                  +---------+----------+
                                                      | ForwardAuthToken
                                                      v
                                            +--------------------+
                                            | CAP Node.js Backend|
                                            | (aegischain-srv)   |
                                            +----+----------+----+
                                                 |          |
                        +------------------------+          |
                        v                                   v
             +---------------------+              +------------------+
             | SAP HANA Cloud      |              | Remote ML Service|
             | (HDI Container)     |              | (Secure Bearer)  |
             +---------------------+              +------------------+
```

### Components in `mta.yaml`:
1. **`aegischain-srv`**: Node.js backend executing CAP runtime, bound to HANA and XSUAA.
2. **`aegischain-db-deployer`**: HDI deployer module running `@sap/hdi-deploy` to materialize CDS entities and seed data into SAP HANA Cloud.
3. **`controltower`**: UI5 build module generating Component preload and optimized assets into `dist/`.
4. **`aegischain-app-deployer`**: Content deployer packaging `controltower.zip` into the HTML5 Application Repository (`app-host`).
5. **`aegischain-destinations`**: Content deployer provisioning dynamic destinations for Work Zone and backend JWT token exchange.

---

## 7. MTA Build Process

### Step 1: Install Dependencies
From the project root:
```bash
npm install
cd app/controltower && npm install && cd ../..
```

### Step 2: Validate Model and Production Compilation
```bash
npx cds build --production
```
*This generates `gen/srv` with production dependencies and `gen/db` with SAP HANA table definitions (`.hdbtable`, `.hdbview`, `.hdbtabledata`).*

### Step 3: Build MTA Archive
Run the Cloud MTA Build Tool:
```bash
mbt build
# or if mbt is not globally installed:
npx mbt build
```

This compiles all modules, builds UI5 assets, packages the deployers, and outputs:
```
mta_archives/aegischain_1.0.0.mtar
```

---

## 8. Deployment to SAP BTP Cloud Foundry

Deploy the generated archive using the Cloud Foundry CLI:

```bash
cf deploy mta_archives/aegischain_1.0.0.mtar
```

During deployment:
1. Cloud Foundry creates or updates the required managed service instances:
   - `aegischain-db` (HANA HDI container)
   - `aegischain-auth` (XSUAA application)
   - `aegischain-destination` (Destination service)
   - `aegischain-html5-repo-host` (HTML5 app repository host)
2. Executes `aegischain-db-deployer` to create database tables and views in HANA.
3. Uploads the UI5 application zip into HTML5 Application Repository via `aegischain-app-deployer`.
4. Creates the service destinations via `aegischain-destinations`.
5. Starts the CAP backend microservice `aegischain-srv`.

### Verify Deployment Status
```bash
cf apps
cf services
```

---

## 9. Machine Learning Service Configuration (Post-Deployment)

The CAP backend (`aegischain-srv`) supports remote ML integration for automated incident evaluation and briefing generation.

To connect `aegischain-srv` to your deployed Python evaluator service:

```bash
# Set remote evaluation mode
cf set-env aegischain-srv AEGISCHAIN_ML_MODE remote

# Set the HTTPS URL of the evaluator microservice
cf set-env aegischain-srv AEGISCHAIN_ML_URL https://<your-ml-service-host>/internal/v1/evaluate

# Inject the shared bearer token (must match AEGISCHAIN_EVALUATOR_TOKEN in the ML service, at least 32 bytes)
cf set-env aegischain-srv AEGISCHAIN_ML_TOKEN <your-32-byte-secret>

# Optional: adjust timeout in milliseconds (default 15000)
cf set-env aegischain-srv AEGISCHAIN_ML_TIMEOUT_MS 15000

# Restage the backend to apply changes
cf restage aegischain-srv
```

> [!CAUTION]
> Never commit `AEGISCHAIN_ML_TOKEN` or any credentials into git repository files. Use `cf set-env` or BTP user-provided service instances.

---

## 10. SAP Build Work Zone Configuration

Once the MTA is deployed, integrate the UI5 Control Tower into your SAP Build Work Zone Launchpad:

1. **Assign Launchpad Administrator Role**:
   - In BTP Cockpit > **Security** > **Users**, assign the `Launchpad_Admin` role collection to your user.
2. **Open SAP Build Work Zone**:
   - Go to **Instances and Subscriptions** > Click on **SAP Build Work Zone, standard edition**.
3. **Verify HTML5 App Discovery**:
   - Open **Channel Manager** and click the **Refresh** button on the `HTML5 Apps` content channel.
   - Go to **Content Manager** > **HTML5 Apps** tab.
   - Verify that **AegisChain Control Tower** (`com.aegis.controltower`) is listed.
4. **Add to Role**:
   - Click on the app > **Edit** > Assign to the **Everyone** role (or create a dedicated `AegisChain Operators` role).
5. **Add to Group / Page**:
   - In **Content Manager** > **Groups** tab, select a group (e.g. `Supply Chain Resilience`) and add the **Control Tower** tile.
6. **Launch Site**:
   - Go to **Site Directory** > Open your Launchpad Site (or create one).
   - Click the **AegisChain Control Tower** tile to access the live application!

---

## 11. Troubleshooting Guide

| Issue | Potential Cause | Resolution |
| :--- | :--- | :--- |
| **`401 Unauthorized` on OData requests** | User lacks required scopes or token forwarding is misconfigured. | Verify user has `AegisChain_Admin` or `AegisChain_Viewer` assigned in BTP Cockpit; ensure `HTML5.ForwardAuthToken: true` is present on the destination. |
| **`404 Not Found` on `/odata/v4/aegis/*`** | Destination `aegischain-srv-api` is missing or pointing to invalid URL. | Check `cf destinations` or Subaccount Destinations in BTP Cockpit. Verify destination URL matches `cf app aegischain-srv` default URL. |
| **HANA deployment fails: `hdi-shared` error** | SAP HANA Cloud instance is stopped or not mapped to the CF space. | Check SAP HANA Cloud status in BTP Cockpit; ensure the database instance is in state `RUNNING` and mapped to your space. |
| **`403 Forbidden` on POST actions** | CSRF token missing or XSUAA validation failure. | UI's `BackendAdapter.js` handles CSRF tokens automatically (`fetchCsrf()`); ensure `xs-app.json` routes match correctly. |
| **UI displays "-" or fallback data** | UI is in local mock mode. | In the UI, click the gear (Settings) dialog to toggle data mode from **Mock** to **Live**, or append `?mode=live` to the launchpad URL. |
