import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const adapterSource = await readFile(new URL('../app/controltower/webapp/model/BackendAdapter.js', import.meta.url), 'utf8')
const controlTowerView = await readFile(new URL('../app/controltower/webapp/view/ControlTower.view.xml', import.meta.url), 'utf8')
const controlTowerController = await readFile(new URL('../app/controltower/webapp/controller/ControlTower.controller.js', import.meta.url), 'utf8')

function response(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => body
  }
}

function loadAdapter(fetch) {
  let adapter
  const context = {
    fetch,
    window: {
      location: { search: '?mode=live' },
      localStorage: { getItem: () => 'live', setItem: () => {} }
    },
    sap: { ui: { define: (_dependencies, factory) => { adapter = factory() } } }
  }
  vm.runInNewContext(adapterSource, context, { filename: 'BackendAdapter.js' })
  return adapter
}

const signalInput = {
  type: 'Port',
  description: 'Demonstration port delay',
  occurredAt: '2026-11-03T10:00:00Z',
  severity: 'high',
  shipmentImpacts: [{ shipment_ID: 'shipment-uuid' }],
  inventoryImpacts: []
}

const recommendationInput = {
  action: 'Review alternate routing',
  rationale: 'Planner-entered demo fallback',
  tradeoffs: 'Additional freight cost'
}

test('adapter creates a signal with explicit IDs then a linked pending non-executed recommendation', async () => {
  const calls = []
  const createdSignal = { ID: 'signal-uuid', ...signalInput, source: 'demoScenario' }
  const createdRecommendation = {
    ID: 'recommendation-uuid', signal_ID: createdSignal.ID,
    approvalStatus: 'pending', executionStatus: 'notExecuted', source: 'fallback'
  }
  const fetch = async (url, options = {}) => {
    calls.push({ url, options })
    if (options.method === 'HEAD') return response(null)
    if (url.endsWith('/DisruptionSignals')) return response(createdSignal, 201)
    if (url.endsWith('/Recommendations')) return response(createdRecommendation, 201)
    throw new Error('Unexpected request: ' + url)
  }
  const adapter = loadAdapter(fetch)

  const result = await adapter.createIncident(signalInput, recommendationInput)
  const posts = calls.filter(call => call.options.method === 'POST')
  assert.equal(posts.length, 2)
  assert.equal(posts[0].url, '/odata/v4/aegis/DisruptionSignals')
  assert.equal(posts[1].url, '/odata/v4/aegis/Recommendations')
  assert.deepEqual(JSON.parse(posts[0].options.body).shipmentImpacts, signalInput.shipmentImpacts)
  assert.equal(JSON.parse(posts[0].options.body).source, 'demoScenario')

  const recommendationPayload = JSON.parse(posts[1].options.body)
  assert.equal(recommendationPayload.signal_ID, createdSignal.ID)
  assert.equal(recommendationPayload.approvalStatus, 'pending')
  assert.equal(recommendationPayload.executionStatus, 'notExecuted')
  assert.equal(recommendationPayload.source, 'fallback')
  assert.equal(result.recommendation.ID, createdRecommendation.ID)
})

test('adapter rejects creation without explicit shipment or inventory IDs before any request', async () => {
  const calls = []
  const adapter = loadAdapter(async (...args) => {
    calls.push(args)
    return response({})
  })

  await assert.rejects(adapter.createIncident({ ...signalInput, shipmentImpacts: [{}] }, recommendationInput),
    /explicit shipment or inventory impact/)
  assert.equal(calls.length, 0)
})

test('adapter reports a persisted signal ID when recommendation creation fails without retrying', async () => {
  const calls = []
  const createdSignal = { ID: 'signal-persisted-uuid' }
  const fetch = async (url, options = {}) => {
    calls.push({ url, options })
    if (options.method === 'HEAD') return response(null)
    if (url.endsWith('/DisruptionSignals')) return response(createdSignal, 201)
    if (url.endsWith('/Recommendations')) {
      return response({ error: { message: 'Invalid recommendation' } }, 400)
    }
    throw new Error('Unexpected request: ' + url)
  }
  const adapter = loadAdapter(fetch)

  await assert.rejects(adapter.createIncident(signalInput, recommendationInput), error => {
    assert.equal(error.signalID, createdSignal.ID)
    assert.equal(error.signalPersisted, true)
    assert.match(error.message, /signal-persisted-uuid remains persisted in CAP/i)
    assert.match(error.message, /recommendation creation failed: Invalid recommendation/i)
    return true
  })
  assert.equal(calls.filter(call => call.options.method === 'POST').length, 2)
})

