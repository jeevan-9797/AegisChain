import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMlCliEvaluator, createMlEvaluator, createMlRemoteEvaluator, MlCliError } from '../srv/ml-evaluator.js'
import { createMlIncidentHandler, mapMlEvaluation, MlWorkflowError } from '../srv/ml-workflow.js'

const shipmentID = '11111111-1111-4111-8111-111111111111'
const inventoryItemID = '33333333-3333-4333-8333-333333333333'
const evaluatorToken = 'test-only-evaluator-token-0123456789abcdef'
const entities = {
  Shipments: { name: 'aegischain.Shipments' },
  InventoryItems: { name: 'aegischain.InventoryItems' },
  DisruptionSignals: { name: 'aegischain.DisruptionSignals' }
}

function resultFor(category = 'PORT', severity = 2) {
  return {
    classified_signals: [{
      signal_id: 'FEED-1', title: 'Port of Rotterdam congestion', summary: 'A port disruption', category, severity,
      impacted_lanes: ['ASIA_EUROPE']
    }],
    scenarios: {
      OPTION_C_SPLIT: {
        description: 'Sea-Air route via Jebel Ali', net_economic_impact_usd: 51415,
        extra_delay_days: 2.4, spoilage_risk_pct: 2.9, extra_freight_usd: 38500
      }
    },
    decision_optimization: {
      recommended_scenario_key: 'OPTION_C_SPLIT',
      recommended_name: 'Sea-Air Multimodal Hybrid',
      recommended_mode: 'Multimodal Sea-Air Hybrid',
      recommendation_rationale: 'This scenario minimizes modeled economic impact.'
    }
  }
}

function makeRequest(overrides = {}) {
  return {
    schemaVersion: 1,
    feed_items: [{ id: 'FEED-1', text: 'Port of Rotterdam congestion delays container vessels.' }],
    cargo_value: 450000,
    incident_id: 'SAP-8842',
    shipmentIDs: [shipmentID],
    inventoryItemIDs: [inventoryItemID],
    ...overrides
  }
}

function makeHarness({ evaluation = resultFor(), evaluate, existingShipments = [shipmentID], existingInventory = [inventoryItemID] } = {}) {
  const calls = []
  const evaluateRequests = []
  const tx = {
    async run(query) {
      calls.push(query)
      if (query.SELECT) {
        const entity = query.SELECT.from.ref[0]
        const ids = query.SELECT.where.find(token => token?.list)?.list.map(token => token.val) ?? []
        const rows = entity.endsWith('Shipments') ? existingShipments : existingInventory
        return rows.filter(id => ids.includes(id)).map(ID => ({ ID }))
      }
      return undefined
    }
  }
  const handler = createMlIncidentHandler({
    evaluate: async request => {
      evaluateRequests.push(request)
      return evaluate ? evaluate(request) : evaluation
    },
    txForRequest: () => tx,
    entities,
    now: () => new Date('2026-11-03T10:00:00.000Z')
  })
  const request = data => ({
    data,
    reject(status, message) {
      throw new MlWorkflowError(status, message)
    }
  })
  return { handler, request, calls, evaluateRequests }
}

test('maps evaluator category, severity, scenario, explicit impacts and pending state into one CAP deep insert', async () => {
  const h = makeHarness()
  const response = await h.handler(h.request(makeRequest()))
  const insert = h.calls.find(call => call.INSERT)?.INSERT
  assert.ok(insert, 'expected a CAP insert')
  const [signal] = insert.entries
  assert.equal(signal.ID, response.signalID)
  assert.equal(signal.type, 'Port')
  assert.equal(signal.severity, 'medium')
  assert.equal(signal.source, 'mlEvaluation')
  assert.equal(signal.description, 'Port of Rotterdam congestion')
  assert.equal(signal.occurredAt, '2026-11-03T10:00:00.000Z')
  assert.deepEqual(signal.shipmentImpacts, [{ signal_ID: signal.ID, shipment_ID: shipmentID }])
  assert.deepEqual(signal.inventoryImpacts, [{ signal_ID: signal.ID, inventoryItem_ID: inventoryItemID }])
  assert.equal(signal.recommendations[0].ID, response.recommendationID)
  assert.equal(signal.recommendations[0].signal_ID, signal.ID)
  assert.match(signal.recommendations[0].action, /Sea-Air Multimodal Hybrid.*OPTION_C_SPLIT/)
  assert.equal(signal.recommendations[0].rationale, 'This scenario minimizes modeled economic impact.')
  assert.equal(signal.recommendations[0].source, 'fallback')
  assert.equal(signal.recommendations[0].approvalStatus, 'pending')
  assert.equal(signal.recommendations[0].executionStatus, 'notExecuted')
  assert.equal(signal.recommendations[0].decidedAt, null)
  assert.deepEqual(response, {
    signalID: signal.ID,
    recommendationID: signal.recommendations[0].ID,
    category: 'Port',
    severity: 'medium',
    scenarioKey: 'OPTION_C_SPLIT',
    approvalStatus: 'pending',
    executionStatus: 'notExecuted'
  })
  assert.deepEqual(h.evaluateRequests[0], {
    schemaVersion: 1,
    feed_items: makeRequest().feed_items,
    cargo_value: 450000,
    incident_id: 'SAP-8842'
  })
  assert.equal(h.evaluateRequests[0].shipmentIDs, undefined)
  assert.equal(h.evaluateRequests[0].inventoryItemIDs, undefined)
})

