namespace aegischain.db;
using { cuid, managed } from '@sap/cds/common';

entity Suppliers : cuid, managed {
  name             : String(100);
  country          : String(50);
  region           : String(50);
  reliabilityScore : Decimal(5,2);
  riskLevel        : String(20); // LOW, MEDIUM, HIGH, CRITICAL
  leadTimeDays     : Integer;
  shipments        : Association to many Shipments on shipments.supplier = $self;
}

entity Shipments : cuid, managed {
  trackingNumber   : String(50);
  origin           : String(100);
  destination      : String(100);
  status           : String(30); // IN_TRANSIT, DELAYED, DELIVERED, REROUTED
  eta              : Date;
  delayProbability : Decimal(5,2);
  supplier         : Association to Suppliers;
}

entity RiskAlerts : cuid, managed {
  alertID          : String(50);
  severity         : String(20);
  description      : String(500);
  timestamp        : Timestamp;
  supplier         : Association to Suppliers;
}