
CREATE TABLE aegischain_db_Suppliers (
  ID NVARCHAR(36) NOT NULL,
  createdAt TIMESTAMP_TEXT,
  createdBy NVARCHAR(255),
  modifiedAt TIMESTAMP_TEXT,
  modifiedBy NVARCHAR(255),
  name NVARCHAR(100),
  country NVARCHAR(50),
  region NVARCHAR(50),
  reliabilityScore REAL_DECIMAL(5, 2),
  riskLevel NVARCHAR(20),
  leadTimeDays INTEGER,
  PRIMARY KEY(ID)
);

CREATE TABLE aegischain_db_Shipments (
  ID NVARCHAR(36) NOT NULL,
  createdAt TIMESTAMP_TEXT,
  createdBy NVARCHAR(255),
  modifiedAt TIMESTAMP_TEXT,
  modifiedBy NVARCHAR(255),
  trackingNumber NVARCHAR(50),
  origin NVARCHAR(100),
  destination NVARCHAR(100),
  status NVARCHAR(30),
  eta DATE_TEXT,
  delayProbability REAL_DECIMAL(5, 2),
  supplier_ID NVARCHAR(36),
  PRIMARY KEY(ID)
);

CREATE TABLE aegischain_db_RiskAlerts (
  ID NVARCHAR(36) NOT NULL,
  createdAt TIMESTAMP_TEXT,
  createdBy NVARCHAR(255),
  modifiedAt TIMESTAMP_TEXT,
  modifiedBy NVARCHAR(255),
  alertID NVARCHAR(50),
  severity NVARCHAR(20),
  description NVARCHAR(500),
  timestamp TIMESTAMP_TEXT,
  supplier_ID NVARCHAR(36),
  PRIMARY KEY(ID)
);

