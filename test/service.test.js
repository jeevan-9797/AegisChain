import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'

const port = 43100 + Math.floor(Math.random() * 1000)
const base = `http://127.0.0.1:${port}/odata/v4/aegis`
let server

async function request(path, method = 'GET', body) {
  const response = await fetch(`${base}/${path}`, {
    method,
    headers: body ? { 'content-type': 'application/json' } : {},
    body: body && JSON.stringify(body)
  })
  const json = await response.json()
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
      const response = await fetch(`${base}/Shipments`)
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

test('creates recommendations and allows one approval or rejection without execution', async () => {
  const signals = await request('DisruptionSignals?$expand=shipmentImpacts')
  const signalID = signals.json.value.find(signal => signal.shipmentImpacts?.length)?.ID
  assert.ok(signalID)

  for (const decision of ['approved', 'rejected']) {
    const created = await request('Recommendations', 'POST', {
      signal_ID: signalID, action: 'Review alternate routing', rationale: 'Demo rationale',
      source: 'fallback'
    })
    assert.equal(created.response.status, 201, JSON.stringify(created.json))
    assert.equal(created.json.approvalStatus, 'pending')

    const forcedDecision = await request('Recommendations', 'POST', {
      signal_ID: signalID, action: 'Unreviewed action', rationale: 'Test', source: 'fallback',
      approvalStatus: 'approved'
    })
    assert.equal(forcedDecision.response.status, 400)
    assert.match(forcedDecision.json.error.message, /must start as pending/i)

    const decided = await request('decideRecommendation', 'POST', {
      recommendationID: created.json.ID, decision, decisionNote: 'Reviewed in test'
    })
    assert.equal(decided.response.status, 200, JSON.stringify(decided.json))
    assert.equal(decided.json.executionStatus, 'notExecuted')

    const repeated = await request('decideRecommendation', 'POST', {
      recommendationID: created.json.ID, decision, decisionNote: 'Repeated'
    })
    assert.equal(repeated.response.status, 409)

    const update = await request(`Recommendations(${created.json.ID})`, 'PATCH', { action: 'change' })
    assert.equal(update.response.status, 405)
  }
})
