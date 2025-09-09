import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Hospitals"
  searchPlaceholder: "Search Hospitals"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: HospitalsModel
  bridgeListFn: function(q) { return catalogBridge.listHospitals(q) }
  bridgeCreateFn: function(m) { return catalogBridge.createHospital(m) }
  bridgeUpdateFn: function(id, m) { return catalogBridge.updateHospital(id, m) }
  bridgeDeleteFn: function(id) { return catalogBridge.deleteHospital(id) }
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 200 },
    { key: "address", label: "Address", type: "text", editable: true, width: 240 },
    { key: "contact_name", label: "Contact", type: "text", editable: true, width: 180 },
    { key: "phone_er", label: "ER Phone", type: "tel", editable: true, width: 140 },
    { key: "phone_switchboard", label: "Switchboard", type: "tel", editable: true, width: 140 },
    { key: "travel_time_min", label: "Travel Min", type: "int", editable: true, width: 100 },
    { key: "helipad", label: "Helipad", type: "enum", editable: true, width: 100, valueMap: ({ 0: "No", 1: "Yes" }) },
    { key: "trauma_level", label: "Trauma Level", type: "enum", editable: true, width: 140, options: ["None", "I", "II", "III", "IV"] },
    { key: "burn_center", label: "Burn Center", type: "enum", editable: true, width: 120, valueMap: ({ 0: "No", 1: "Yes" }) },
    { key: "pediatric_capability", label: "Pediatric", type: "enum", editable: true, width: 120, valueMap: ({ 0: "No", 1: "Yes" }) },
    { key: "bed_available", label: "Beds", type: "int", editable: true, width: 80 },
    { key: "diversion_status", label: "Diversion", type: "text", editable: true, width: 160 },
    { key: "ambulance_radio_channel", label: "Amb Radio Ch", type: "text", editable: true, width: 160 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 260 },
    { key: "lat", label: "Latitude", type: "float", editable: true, width: 120 },
    { key: "lon", label: "Longitude", type: "float", editable: true, width: 120 }
  ]
}

