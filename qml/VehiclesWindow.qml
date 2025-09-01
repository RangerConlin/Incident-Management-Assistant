import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Vehicles"
  searchPlaceholder: "Search vehicles"
  primaryKey: "id"
  defaultSort: ({ key: "make", order: "asc" })
  model: VehiclesModel
  bridgeListFn: function(q) { return catalogBridge.listVehicles(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createVehicles(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateVehicles(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteVehicles(id) }
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 70 },
    { key: "vin", label: "VIN", type: "text", editable: true, width: 200 },
    { key: "license_plate", label: "Plate", type: "text", editable: true, width: 120 },
    { key: "year", label: "Year", type: "int", editable: true, width: 80 },
    { key: "make", label: "Make", type: "text", editable: true, width: 120 },
    { key: "model", label: "Model", type: "text", editable: true, width: 140 },
    { key: "capacity", label: "Capacity", type: "int", editable: true, width: 100 },
    { key: "type_id", label: "Type ID", type: "int", editable: true, width: 90 },
    { key: "status_id", label: "Status ID", type: "int", editable: true, width: 90 },
    { key: "tags", label: "Tags", type: "text", editable: true, width: 160 },
    { key: "organization", label: "Org", type: "text", editable: true, width: 150 }
  ]
}
