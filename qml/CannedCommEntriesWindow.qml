import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Canned Communications"
  searchPlaceholder: "Search canned entries"
  primaryKey: "id"
  defaultSort: ({ key: "title", order: "asc" })
  model: CannedCommEntriesModel
  // Wire CRUD actions to the catalog bridge
  bridgeListFn: function(q) { return catalogBridge.listCannedCommEntries(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createCannedCommEntry(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateCannedCommEntry(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteCannedCommEntry(id) }
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "title", label: "Title", type: "text", editable: true, required: true, width: 260 },
    { key: "category", label: "Category", type: "text", editable: true, width: 160 },
    { key: "message", label: "Message", type: "multiline", editable: true, required: true, width: 420 },
    { key: "notification_level", label: "Notify Level", type: "enum", editable: true, width: 200, valueMap: ({ 0: "None", 1: "Notification", 2: "Emergency Alert" }) },
    { key: "status_update", label: "Status Update", type: "enum", editable: true, width: 220, options: ["", "Active", "Resolved", "Closed"] }
  ]
  // Hint for model-driven ORDER BY sorting
  tableName: "canned_comm_entries"
  // viewing via model; bridge remains unused here
}
