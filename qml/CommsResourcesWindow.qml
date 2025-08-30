import QtQuick 2.15
import QtQuick.Controls 2.15
import "./" as Shared

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Communications Resources"
  searchPlaceholder: "Search by alpha tag or ID"
  primaryKey: "id"
  defaultSort: ({ key: "alpha_tag", order: "asc" })
  model: CommsResourcesModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "alpha_tag", label: "Alpha Tag", type: "text", editable: true, required: true, width: 140 },
    { key: "function", label: "Function", type: "text", editable: true, width: 140 },
    { key: "freq_rx", label: "Rx Freq", type: "text", editable: true, width: 120 },
    { key: "rx_tone", label: "Rx Tone", type: "text", editable: true, width: 100 },
    { key: "freq_tx", label: "Tx Freq", type: "text", editable: true, width: 120 },
    { key: "tx_tone", label: "Tx Tone", type: "text", editable: true, width: 100 },
    { key: "system", label: "System", type: "text", editable: true, width: 120 },
    { key: "mode", label: "Mode", type: "text", editable: true, width: 100 },
    { key: "notes", label: "Notes", type: "multiline", editable: true, width: 220 },
    { key: "line_a", label: "Line A", type: "text", editable: true, width: 120 },
    { key: "line_c", label: "Line C", type: "text", editable: true, width: 120 }
  ]
}
