using { aegischain as db } from '../db/schema';

service AegisService {
  @readonly entity Shipments as projection on db.Shipments;
  @readonly entity InventoryItems as projection on db.InventoryItems;
  entity DisruptionSignals as projection on db.DisruptionSignals;
  entity Recommendations as projection on db.Recommendations;

  action decideRecommendation(
    recommendationID : UUID,
    decision         : String enum { approved; rejected; },
    decisionNote     : String(500)
  ) returns {
    recommendationID : UUID;
    decision          : String;
    executionStatus   : String;
  };
}
