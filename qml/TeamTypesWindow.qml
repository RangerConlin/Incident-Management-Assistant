import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Team Types"
  searchPlaceholder: "Search team types"
  primaryKey: "id"
  defaultSort: ({ key: "name", order: "asc" })
  model: TeamTypesModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "type_short", label: "Name", type: "text", editable: true, required: true, width: 240 },
    { key: "name", label: "Description", type: "multiline", editable: true, width: 420 },
  ]
}
