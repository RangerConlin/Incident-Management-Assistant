import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Aircraft"
  searchPlaceholder: "Search by tail number or callsign"
  primaryKey: "id"
  defaultSort: ({ key: "tail_number", order: "asc" })
  model: AircraftModel
  bridgeListFn: function(q) { return catalogBridge.listAircraft(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createAircraft(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateAircraft(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteAircraft(id) }
  columns: [
    { key: "tail_number", label: "Tail Number", type: "text", editable: true, required: true, width: 140 },
    { key: "callsign", label: "Callsign", type: "text", editable: true, width: 120 },
    { key: "type", label: "Type", type: "text", editable: true, width: 120 },
    { key: "make_model", label: "Make/Model", type: "text", editable: true, width: 160 },
    { key: "capacity", label: "Capacity", type: "int", editable: true, width: 90 },
    { key: "status", label: "Status", type: "enum", editable: true, required: true, width: 120, options: (typeof teamStatuses !== 'undefined' ? teamStatuses : []) },
    { key: "base_location", label: "Base Location", type: "text", editable: true, width: 160 },
    { key: "current_assignment", label: "Current Assignment", type: "text", editable: true, width: 180 },
    { key: "capabilities", label: "Capabilities", type: "multiline", editable: true, width: 200 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 200 },
    { key: "created_at", label: "Created", type: "text", editable: false, width: 160 },
    { key: "updated_at", label: "Updated", type: "text", editable: false, width: 160 }
  ]
}
