import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'

const port = 43100 + Math.floor(Math.random() * 1000)
const base = `http://127.0.0.1:${port}/odata/v4/aegis`
let server

function authHeader(user) {
  return user ? `Basic ${Buffer.from(`${user}:`).toString('base64')}` : undefined
}

async function request(path, method = 'GET', body, user = 'approver') {
  const headers = {}
  if (body) headers['content-type'] = 'application/json'
  const auth = authHeader(user)
  if (auth) headers['authorization'] = auth
  const response = await fetch(`${base}/${path}`, {
    method,
    headers,
    body: body && JSON.stringify(body)
  })
  let json
  try { json = await response.json() } catch { json = null }
  return { response, json }
}

before(async () => {
  server = spawn(process.execPath, ['node_modules/@sap/cds/bin/serve.js'], {
    cwd: process.cwd(),
    env: { ...process.env, PORT: String(port) },
    stdio: 'ignore'
  })
  for (let i = 0; i < 50; i++) {
    if (server.exitCode !== null) throw new Error(`CAP server exited with ${server.exitCode}`)
    try {
      const response = await fetch(`${base}/Shipments`, {
        headers: { authorization: `Basic ${Buffer.from('approver:').toString('base64')}` }
      })
      if (response.ok) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  throw new Error('CAP server did not become ready')
})

after(() => server?.kill())

test('reads seeded shipments and inventory', async () => {
  const shipments = await request('Shipments')
  const inventory = await request('InventoryItems')
  assert.equal(shipments.response.status, 200)
  assert.equal(shipments.json.value.length, 2)
  assert.equal(inventory.response.status, 200)
  assert.equal(inventory.json.value.length, 2)
})

test('creates a signal with impacts and rejects a signal without impacts', async () => {
  const bad = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Port closure', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario'
  })
  assert.equal(bad.response.status, 400)
  assert.match(bad.json.error.message, /at least one shipment or inventory item/i)

  const missingImpactID = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Missing impact ID', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario', shipmentImpacts: [{}]
  })
  assert.equal(missingImpactID.response.status, 400)
  assert.match(missingImpactID.json.error.message, /explicit shipment_ID|existing shipment/i)

  const unknownImpactID = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Unknown shipment', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario',
    shipmentImpacts: [{ shipment_ID: '99999999-9999-4999-8999-999999999999' }]
  })
  assert.equal(unknownImpactID.response.status, 400)
  assert.match(unknownImpactID.json.error.message, /existing shipment/i)

  const unknownInventoryID = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Unknown inventory', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario',
    inventoryImpacts: [{ inventoryItem_ID: '99999999-9999-4999-8999-999999999999' }]
  })
  assert.equal(unknownInventoryID.response.status, 400)
  assert.match(unknownInventoryID.json.error.message, /existing inventory item/i)

  const wrongSource = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Port closure', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'externalFeed',
    shipmentImpacts: [{ shipment_ID: '11111111-1111-4111-8111-111111111111' }]
  })
  assert.equal(wrongSource.response.status, 400)
  assert.match(wrongSource.json.error.message, /source must be 'demoScenario'/i)

  const created = await request('DisruptionSignals', 'POST', {
    type: 'portDelay', description: 'Port closure', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario',
    shipmentImpacts: [{ shipment_ID: '11111111-1111-4111-8111-111111111111' }],
    inventoryImpacts: [{ inventoryItem_ID: '33333333-3333-4333-8333-333333333333' }]
  })
  assert.equal(created.response.status, 201, JSON.stringify(created.json))
  assert.equal(created.json.shipmentImpacts.length, 1)
  assert.equal(created.json.inventoryImpacts.length, 1)
  return created.json.ID
})

