import { test } from 'node:test'
import assert from 'node:assert/strict'
import cds from '@sap/cds'

test('CAP database and service models compile with the intended public entities and associations', async () => {
  const model = await cds.load(['db', 'srv'])
  const sql = cds.compile.to.sql(model)

  // Assert that core entities, new Suppliers, and RiskAlerts are present in the service model
  for (const name of [
    'AegisService.Shipments',
    'AegisService.InventoryItems',
    'AegisService.DisruptionSignals',
    'AegisService.Recommendations',
    'AegisService.Suppliers',
    'AegisService.RiskAlerts',
    'AegisService.decideRecommendation'
  ]) assert.ok(model.definitions[name], `Expected ${name} in compiled model`)

  // Verify Shipment-to-Supplier and RiskAlert-to-Supplier associations
  assert.ok(model.definitions['aegischain.Shipments'].elements.supplier, 'Expected supplier association on Shipments')
  assert.ok(model.definitions['aegischain.RiskAlerts'].elements.supplier, 'Expected supplier association on RiskAlerts')

  assert.deepEqual(Object.keys(model.definitions['aegischain.RecommendationApprovalStatus'].enum).sort(), 
    ['approved', 'pending', 'rejected'])
})