test('normalizes supported evaluator category and severity values to the UI vocabulary', () => {
  const expected = [
    ['CHOKEPOINT', 3, 'Chokepoint', 'critical'],
    ['PORT', 2, 'Port', 'medium'],
    ['TARIFF', 2, 'Tariff', 'medium'],
    ['WEATHER', 3, 'Weather', 'critical']
  ]
  for (const [category, severity, type, label] of expected) {
    const mapped = mapMlEvaluation(resultFor(category, severity), '2026-11-03T10:00:00.000Z')
    assert.equal(mapped.signal.type, type)
    assert.equal(mapped.signal.severity, label)
  }
})

test('rejects unknown explicit impact IDs before invoking ML or inserting records', async () => {
  const h = makeHarness({ existingShipments: [] })
  await assert.rejects(h.handler(h.request(makeRequest())), error => {
    assert.equal(error.status, 400)
    assert.match(error.message, /unknown shipment ID/)
    return true
  })
  assert.equal(h.evaluateRequests.length, 0)
  assert.equal(h.calls.some(call => call.INSERT), false)
})

test('rejects case-insensitive duplicate impact IDs before invoking ML', async () => {
  const h = makeHarness()
  const request = makeRequest({ shipmentIDs: [shipmentID, shipmentID.toUpperCase()] })
  await assert.rejects(h.handler(h.request(request)), error => {
    assert.equal(error.status, 400)
    assert.match(error.message, /shipmentIDs.*duplicate IDs/i)
    return true
  })
  assert.equal(h.evaluateRequests.length, 0)
  assert.equal(h.calls.some(call => call.INSERT), false)
})

test('rejects empty feed without invoking ML or creating CAP records', async () => {
  const h = makeHarness()
  await assert.rejects(h.handler(h.request(makeRequest({ feed_items: [] }))), error => {
    assert.equal(error.status, 400)
    assert.match(error.message, /at least one feed item/)
    return true
  })
  assert.equal(h.evaluateRequests.length, 0)
  assert.equal(h.calls.some(call => call.INSERT), false)
})

test('rejects OTHER or unsupported categories instead of creating a misleading recommendation', async () => {
  for (const category of ['OTHER', 'UNRECOGNIZED']) {
    const h = makeHarness({ evaluation: resultFor(category, 3) })
    await assert.rejects(h.handler(h.request(makeRequest())), error => {
      assert.equal(error.status, 422)
      assert.match(error.message, /OTHER or unsupported/)
      return true
    })
    assert.equal(h.calls.some(call => call.INSERT), false)
  }
})

test('ignores OTHER classifications when one supported active disruption is present', async () => {
  const evaluation = resultFor()
  evaluation.classified_signals.unshift({ title: 'Sports result', category: 'OTHER', severity: 1 })
  const h = makeHarness({ evaluation })
  const response = await h.handler(h.request(makeRequest()))
  const signal = h.calls.find(call => call.INSERT).INSERT.entries[0]
  assert.equal(response.category, 'Port')
  assert.equal(signal.type, 'Port')
  assert.equal(signal.description, 'Port of Rotterdam congestion')
})

test('rejects multiple active signals instead of attaching one scenario to an ambiguous incident', async () => {
  const evaluation = resultFor()
  evaluation.classified_signals.push({ title: 'Cyclone warning', category: 'WEATHER', severity: 3 })
  const h = makeHarness({ evaluation })
  await assert.rejects(h.handler(h.request(makeRequest())), error => {
    assert.equal(error.status, 422)
    assert.match(error.message, /multiple active disruptions/)
    return true
  })
  assert.equal(h.calls.some(call => call.INSERT), false)
})

