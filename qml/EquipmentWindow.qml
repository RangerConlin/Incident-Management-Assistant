import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Equipment"
  searchPlaceholder: "Search equipment"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: EquipmentModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 70 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 220 },
    { key: "type", label: "Type", type: "text", editable: true, width: 150 },
    { key: "serial_number", label: "Serial #", type: "text", editable: true, width: 160 },
    { key: "condition", label: "Condition", type: "text", editable: true, width: 120 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 240 }
  ]
}
