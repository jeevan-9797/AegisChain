import cds from '@sap/cds'
import { createMlEvaluator } from './ml-evaluator.js'
import { createMlIncidentHandler } from './ml-workflow.js'

export default class AegisService extends cds.ApplicationService {
  async init() {
    const { DisruptionSignals, Recommendations, Shipments, InventoryItems } = this.entities
    const requireNonBlank = (req, fields) => {
      for (const field of fields) {
        if (typeof req.data[field] !== 'string' || !req.data[field].trim()) {
          req.reject(400, `${field} is required and must be nonblank`)
          return false
        }
      }
      return true
    }

    this.before('CREATE', DisruptionSignals, async req => {
      if (!requireNonBlank(req, ['type', 'description', 'occurredAt', 'severity', 'source'])) return
      const shipmentImpacts = req.data.shipmentImpacts ?? []
      const inventoryImpacts = req.data.inventoryImpacts ?? []
      if (!Array.isArray(shipmentImpacts) || !Array.isArray(inventoryImpacts)) {
        req.reject(400, 'Shipment and inventory impacts must be arrays')
        return
      }
      if (!shipmentImpacts.length && !inventoryImpacts.length) {
        req.reject(400, 'A disruption signal must affect at least one shipment or inventory item')
        return
      }
      if (!['demoScenario', 'mlEvaluation'].includes(req.data.source)) {
        req.reject(400, "Disruption signal source must be 'demoScenario' or 'mlEvaluation'")
        return
      }

      const validateReferences = async (impacts, foreignKey, association, entity, label) => {
        const ids = impacts.map(impact => impact?.[foreignKey] ?? impact?.[association]?.ID)
        if (ids.some(id => typeof id !== 'string' || !id.trim())) {
          req.reject(400, `Every ${label} impact must include an explicit ${foreignKey}`)
          return
        }

        const uniqueIDs = [...new Set(ids)]
        if (uniqueIDs.length !== ids.length) {
          req.reject(400, `Duplicate ${label} impact IDs are not allowed`)
          return
        }
        const existing = await cds.tx(req).run(
          SELECT.from(entity).columns('ID').where({ ID: { in: uniqueIDs } })
        )
        if (existing.length !== uniqueIDs.length) {
          req.reject(400, `Every ${label} impact must reference an existing ${label}`)
          return false
        }
        return true
      }

      if (!await validateReferences(shipmentImpacts, 'shipment_ID', 'shipment', Shipments, 'shipment')) return
      if (!await validateReferences(inventoryImpacts, 'inventoryItem_ID', 'inventoryItem', InventoryItems, 'inventory item')) return
    })

    this.before('CREATE', Recommendations, async req => {
      if (!requireNonBlank(req, ['action', 'rationale', 'source'])) return
      if (!['ai', 'fallback'].includes(req.data.source)) {
        req.reject(400, "Recommendation source must be 'ai' or 'fallback'")
        return
      }
      if (req.data.approvalStatus && req.data.approvalStatus !== 'pending') {
        req.reject(400, 'A recommendation must start as pending')
        return
      }
      if (req.data.executionStatus && req.data.executionStatus !== 'notExecuted') {
        req.reject(400, 'A recommendation must start with executionStatus notExecuted')
        return
      }
      const signalID = req.data.signal_ID ?? req.data.signal?.ID
      if (typeof signalID !== 'string' || !signalID.trim()) {
        req.reject(400, 'signal_ID is required, nonblank, and must reference an existing signal')
        return
      }
      const signal = await cds.tx(req).run(
        SELECT.one.from(DisruptionSignals).columns('ID').where({ ID: signalID })
      )
      if (!signal) {
        req.reject(400, 'signal_ID must reference an existing signal')
        return
      }

      req.data.approvalStatus = 'pending'
      req.data.executionStatus = 'notExecuted'
      req.data.decidedBy = null
      req.data.decidedAt = null
      req.data.decisionNote = null
    })

    this.before('UPDATE', Recommendations, req => {
      req.reject(405, 'Use decideRecommendation to record an approval decision')
    })

    this.on('evaluateIncident', createMlIncidentHandler({
      evaluate: createMlEvaluator(),
      txForRequest: req => cds.tx(req),
      entities: this.entities
    }))

    this.on('decideRecommendation', async req => {
      const { recommendationID, decision, decisionNote } = req.data
      if (!recommendationID) req.reject(400, 'recommendationID is required')
      if (!['approved', 'rejected'].includes(decision)) req.reject(400, 'Decision must be approved or rejected')

      const tx = cds.tx(req)
      const row = await tx.run(SELECT.one.from(Recommendations).where({ ID: recommendationID }))
      if (!row) req.reject(404, 'Recommendation not found')
      if (row.approvalStatus !== 'pending') req.reject(409, 'Only pending recommendations can be decided')

      await tx.run(UPDATE(Recommendations).set({
        approvalStatus: decision,
        executionStatus: 'notExecuted',
        decidedBy: req.user.id,
        decidedAt: new Date().toISOString(),
        decisionNote: decisionNote || null
      }).where({ ID: recommendationID, approvalStatus: 'pending' }))

      return { recommendationID, decision, executionStatus: 'notExecuted' }
    })

    return super.init()
  }
}
