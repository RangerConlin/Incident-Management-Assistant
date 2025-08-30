import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit EMS Agencies"
  searchPlaceholder: "Search EMS Agencies"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: EmsModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 220 },
    { key: "type", label: "Type", type: "text", editable: true, width: 140 },
    { key: "phone", label: "Phone", type: "tel", editable: true, width: 140 },
    { key: "fax", label: "Fax", type: "text", editable: true, width: 140 },
    { key: "email", label: "Email", type: "email", editable: true, width: 200 },
    { key: "contact", label: "Contact", type: "text", editable: true, width: 180 },
    { key: "address", label: "Address", type: "text", editable: true, width: 240 },
    { key: "city", label: "City", type: "text", editable: true, width: 160 },
    { key: "state", label: "State", type: "text", editable: true, width: 80 },
    { key: "zip", label: "ZIP", type: "text", editable: true, width: 100 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 260 },
    { key: "is_active", label: "Active", type: "int", editable: true, width: 80 }
  ]
  // viewing via model; bridge remains unused here
}