test('rejects blank required signal fields and duplicate shipment or inventory impacts', async () => {
  const required = {
    type: 'portDelay', description: 'Port closure', occurredAt: '2026-11-02T10:00:00Z',
    severity: 'high', source: 'demoScenario',
    shipmentImpacts: [{ shipment_ID: '11111111-1111-4111-8111-111111111111' }]
  }
  for (const field of ['type', 'description', 'occurredAt', 'severity', 'source']) {
    const payload = { ...required, [field]: '  \t ' }
    const result = await request('DisruptionSignals', 'POST', payload)
    assert.equal(result.response.status, 400, `Expected blank ${field} to be rejected`)
    const expectedError = field === 'occurredAt'
      ? /occurredAt.*nonblank|not a valid Timestamp/i
      : new RegExp(field + '.*nonblank', 'i')
    assert.match(result.json.error.message, expectedError)
  }

  const duplicateShipment = await request('DisruptionSignals', 'POST', {
    ...required,
    shipmentImpacts: [
      { shipment_ID: '11111111-1111-4111-8111-111111111111' },
      { shipment_ID: '11111111-1111-4111-8111-111111111111' }
    ]
  })
  assert.equal(duplicateShipment.response.status, 400)
  assert.match(duplicateShipment.json.error.message, /duplicate shipment impact IDs/i)

  const duplicateInventory = await request('DisruptionSignals', 'POST', {
    ...required,
    shipmentImpacts: [],
    inventoryImpacts: [
      { inventoryItem_ID: '33333333-3333-4333-8333-333333333333' },
      { inventoryItem_ID: '33333333-3333-4333-8333-333333333333' }
    ]
  })
  assert.equal(duplicateInventory.response.status, 400)
  assert.match(duplicateInventory.json.error.message, /duplicate inventory item impact IDs/i)
})

test('creates recommendations and allows one approval or rejection without execution', async () => {
  const signals = await request('DisruptionSignals?$expand=shipmentImpacts')
  const signalID = signals.json.value.find(signal => signal.shipmentImpacts?.length)?.ID
  assert.ok(signalID)

  for (const field of ['signal_ID', 'action', 'rationale', 'source']) {
    const payload = {
      signal_ID: signalID, action: 'Review alternate routing', rationale: 'Demo rationale', source: 'fallback'
    }
    payload[field] = '  \t '
    const result = await request('Recommendations', 'POST', payload)
    assert.equal(result.response.status, 400, `Expected blank ${field} to be rejected`)
    assert.match(result.json.error.message, new RegExp(field + '.*nonblank', 'i'))
  }

  const unknownSignal = await request('Recommendations', 'POST', {
    signal_ID: '99999999-9999-4999-8999-999999999999', action: 'Review alternate routing',
    rationale: 'Demo rationale', source: 'fallback'
  })
  assert.equal(unknownSignal.response.status, 400)
  assert.match(unknownSignal.json.error.message, /signal_ID.*existing signal/i)

  for (const decision of ['approved', 'rejected']) {
    const created = await request('Recommendations', 'POST', {
      signal_ID: signalID, action: 'Review alternate routing', rationale: 'Demo rationale',
      source: 'fallback'
    })
    assert.equal(created.response.status, 201, JSON.stringify(created.json))
    assert.equal(created.json.approvalStatus, 'pending')
    assert.equal(created.json.executionStatus, 'notExecuted')
    assert.equal(created.json.signal_ID, signalID)

    const persistedBeforeDecision = await request(`Recommendations(${created.json.ID})`)
    assert.equal(persistedBeforeDecision.response.status, 200)
    assert.equal(persistedBeforeDecision.json.executionStatus, 'notExecuted')
    assert.equal(persistedBeforeDecision.json.signal_ID, signalID)

    const forcedDecision = await request('Recommendations', 'POST', {
      signal_ID: signalID, action: 'Unreviewed action', rationale: 'Test', source: 'fallback',
      approvalStatus: 'approved'
    })
    assert.equal(forcedDecision.response.status, 400)
    assert.match(forcedDecision.json.error.message, /must start as pending/i)

    const forcedExecution = await request('Recommendations', 'POST', {
      signal_ID: signalID, action: 'Unsafe execution state', rationale: 'Test', source: 'fallback',
      executionStatus: 'executed'
    })
    assert.equal(forcedExecution.response.status, 400)
    assert.match(forcedExecution.json.error.message, /executionStatus notExecuted/i)

    const decided = await request('decideRecommendation', 'POST', {
      recommendationID: created.json.ID, decision, decisionNote: 'Reviewed in test'
    })
    assert.equal(decided.response.status, 200, JSON.stringify(decided.json))
    assert.equal(decided.json.executionStatus, 'notExecuted')

    const persistedDecision = await request(`Recommendations(${created.json.ID})`)
    assert.equal(persistedDecision.response.status, 200)
    assert.equal(persistedDecision.json.approvalStatus, decision)
    assert.equal(persistedDecision.json.executionStatus, 'notExecuted')
    assert.ok(persistedDecision.json.decidedAt)

    const repeated = await request('decideRecommendation', 'POST', {
      recommendationID: created.json.ID, decision, decisionNote: 'Repeated'
    })
    assert.equal(repeated.response.status, 409)

    const update = await request(`Recommendations(${created.json.ID})`, 'PATCH', { action: 'change' })
    assert.equal(update.response.status, 405)
  }
})


