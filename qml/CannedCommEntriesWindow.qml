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
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "title", label: "Title", type: "text", editable: true, required: true, width: 260 },
    { key: "category", label: "Category", type: "text", editable: true, width: 160 },
    { key: "body", label: "Body", type: "multiline", editable: true, required: true, width: 420 },
    { key: "delivery_channels", label: "Channels", type: "text", editable: true, width: 200 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 260 },
    { key: "is_active", label: "Active", type: "int", editable: true, width: 80 }
  ]
  // viewing via model; bridge remains unused here
}
