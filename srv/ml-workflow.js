import { randomUUID } from 'node:crypto'
import cds from '@sap/cds'
import { MlCliError } from './ml-evaluator.js'

const { SELECT, INSERT } = cds.ql

const CATEGORY_MAP = Object.freeze({
  CHOKEPOINT: 'Chokepoint',
  PORT: 'Port',
  TARIFF: 'Tariff',
  WEATHER: 'Weather'
})

const SEVERITY_MAP = Object.freeze({ 3: 'critical', 2: 'medium', 1: 'low' })

export class MlWorkflowError extends Error {
  constructor(status, message) {
    super(message)
    this.name = 'MlWorkflowError'
    this.status = status
  }
}

function fail(status, message) {
  throw new MlWorkflowError(status, message)
}

function numericMetric(value, label) {
  return typeof value === 'number' && Number.isFinite(value) ? `${label}: ${value}` : null
}

/** Convert evaluator output to one supported CAP signal and advisory recommendation. */
export function mapMlEvaluation(result, occurredAt) {
  if (!result || typeof result !== 'object' || !Array.isArray(result.classified_signals)) {
    throw new MlWorkflowError(502, 'ML evaluator response is missing classified_signals')
  }
  const optimization = result.decision_optimization
  if (!optimization || typeof optimization !== 'object'
      || typeof optimization.recommended_scenario_key !== 'string'
      || typeof optimization.recommended_name !== 'string'
      || typeof optimization.recommended_mode !== 'string'
      || typeof optimization.recommendation_rationale !== 'string'
      || !optimization.recommendation_rationale.trim()) {
    throw new MlWorkflowError(502, 'ML evaluator response is missing its recommendation scenario or rationale')
  }

  for (const signal of result.classified_signals) {
    if (!signal || typeof signal.category !== 'string'
        || !Number.isInteger(signal.severity) || signal.severity < 1 || signal.severity > 3) {
      throw new MlWorkflowError(502, 'ML evaluator returned a malformed classified signal')
    }
  }

  const actionable = result.classified_signals.filter(signal =>
    Object.hasOwn(CATEGORY_MAP, signal.category) && signal.severity >= 2
  )
  if (!actionable.length) {
    const categories = result.classified_signals.map(signal => signal.category)
    const onlyUnsupported = !categories.some(category => Object.hasOwn(CATEGORY_MAP, category))
    const reason = onlyUnsupported
      ? 'ML returned only OTHER or unsupported disruption categories'
      : 'ML found no active disruption at moderate severity or higher'
    throw new MlWorkflowError(422, `${reason}; no CAP records were created`)
  }
  if (actionable.length > 1) {
    throw new MlWorkflowError(422, 'ML found multiple active disruptions; evaluate one incident at a time; no CAP records were created')
  }

  const classified = actionable[0]
  const title = typeof classified.title === 'string' && classified.title.trim()
    ? classified.title.trim()
    : classified.summary
  if (typeof title !== 'string' || !title.trim()) {
    throw new MlWorkflowError(502, 'ML evaluator returned an active signal without a title or summary')
  }

  const scenario = result.scenarios?.[optimization.recommended_scenario_key]
  const tradeoffs = [
    typeof scenario?.description === 'string' ? scenario.description : null,
    numericMetric(scenario?.net_economic_impact_usd, 'Estimated net impact USD'),
    numericMetric(scenario?.extra_delay_days, 'Additional delay days'),
    numericMetric(scenario?.spoilage_risk_pct, 'Spoilage risk percent'),
    numericMetric(scenario?.extra_freight_usd, 'Additional freight USD')
  ].filter(Boolean).join('; ')

  return {
    signal: {
      type: CATEGORY_MAP[classified.category],
      description: title.slice(0, 500),
      occurredAt,
      severity: SEVERITY_MAP[classified.severity],
      source: 'mlEvaluation'
    },
    recommendation: {
      action: `${optimization.recommended_name} (${optimization.recommended_scenario_key}) via ${optimization.recommended_mode}`.slice(0, 500),
      rationale: optimization.recommendation_rationale,
      tradeoffs: tradeoffs || null,
      source: 'fallback',
      approvalStatus: 'pending',
      executionStatus: 'notExecuted'
    },
    category: CATEGORY_MAP[classified.category],
    severity: SEVERITY_MAP[classified.severity],
    scenarioKey: optimization.recommended_scenario_key
  }
}

