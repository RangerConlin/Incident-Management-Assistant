import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "./" as Shared
import "./components" as C

Shared.MasterTableWindow {
  id: root
  windowTitle: "Narrative"
  searchPlaceholder: "Search narrative"
  primaryKey: "id"
  defaultSort: ({ key: "timestamp", order: "desc" })
  model: NarrativeModel

  // Narrative CRUD is incident-scoped
  // taskId can be provided by the opener (0 -> all tasks)
  property int taskId: 0
  bridgeListFn: function(q) { return incidentBridge.listTaskNarrative(taskId, q || searchBar.text, criticalOnlyBox.checked, teamFilterBox.currentText) }
  bridgeCreateFn: function(m) { m.taskid = taskId; return incidentBridge.createTaskNarrative(m) }
  bridgeUpdateFn: function(id, m) { return incidentBridge.updateTaskNarrative(id, m) }
  bridgeDeleteFn: function(id) { return incidentBridge.deleteTaskNarrative(id) }

  // Columns reflect incident DB schema
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 70 },
    { key: "timestamp", label: "Date/Time (UTC)", type: "text", editable: true, required: true, width: 190 },
    { key: "narrative", label: "Entry", type: "multiline", editable: true, required: true, width: 420 },
    { key: "entered_by", label: "Entered By", type: "text", editable: true, width: 160 },
    { key: "team_num", label: "Team", type: "text", editable: true, width: 120 },
    { key: "critical", label: "Critical", type: "int", editable: true, width: 90 }
  ]

  header: ToolBar {
    RowLayout {
      anchors.fill: parent
      spacing: 8
      C.SearchBar {
        id: searchBar
        placeholder: searchPlaceholder
        Layout.fillWidth: true
        onSearchChanged: updateQuery()
      }
      CheckBox { id: criticalOnlyBox; text: "Critical"; onToggled: updateQuery() }
      ComboBox {
        id: teamFilterBox
        model: [""] // will be populated on show
        Layout.preferredWidth: 140
        onActivated: updateQuery()
      }
      Button { text: "Add"; onClicked: addRow() }
      Button { text: "Edit"; enabled: selectedRow >= 0; onClicked: editRow() }
      Button { text: "Delete"; enabled: selectedRow >= 0; onClicked: deleteRow() }
      Button { text: "Export ICS-214"; onClicked: incidentBridge && incidentBridge.exportIcs214 && incidentBridge.exportIcs214(taskId) }
    }
  }

  function updateQuery() {
    // Build SQL with filters (default DESC by timestamp)
    var table = "narrative_entries"; // IncidentBridge will fallback if task_narrative exists
    var clauses = []
    if (taskId && taskId > 0) clauses.push("taskid = " + taskId)
    var q = searchBar.text.trim()
    if (q.length > 0) clauses.push("(narrative LIKE '%" + q.replace("'","''") + "%' OR entered_by LIKE '%" + q.replace("'","''") + "%')")
    if (criticalOnlyBox.checked) clauses.push("critical = 1")
    var team = (teamFilterBox.currentText || "").trim()
    if (team.length > 0) clauses.push("team_num = '" + team.replace("'","''") + "'")
    var where = clauses.length ? (" WHERE " + clauses.join(" AND ")) : ""
    var sql = "SELECT id, taskid, timestamp, narrative, entered_by, team_num, critical FROM " + table + where + " ORDER BY timestamp DESC"
    try { NarrativeModel.setQuery(sql) } catch (e) { /* ignore */ }
  }

  Component.onCompleted: {
    // Initial query and team dropdown values
    updateQuery()
    try {
      var rows = incidentBridge.listTaskNarrative(taskId, "", false, "") || []
      var teams = {"": true}
      for (var i=0; i<rows.length; i++) { var t = rows[i].team_num; if (t) teams[String(t)] = true }
      teamFilterBox.model = Object.keys(teams)
    } catch (e) { teamFilterBox.model = [""] }
  }
}

