import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Task Types"
  searchPlaceholder: "Search task types"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: TaskTypesModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 220 },
    { key: "category", label: "Category", type: "text", editable: true, width: 160 },
    { key: "description", label: "Description", type: "multiline", editable: true, width: 360 },
    { key: "is_active", label: "Active", type: "int", editable: true, width: 80 }
  ]
}