test('CLI adapter sends only the versioned evaluator envelope and parses one JSON result', async () => {
  const invocation = {}
  const evaluate = createMlCliEvaluator({
    command: 'python-test',
    timeoutMs: 1000,
    execute: async (command, args, request, options) => {
      Object.assign(invocation, { command, args, request, options })
      return { error: null, stdout: JSON.stringify({ classified_signals: [] }), stderr: '' }
    }
  })
  const envelope = { schemaVersion: 1, feed_items: [], cargo_value: 10, incident_id: 'TEST' }
  assert.deepEqual(await evaluate(envelope), { classified_signals: [] })
  assert.equal(invocation.command, 'python-test')
  assert.deepEqual(invocation.args, ['-m', 'ml.cli'])
  assert.deepEqual(invocation.request, envelope)
  assert.equal(invocation.options.timeout, 1000)
})

test('CLI adapter maps missing runtime, timeout and malformed output to safe errors', async () => {
  const missingRuntime = createMlCliEvaluator({ execute: async () => ({
    error: Object.assign(new Error('not found'), { code: 'ENOENT' }), stdout: '', stderr: ''
  }) })
  await assert.rejects(missingRuntime({}), error => error instanceof MlCliError && error.status === 503)

  const timedOut = createMlCliEvaluator({ execute: async () => ({
    error: Object.assign(new Error('timeout'), { code: 'ETIMEDOUT', killed: true }), stdout: '', stderr: ''
  }) })
  await assert.rejects(timedOut({}), error => error instanceof MlCliError && error.status === 504)

  const malformed = createMlCliEvaluator({ execute: async () => ({ error: null, stdout: 'not json', stderr: '' }) })
  await assert.rejects(malformed({}), error => error instanceof MlCliError && error.status === 502)

  const rejectedInput = createMlCliEvaluator({ execute: async () => ({
    error: Object.assign(new Error('evaluator rejected input'), { code: 1 }),
    stdout: '', stderr: 'evaluation error: ValueError: feed_items[0] must be a mapping\n'
  }) })
  await assert.rejects(rejectedInput({}), error => error instanceof MlCliError && error.status === 400)
})

test('remote adapter posts the versioned envelope and returns evaluator JSON', async () => {
  let invocation
  const evaluate = createMlRemoteEvaluator({
    url: 'https://python.internal/internal/v1/evaluate',
    authToken: evaluatorToken,
    timeoutMs: 250,
    fetchImpl: async (url, options) => {
      invocation = { url: String(url), options }
      return { ok: true, status: 200, text: async () => JSON.stringify(resultFor()) }
    }
  })
  const envelope = { schemaVersion: 1, feed_items: [], cargo_value: 10, incident_id: 'TEST' }
  assert.deepEqual(await evaluate(envelope), resultFor())
  assert.equal(invocation.url, 'https://python.internal/internal/v1/evaluate')
  assert.equal(invocation.options.method, 'POST')
  assert.equal(invocation.options.headers['content-type'], 'application/json')
  assert.equal(invocation.options.headers.authorization, `Bearer ${evaluatorToken}`)
  assert.deepEqual(JSON.parse(invocation.options.body), envelope)
})

test('remote adapter maps timeout, connection, malformed response and HTTP errors', async () => {
  const timedOut = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate',
    authToken: evaluatorToken,
    timeoutMs: 5,
    fetchImpl: (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(Object.assign(new Error('abort'), { name: 'AbortError' })))
    })
  })
  await assert.rejects(timedOut({}), error => error instanceof MlCliError && error.status === 504)

  const timedOutReadingBody = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate',
    authToken: evaluatorToken,
    timeoutMs: 5,
    fetchImpl: async (_url, { signal }) => ({
      ok: true,
      status: 200,
      text: () => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(Object.assign(new Error('abort'), { name: 'AbortError' })))
      })
    })
  })
  await assert.rejects(timedOutReadingBody({}), error => error instanceof MlCliError && error.status === 504)

  const unavailable = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate', authToken: evaluatorToken,
    fetchImpl: async () => { throw new Error('socket details') }
  })
  await assert.rejects(unavailable({}), error => error instanceof MlCliError
    && error.status === 503 && !error.message.includes('socket details'))

  const malformed = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate',
    authToken: evaluatorToken,
    fetchImpl: async () => ({ ok: true, status: 200, text: async () => '<html>failure</html>' })
  })
  await assert.rejects(malformed({}), error => error instanceof MlCliError && error.status === 502)

  const invalidInput = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate',
    authToken: evaluatorToken,
    fetchImpl: async () => ({ ok: false, status: 422, text: async () => JSON.stringify({
      error: { code: 'invalid_evaluation_input', message: 'cargo_value is invalid' }
    }) })
  })
  await assert.rejects(invalidInput({}), error => error instanceof MlCliError
    && error.status === 400 && error.message.includes('cargo_value is invalid'))

  const serverError = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate',
    authToken: evaluatorToken,
    fetchImpl: async () => ({ ok: false, status: 503, text: async () => 'unavailable' })
  })
  await assert.rejects(serverError({}), error => error instanceof MlCliError && error.status === 502)
})