function normalizeImpactIds(value, field, req) {
  if (value === undefined || value === null) return []
  if (!Array.isArray(value)) return req.reject(400, `${field} must be an array of explicit CAP IDs`)
  const ids = []
  for (const id of value) {
    if (typeof id !== 'string' || !id.trim()) {
      return req.reject(400, `${field} must contain nonblank explicit CAP IDs`)
    }
    ids.push(id.trim().toLowerCase())
  }
  if (new Set(ids).size !== ids.length) {
    return req.reject(400, `${field} must not contain duplicate IDs`)
  }
  return ids
}

/** CAP action handler. The injected evaluator and transaction make it unit-testable. */
export function createMlIncidentHandler({ evaluate, txForRequest, entities, now = () => new Date() }) {
  return async req => {
    const data = req.data ?? {}
    if (data.schemaVersion !== 1) return req.reject(400, 'schemaVersion must be 1')
    if (!Array.isArray(data.feed_items) || !data.feed_items.length) {
      return req.reject(400, 'feed_items must contain at least one feed item; no CAP records were created')
    }
    if (typeof data.incident_id !== 'string' || !data.incident_id.trim()) {
      return req.reject(400, 'incident_id is required and must be nonblank')
    }
    if (typeof data.cargo_value !== 'number' || !Number.isFinite(data.cargo_value) || data.cargo_value <= 0) {
      return req.reject(400, 'cargo_value must be a finite number greater than zero')
    }

    const shipmentIDs = normalizeImpactIds(data.shipmentIDs, 'shipmentIDs', req)
    const inventoryItemIDs = normalizeImpactIds(data.inventoryItemIDs, 'inventoryItemIDs', req)
    if (!shipmentIDs.length && !inventoryItemIDs.length) {
      return req.reject(400, 'Provide at least one explicit shipmentIDs or inventoryItemIDs value')
    }

    const tx = txForRequest(req)
    const validateIDs = async (ids, entity, field, label) => {
      if (!ids.length) return true
      const rows = await tx.run(SELECT.from(entity).columns('ID').where({ ID: { in: ids } }))
      const found = new Set(rows.map(row => String(row.ID).toLowerCase()))
      const missing = ids.filter(id => !found.has(id))
      if (missing.length) req.reject(400, `${field} contains unknown ${label} ID(s): ${missing.join(', ')}`)
      return missing.length === 0
    }
    if (!await validateIDs(shipmentIDs, entities.Shipments, 'shipmentIDs', 'shipment')) return
    if (!await validateIDs(inventoryItemIDs, entities.InventoryItems, 'inventoryItemIDs', 'inventory item')) return

    let evaluation
    try {
      evaluation = await evaluate({
        schemaVersion: 1,
        feed_items: data.feed_items,
        cargo_value: data.cargo_value,
        incident_id: data.incident_id.trim()
      })
    } catch (error) {
      if (error instanceof MlCliError) return req.reject(error.status, error.message)
      return req.reject(502, 'ML evaluation failed before any CAP records were created')
    }

    let mapped
    try {
      mapped = mapMlEvaluation(evaluation, now().toISOString())
    } catch (error) {
      if (error instanceof MlWorkflowError) return req.reject(error.status, error.message)
      return req.reject(502, 'ML evaluation output could not be mapped to the CAP contract')
    }

    const signalID = randomUUID()
    const recommendationID = randomUUID()
    const signalEntry = {
      ID: signalID,
      ...mapped.signal,
      shipmentImpacts: shipmentIDs.map(shipment_ID => ({ signal_ID: signalID, shipment_ID })),
      inventoryImpacts: inventoryItemIDs.map(inventoryItem_ID => ({ signal_ID: signalID, inventoryItem_ID })),
      recommendations: [{
        ID: recommendationID,
        signal_ID: signalID,
        ...mapped.recommendation,
        decidedBy: null,
        decidedAt: null,
        decisionNote: null
      }]
    }

    // One deep insert keeps the signal, explicit impact links, and pending recommendation together.
    await tx.run(INSERT.into(entities.DisruptionSignals).entries(signalEntry))
    return {
      signalID,
      recommendationID,
      category: mapped.category,
      severity: mapped.severity,
      scenarioKey: mapped.scenarioKey,
      approvalStatus: 'pending',
      executionStatus: 'notExecuted'
    }
  }
}
