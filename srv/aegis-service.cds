using { aegischain as db } from '../db/schema';

type MlFeedItem : {
  id        : String(120);
  signal_id : String(120);
  text      : LargeString;
  title     : String(500);
  headline  : String(500);
  content   : LargeString;
};

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

  action evaluateIncident(
    schemaVersion    : Integer,
    feed_items       : array of MlFeedItem,
    cargo_value      : Decimal(15,2),
    incident_id      : String(120),
    shipmentIDs      : array of UUID,
    inventoryItemIDs : array of UUID
  ) returns {
    signalID          : UUID;
    recommendationID  : UUID;
    category          : String(30);
    severity          : String(30);
    scenarioKey       : String(80);
    approvalStatus    : String(30);
    executionStatus   : String(30);
  };
}
