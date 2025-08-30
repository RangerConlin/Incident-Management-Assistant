import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Personnel"
  searchPlaceholder: "Search by name or ID"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: PersonnelModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 80 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 220 },
    { key: "callsign", label: "Callsign", type: "text", editable: true, width: 140 },
    { key: "role", label: "Role", type: "text", editable: true, width: 160 },
    { key: "phone", label: "Phone", type: "tel", editable: true, width: 160 },
    { key: "email", label: "Email", type: "email", editable: true, width: 220 },
  ]
}
