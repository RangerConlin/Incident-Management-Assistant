import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Objectives (Templates)"
  searchPlaceholder: "Search objectives"
  primaryKey: "id"
  defaultSort: ({ key: "priority", order: "desc" })
  model: ObjectivesModel
  bridgeListFn: function(q) { return catalogBridge.listObjectives(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createObjectives(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateObjectives(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteObjectives(id) }
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "description", label: "Description", type: "multiline", editable: true, required: true, width: 420 },
    { key: "priority", label: "Priority", type: "int", editable: true, width: 90 },
    { key: "status", label: "Status", type: "text", editable: true, width: 120 },
    { key: "section", label: "Section", type: "text", editable: true, width: 120 },
    { key: "due_time", label: "Due", type: "text", editable: true, width: 140 },
    { key: "customer", label: "Customer", type: "text", editable: true, width: 160 },
    { key: "created_by", label: "Created By", type: "text", editable: true, width: 140 }
  ]
}
