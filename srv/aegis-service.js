import cds from '@sap/cds'

export default class AegisService extends cds.ApplicationService {
  async init() {
    const { DisruptionSignals, Recommendations } = this.entities

    this.before('CREATE', DisruptionSignals, req => {
      const shipmentImpacts = req.data.shipmentImpacts || []
      const inventoryImpacts = req.data.inventoryImpacts || []
      if (!shipmentImpacts.length && !inventoryImpacts.length) {
        req.reject(400, 'A disruption signal must affect at least one shipment or inventory item')
      }
      if (req.data.source !== 'demoScenario') {
        req.reject(400, "Disruption signal source must be 'demoScenario'")
      }
    })

    this.before('CREATE', Recommendations, req => {
      if (req.data.approvalStatus && req.data.approvalStatus !== 'pending') {
        req.reject(400, 'A recommendation must start as pending')
      }
      req.data.approvalStatus = 'pending'
      req.data.decidedBy = null
      req.data.decidedAt = null
      req.data.decisionNote = null
    })

    this.before('UPDATE', Recommendations, req => {
      req.reject(405, 'Use decideRecommendation to record an approval decision')
    })

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
        decidedBy: req.user.id,
        decidedAt: new Date().toISOString(),
        decisionNote: decisionNote || null
      }).where({ ID: recommendationID, approvalStatus: 'pending' }))

      return { recommendationID, decision, executionStatus: 'notExecuted' }
    })

    return super.init()
  }
}
