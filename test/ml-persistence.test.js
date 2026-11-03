import { test } from 'node:test'
import assert from 'node:assert/strict'
import cds from '@sap/cds'
import { createMlRemoteEvaluator } from '../srv/ml-evaluator.js'
import { createMlIncidentHandler } from '../srv/ml-workflow.js'

const evaluatorToken = 'test-only-evaluator-token-0123456789abcdef'

test('remote ML output persists explicit links and a pending non-executed recommendation in SQLite', async () => {
  cds.env.requires.db = { kind: 'sqlite', credentials: { url: ':memory:' } }
  const model = await cds.load(['db', 'srv'])
  const database = await cds.connect.to('db')
  try {
    await cds.deploy(model).to(database)
    const shipment = await database.run(cds.ql.SELECT.one.from('aegischain.Shipments'))
    const inventory = await database.run(cds.ql.SELECT.one.from('aegischain.InventoryItems'))
    assert.ok(shipment?.ID)
    assert.ok(inventory?.ID)

    const evaluatorResult = {
      classified_signals: [{ title: 'Port of Rotterdam congestion', category: 'PORT', severity: 2 }],
      decision_optimization: {
        recommended_scenario_key: 'OPTION_C_SPLIT',
        recommended_name: 'Sea-Air Hybrid',
        recommended_mode: 'Multimodal',
        recommendation_rationale: 'Protect the cold-chain.'
      },
      scenarios: { OPTION_C_SPLIT: { net_economic_impact_usd: 51415 } }
    }
    const remoteEvaluator = createMlRemoteEvaluator({
      url: 'https://python.internal/internal/v1/evaluate',
      authToken: evaluatorToken,
      fetchImpl: async (_url, options) => {
        const sent = JSON.parse(options.body)
        assert.deepEqual(Object.keys(sent).sort(), ['cargo_value', 'feed_items', 'incident_id', 'schemaVersion'])
        assert.equal(sent.schemaVersion, 1)
        return { ok: true, status: 200, text: async () => JSON.stringify(evaluatorResult) }
      }
    })
    const entities = {
      Shipments: 'aegischain.Shipments',
      InventoryItems: 'aegischain.InventoryItems',
      DisruptionSignals: 'AegisService.DisruptionSignals'
    }
    const handler = createMlIncidentHandler({
      evaluate: remoteEvaluator,
      txForRequest: () => database,
      entities,
      now: () => new Date('2026-11-03T10:00:00.000Z')
    })
    const request = {
      data: {
        schemaVersion: 1,
        feed_items: [{ id: 'PERSIST-1', text: 'Rotterdam port congestion' }],
        cargo_value: 450000,
        incident_id: 'SAP-8842',
        shipmentIDs: [shipment.ID],
        inventoryItemIDs: [inventory.ID]
      },
      reject(status, message) { throw Object.assign(new Error(message), { status }) }
    }

    const created = await handler(request)
    const signal = await database.run(cds.ql.SELECT.one.from('aegischain.DisruptionSignals').where({ ID: created.signalID }))
    const shipmentImpact = await database.run(cds.ql.SELECT.one.from('aegischain.ShipmentImpacts').where({ signal_ID: created.signalID }))
    const inventoryImpact = await database.run(cds.ql.SELECT.one.from('aegischain.InventoryImpacts').where({ signal_ID: created.signalID }))
    const recommendation = await database.run(cds.ql.SELECT.one.from('aegischain.Recommendations').where({ ID: created.recommendationID }))

    assert.equal(signal.source, 'mlEvaluation')
    assert.equal(signal.type, 'Port')
    assert.equal(shipmentImpact.shipment_ID, shipment.ID)
    assert.equal(inventoryImpact.inventoryItem_ID, inventory.ID)
    assert.equal(recommendation.signal_ID, signal.ID)
    assert.equal(recommendation.approvalStatus, 'pending')
    assert.equal(recommendation.executionStatus, 'notExecuted')
    assert.equal(recommendation.decidedAt, null)

    const beforeSignals = await database.run(cds.ql.SELECT.from('aegischain.DisruptionSignals'))
    const beforeRecommendations = await database.run(cds.ql.SELECT.from('aegischain.Recommendations'))
    for (const status of [401, 403, 503]) {
      const failedEvaluator = createMlRemoteEvaluator({
        url: 'https://python.internal/internal/v1/evaluate',
        authToken: evaluatorToken,
        fetchImpl: async () => ({ ok: false, status, text: async () => 'rejected' })
      })
      const failureHandler = createMlIncidentHandler({
        evaluate: failedEvaluator,
        txForRequest: () => database,
        entities
      })
      await assert.rejects(failureHandler(request), error => error.status === 502)
      assert.equal((await database.run(cds.ql.SELECT.from('aegischain.DisruptionSignals'))).length, beforeSignals.length)
      assert.equal((await database.run(cds.ql.SELECT.from('aegischain.Recommendations'))).length, beforeRecommendations.length)
    }
  } finally {
    await database.disconnect()
  }
})
