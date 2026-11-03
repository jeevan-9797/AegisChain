using { aegischain.db as my } from '../db/schema';

service AegisChainService @(path: '/odata/v4/aegischain') {
    entity Suppliers as projection on my.Suppliers;
    entity Shipments as projection on my.Shipments;
    entity RiskAlerts as projection on my.RiskAlerts;
}