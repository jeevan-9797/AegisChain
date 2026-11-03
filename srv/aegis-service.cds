using { aegischain as db } from '../db/schema';

service AegisService @(path: '/odata/v4/aegis') {
  @readonly entity Shipments         as projection on db.Shipments;
  @readonly entity InventoryItems    as projection on db.InventoryItems;
           entity DisruptionSignals as projection on db.DisruptionSignals;
           entity Recommendations   as projection on db.Recommendations;
           entity Suppliers         as projection on db.Suppliers;
           entity RiskAlerts        as projection on db.RiskAlerts;

  action decideRecommendation(
    recommendationID : UUID,
    decision         : String enum { approved; rejected; },
    decisionNote     : String(500)
  ) returns {
    recommendationID : UUID;
    decision         : String;
    executionStatus  : String;
  };
}
