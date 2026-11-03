namespace aegischain;

using { cuid, managed } from '@sap/cds/common';

// --- Your Team's Existing Entities (Keep or merge with these) ---
entity Shipments : cuid, managed {
  shipmentID   : String(50);
  origin       : String(100);
  destination  : String(100);
  status       : String(50);
  supplier     : Association to Suppliers;
}

entity DisruptionSignals : cuid, managed {
  signalID     : String(50);
  description  : String(500);
  severity     : String(20);
}

// --- New Integrated Entities ---
entity Suppliers : cuid, managed {
  name             : String(100);
  country          : String(50);
  region           : String(50);
  reliabilityScore : Decimal(5,2);
  riskLevel        : String(20);
  leadTimeDays     : Integer;
  shipments        : Association to many Shipments on shipments.supplier = $self;
}

entity RiskAlerts : cuid, managed {
  alertID          : String(50);
  severity         : String(20);
  description      : String(500);
  timestamp        : Timestamp;
  supplier         : Association to Suppliers;
}