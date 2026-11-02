# AegisChain

SAP-based, AI-assisted supply-chain resilience application built with SAP CAP. The current repository includes a CAP backend and a SAPUI5 control-tower demo frontend using mock data.

## Project structure

| File or folder | Purpose |
| --- | --- |
| `app/` | UI frontends, including `app/controltower/` |
| `db/` | CAP domain model and local mock data |
| `srv/` | CAP service definitions and handlers |
| `docs/` | Product requirements, architecture, development, and API guidance |
| `README.md` | Project overview and getting-started guide |

## Getting started

Install the backend dependencies and start the CAP server from the repository root:

```sh
npm install
npm start
```

For CAP development watch mode, make the CAP development kit CLI available in `PATH`, then run:

```sh
cds watch
```

The local backend uses SQLite and seeded mock shipment and inventory data. It does not require production SAP credentials. The UI5 control-tower app is under `app/controltower/`; see its README for frontend-specific setup.

## Documentation

- [Product requirements](docs/PRODUCT_REQUIREMENTS.md)
- [Intended architecture](docs/ARCHITECTURE.md)
- [Development workflow](docs/DEVELOPMENT.md)
- [CAP API contract](docs/API.md)

Learn more about CAP at <https://cap.cloud.sap>.