test('remote mode requires explicit URL and never falls back to subprocess mode', () => {
  assert.throws(() => createMlEvaluator({ env: { AEGISCHAIN_ML_MODE: 'remote' } }), error =>
    error instanceof MlCliError && error.status === 503 && error.message.includes('AEGISCHAIN_ML_URL'))
  assert.throws(() => createMlEvaluator({ env: { AEGISCHAIN_ML_MODE: 'unsupported' } }), error =>
    error instanceof MlCliError && error.status === 503)
  assert.throws(() => createMlEvaluator({ env: {
    AEGISCHAIN_ML_MODE: 'remote',
    AEGISCHAIN_ML_URL: 'https://python.internal/evaluate'
  } }), error => error instanceof MlCliError && error.status === 503 && error.message.includes('AEGISCHAIN_ML_TOKEN'))
  assert.throws(() => createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate', authToken: 'weak'
  }), error => error instanceof MlCliError && error.status === 503)
  assert.throws(() => createMlRemoteEvaluator({
    url: 'http://python.internal/evaluate', authToken: evaluatorToken
  }), error => error instanceof MlCliError && error.status === 503 && error.message.includes('HTTPS'))
})

test('remote evaluation success persists links and a pending non-executed recommendation', async () => {
  const request = makeRequest()
  const remote = createMlRemoteEvaluator({
    url: 'https://python.internal/internal/v1/evaluate',
    authToken: evaluatorToken,
    fetchImpl: async (_url, options) => {
      assert.deepEqual(JSON.parse(options.body), {
        schemaVersion: 1,
        feed_items: request.feed_items,
        cargo_value: request.cargo_value,
        incident_id: request.incident_id
      })
      return { ok: true, status: 200, text: async () => JSON.stringify(resultFor()) }
    }
  })
  const h = makeHarness({ evaluate: remote })
  const response = await h.handler(h.request(request))
  const [signal] = h.calls.find(call => call.INSERT).INSERT.entries
  assert.equal(signal.ID, response.signalID)
  assert.equal(signal.recommendations[0].signal_ID, signal.ID)
  assert.deepEqual(signal.shipmentImpacts, [{ signal_ID: signal.ID, shipment_ID: shipmentID }])
  assert.deepEqual(signal.inventoryImpacts, [{ signal_ID: signal.ID, inventoryItem_ID: inventoryItemID }])
  assert.equal(signal.recommendations[0].approvalStatus, 'pending')
  assert.equal(signal.recommendations[0].executionStatus, 'notExecuted')
})

test('remote evaluator failures create no signal or recommendation records', async () => {
  const failures = [
    { fetchImpl: async () => { throw new Error('connection refused') }, status: 503 },
    { fetchImpl: async () => ({ ok: false, status: 401, text: async () => 'unauthorized' }), status: 502 },
    { fetchImpl: async () => ({ ok: false, status: 503, text: async () => 'unavailable' }), status: 502 },
    { fetchImpl: async () => ({ ok: true, status: 200, text: async () => 'not json' }), status: 502 }
  ]
  for (const { fetchImpl, status } of failures) {
    const remote = createMlRemoteEvaluator({
    url: 'https://python.internal/evaluate', authToken: evaluatorToken, fetchImpl
    })
    const h = makeHarness({ evaluate: remote })
    await assert.rejects(h.handler(h.request(makeRequest())), error => error.status === status)
    assert.equal(h.calls.some(call => call.INSERT), false)
  }
})