test('adapter refresh mapping reflects persisted decisions and decide returns the non-execution result', async () => {
  const signal = {
    ID: 'signal-uuid', type: 'Port', description: 'Demonstration port delay', severity: 'high',
    occurredAt: '2026-11-03T10:00:00Z', source: 'demoScenario', createdAt: '2026-11-03T10:00:00Z',
    createdBy: 'demo', shipmentImpacts: [{ shipment_ID: 'shipment-uuid', shipment: { shipmentNumber: 'S-1', status: 'In Transit' } }],
    inventoryImpacts: [], recommendations: [{
      ID: 'recommendation-uuid', action: 'Review alternate routing', rationale: 'Planner-entered demo fallback',
      source: 'fallback', approvalStatus: 'pending', executionStatus: 'notExecuted'
    }]
  }
  let decisionPayload
  const fetch = async (url, options = {}) => {
    if (options.method === 'HEAD') return response(null)
    if (url.includes('DisruptionSignals?')) return response({ value: [signal] })
    if (url.endsWith('/decideRecommendation')) {
      decisionPayload = JSON.parse(options.body)
      signal.recommendations[0].approvalStatus = decisionPayload.decision
      signal.recommendations[0].decidedBy = 'demo-user'
      signal.recommendations[0].decidedAt = '2026-11-03T10:01:00Z'
      signal.recommendations[0].decisionNote = decisionPayload.decisionNote
      return response({ ...decisionPayload, executionStatus: 'notExecuted' })
    }
    throw new Error('Unexpected request: ' + url)
  }
  const adapter = loadAdapter(fetch)
  const mockData = { Incidents: [], Signals: [], AuditLog: [], Actions: [], Kpis: {}, Notifications: [] }

  const before = await adapter.loadLive(mockData)
  assert.equal(before.Incidents[0].options[0].approvalStatus, 'pending')
  assert.equal(before.Incidents[0].options[0].executionStatus, 'notExecuted')

  const decision = await adapter.decide('recommendation-uuid', 'approved', 'Reviewed')
  assert.equal(decision.executionStatus, 'notExecuted')
  assert.equal(decisionPayload.recommendationID, 'recommendation-uuid')
  const after = await adapter.loadLive(mockData)
  assert.equal(after.Incidents[0].options[0].approvalStatus, 'approved')
  assert.equal(after.Incidents[0].status, 'Approved - decision recorded, not executed')
})

test('adapter posts the ML protocol and only forwards explicitly selected CAP impact IDs', async () => {
  const calls = []
  const payload = {
    feed_items: [{ id: 'UI-1', text: 'Port of Rotterdam congestion' }],
    cargo_value: 450000,
    incident_id: 'SAP-8842',
    shipmentIDs: ['shipment-uuid'],
    inventoryItemIDs: ['inventory-uuid']
  }
  const adapter = loadAdapter(async (url, options = {}) => {
    calls.push({ url, options })
    if (options.method === 'HEAD') return response(null)
    return response({
      signalID: 'signal-uuid', recommendationID: 'recommendation-uuid',
      category: 'Port', severity: 'medium', scenarioKey: 'OPTION_C_SPLIT',
      approvalStatus: 'pending', executionStatus: 'notExecuted'
    })
  })

  const result = await adapter.evaluateIncident(payload)
  const post = calls.find(call => call.options.method === 'POST')
  assert.equal(post.url, '/odata/v4/aegis/evaluateIncident')
  assert.deepEqual(JSON.parse(post.options.body), {
    schemaVersion: 1,
    feed_items: payload.feed_items,
    cargo_value: payload.cargo_value,
    incident_id: payload.incident_id,
    shipmentIDs: payload.shipmentIDs,
    inventoryItemIDs: payload.inventoryItemIDs
  })
  assert.equal(result.executionStatus, 'notExecuted')
})

test('adapter prevents ML requests without a feed or explicit impact IDs', async () => {
  let requestCount = 0
  const adapter = loadAdapter(async () => { requestCount++; return response({}) })
  const base = {
    feed_items: [{ id: 'UI-1', text: 'Port disruption' }], cargo_value: 450000,
    incident_id: 'SAP-8842', shipmentIDs: [], inventoryItemIDs: []
  }

  await assert.rejects(adapter.evaluateIncident({ ...base, feed_items: [] }), /at least one disruption feed item/)
  await assert.rejects(adapter.evaluateIncident(base), /at least one shipment or inventory impact explicitly/)
  await assert.rejects(adapter.evaluateIncident({ ...base, shipmentIDs: [{}] }), /explicit CAP IDs/)
  assert.equal(requestCount, 0)
})

test('adapter preserves actionable CAP 400 and 422 messages for the UI', async () => {
  for (const [status, message] of [
    [400, 'feed_items must contain at least one feed item'],
    [422, 'ML returned only OTHER or unsupported disruption categories; no CAP records were created'],
    [422, 'ML found multiple active disruptions; evaluate one incident at a time; no CAP records were created']
  ]) {
    const adapter = loadAdapter(async (url, options = {}) => {
      if (options.method === 'HEAD') return response(null)
      return response({ error: { message } }, status)
    })
    await assert.rejects(adapter.evaluateIncident({
      feed_items: [{ id: 'UI-1', text: 'Test alert' }], cargo_value: 450000,
      incident_id: 'SAP-8842', shipmentIDs: ['shipment-uuid'], inventoryItemIDs: []
    }), error => {
      assert.equal(error.status, status)
      assert.equal(error.message, message)
      return true
    })
  }
})

test('ML action is live-only and its controller handler guards against mock-mode invocation', () => {
  assert.match(controlTowerView,
    /Button text="Evaluate incident with ML" press="\.onEvaluateIncidentWithML"\s+visible="\{= \$\{\/Meta\/mode\} === 'live' \}"/)
  assert.match(controlTowerController,
    /onEvaluateIncidentWithML: function \(\) \{\s*if \(!this\._isLive\(\)\) \{ return; \}/)
  assert.match(controlTowerController, /OTHER or an unsupported category\. No signal or recommendation was created/)
  assert.match(controlTowerController, /multiple active disruptions\. Evaluate one incident at a time; no records were created/)
  assert.match(controlTowerController, /no active moderate-or-higher disruption\. No records were created/)
  assert.match(controlTowerController, /nonempty disruption feed item\. No records were created/)
})