test('restricts decideRecommendation to Approver: viewer returns 403, approver returns 200', async () => {
  const signals = await request('DisruptionSignals?$expand=shipmentImpacts')
  const signalID = signals.json.value.find(signal => signal.shipmentImpacts?.length)?.ID
  assert.ok(signalID)

  const created = await request('Recommendations', 'POST', {
    signal_ID: signalID, action: 'Route verification for auth test', rationale: 'Auth scope test',
    source: 'fallback'
  })
  assert.equal(created.response.status, 201)

  // Viewer without Approver role -> 403 Forbidden
  const forbidden = await request('decideRecommendation', 'POST', {
    recommendationID: created.json.ID, decision: 'approved', decisionNote: 'Should fail'
  }, 'viewer')
  assert.equal(forbidden.response.status, 403)

  // Approver with Approver role -> 200 OK
  const allowed = await request('decideRecommendation', 'POST', {
    recommendationID: created.json.ID, decision: 'approved', decisionNote: 'Approved by authorized user'
  }, 'approver')
  assert.equal(allowed.response.status, 200)
  assert.equal(allowed.json.decision, 'approved')
})
test('evaluateIncident rejects empty feeds and unknown explicit IDs before starting ML', async () => {
  const emptyFeed = await request('evaluateIncident', 'POST', {
    schemaVersion: 1, feed_items: [], cargo_value: 450000, incident_id: 'SAP-8842',
    shipmentIDs: ['11111111-1111-4111-8111-111111111111'], inventoryItemIDs: []
  })
  assert.equal(emptyFeed.response.status, 400)
  assert.match(emptyFeed.json.error.message, /at least one feed item/i)

  const unknownShipment = await request('evaluateIncident', 'POST', {
    schemaVersion: 1, feed_items: [{ id: 'TEST-1', text: 'Port disruption' }],
    cargo_value: 450000, incident_id: 'SAP-8842',
    shipmentIDs: ['99999999-9999-4999-8999-999999999999'], inventoryItemIDs: []
  })
  assert.equal(unknownShipment.response.status, 400)
  assert.match(unknownShipment.json.error.message, /unknown shipment ID/i)
})

test('evaluateIncident persists a linked pending recommendation and decisions remain non-executing', {
  skip: !process.env.AEGISCHAIN_PYTHON && 'Set AEGISCHAIN_PYTHON to run the real Python/CAP integration test'
}, async () => {
  const shipments = await request('Shipments')
  const shipmentID = shipments.json.value[0]?.ID
  assert.ok(shipmentID, 'expected a seeded shipment')

  const created = await request('evaluateIncident', 'POST', {
    schemaVersion: 1,
    feed_items: [{ id: 'ML-HTTP-1', text: 'Houthi missile strikes close the Bab el-Mandeb route.' }],
    cargo_value: 450000,
    incident_id: 'SAP-8842',
    shipmentIDs: [shipmentID],
    inventoryItemIDs: []
  })
  assert.equal(created.response.status, 200, JSON.stringify(created.json))
  assert.equal(created.json.category, 'Chokepoint')
  assert.equal(created.json.severity, 'critical')
  assert.equal(created.json.approvalStatus, 'pending')
  assert.equal(created.json.executionStatus, 'notExecuted')

  const signal = await request(`DisruptionSignals(${created.json.signalID})?$expand=shipmentImpacts,recommendations`)
  assert.equal(signal.response.status, 200)
  assert.equal(signal.json.source, 'mlEvaluation')
  assert.equal(signal.json.shipmentImpacts[0].shipment_ID, shipmentID)
  assert.equal(signal.json.recommendations[0].ID, created.json.recommendationID)
  assert.equal(signal.json.recommendations[0].signal_ID, created.json.signalID)
  assert.equal(signal.json.recommendations[0].approvalStatus, 'pending')
  assert.equal(signal.json.recommendations[0].executionStatus, 'notExecuted')
  assert.equal(signal.json.recommendations[0].source, 'fallback')

  const decision = await request('decideRecommendation', 'POST', {
    recommendationID: created.json.recommendationID, decision: 'approved'
  })
  assert.equal(decision.response.status, 200)
  assert.equal(decision.json.executionStatus, 'notExecuted')
  const persisted = await request(`Recommendations(${created.json.recommendationID})`)
  assert.equal(persisted.json.approvalStatus, 'approved')
  assert.equal(persisted.json.executionStatus, 'notExecuted')
})
