import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Safety Templates"
  searchPlaceholder: "Search safety templates"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: SafetyTemplatesModel
  bridgeListFn: function(q) { return catalogBridge.listSafetyTemplates(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createSafetyTemplate(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateSafetyTemplate(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteSafetyTemplate(id) }
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 240 },
    { key: "operational_context", label: "Context", type: "text", editable: true, width: 220 },
    { key: "hazard", label: "Hazard", type: "text", editable: true, required: true, width: 260 },
    { key: "controls", label: "Controls", type: "multiline", editable: true, required: true, width: 360 },
    { key: "residual_risk", label: "Residual Risk", type: "text", editable: true, width: 160 },
    { key: "ppe", label: "PPE", type: "text", editable: true, width: 180 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 260 }
  ]
}
