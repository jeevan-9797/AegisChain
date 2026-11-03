using { aegischain.db as db } from '../db/schema';

service AegisService @(path: '/odata/v4/aegischain') {
  entity Shipments         as projection on db.Shipments;
  entity DisruptionSignals as projection on db.DisruptionSignals;
  entity Suppliers         as projection on db.Suppliers;
  entity RiskAlerts        as projection on db.RiskAlerts;
}