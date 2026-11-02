namespace aegischain;

using { cuid, managed } from '@sap/cds/common';

type RecommendationSource : String enum {
  ai;
  fallback;
}

type RecommendationApprovalStatus : String enum {
  pending;
  approved;
  rejected;
}

/** Mock S/4HANA operational data for the local demonstration. */
entity Shipments : cuid, managed {
  shipmentNumber : String(40) not null;
  origin         : String(120) not null;
  destination    : String(120) not null;
  currentLocation: String(120);
  status         : String(30) not null;
  expectedArrival: Timestamp;
  dataSource     : String(30) not null default 'mockS4HANA';
}

/** Mock S/4HANA inventory snapshot for the local demonstration. */
entity InventoryItems : cuid, managed {
  materialNumber : String(40) not null;
  description    : String(160) not null;
  location       : String(120) not null;
  quantity       : Decimal(15, 3) not null;
  unitOfMeasure  : String(12) not null;
  dataSource     : String(30) not null default 'mockS4HANA';
}

/** A disruption signal recorded for assessment. */
entity DisruptionSignals : cuid, managed {
  type           : String(80) not null;
  description    : String(500) not null;
  occurredAt     : Timestamp not null;
  severity       : String(30) not null;
  source         : String(40) not null;
  shipmentImpacts: Composition of many ShipmentImpacts
                     on shipmentImpacts.signal = $self;
  inventoryImpacts: Composition of many InventoryImpacts
                      on inventoryImpacts.signal = $self;
  recommendations: Composition of many Recommendations
                     on recommendations.signal = $self;
}

/** Explicit link between a disruption signal and an affected shipment. */
entity ShipmentImpacts {
  key signal   : Association to DisruptionSignals;
  key shipment : Association to Shipments;
}

/** Explicit link between a disruption signal and affected inventory. */
entity InventoryImpacts {
  key signal        : Association to DisruptionSignals;
  key inventoryItem : Association to InventoryItems;
}

/** Advisory recovery proposal and its human approval decision. */
entity Recommendations : cuid, managed {
  signal         : Association to DisruptionSignals not null;
  action         : String(500) not null;
  rationale      : LargeString not null;
  tradeoffs      : LargeString;
  source         : RecommendationSource not null;
  approvalStatus : RecommendationApprovalStatus not null default #pending;
  decidedBy      : String(120);
  decidedAt      : Timestamp;
  decisionNote   : String(500);
}
