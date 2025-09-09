import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Column {
    anchors.fill: parent
    spacing: 8

    Column {
        spacing: 4
        RowLayout {
            width: parent.width
            Label { text: "Incident Dashboard — Command"; font.bold: true }
            Item { Layout.fillWidth: true }
            Label {
                text: "Mission: " + dashboard.incidentName +
                      " | #" + dashboard.incidentNumber +
                      " | Type: " + dashboard.incidentType +
                      " | Role: " + dashboard.activeUserRole
            }
        }
        RowLayout {
            width: parent.width
            spacing: 4
            Label { text: "OP Period: " + dashboard.opNumber }
            Button { text: "◀"; onClicked: dashboard.selectOp("prev") }
            Button { text: "current"; onClicked: dashboard.selectOp(dashboard.opNumber) }
            Button { text: "▶"; onClicked: dashboard.selectOp("next") }
            Label { text: "| Status: " + dashboard.incidentStatusText }
            Item { Layout.fillWidth: true }
            Label { text: "Local " + dashboard.localClock }
            Label { text: "| UTC " + dashboard.utcClock }
        }
    }

    GridLayout {
        columns: width < 900 ? 1 : 2
        columnSpacing: 16
        rowSpacing: 16
        width: parent.width

        ColumnLayout {
            Layout.fillWidth: true
            Label { text: "Objectives & Priorities"; font.bold: true }
            Button { text: "Manage Objectives"; onClicked: dashboard.openPlanningObjectives() }
            Repeater {
                model: dashboard.objectives
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: modelData.index; width: 24; font.family: "monospace" }
                    Text { text: "[" + modelData.priority + "]"; width: 80; font.family: "monospace" }
                    Text { text: modelData.text; font.family: "monospace" }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Label { text: "Status Snapshot"; font.bold: true }
            Text { text: "Teams: Assigned " + dashboard.statusSnapshot.teams.assigned +
                          " | Available " + dashboard.statusSnapshot.teams.available +
                          " | OOS " + dashboard.statusSnapshot.teams.oos }
            Text { text: "Personnel: Total " + dashboard.statusSnapshot.personnel.total +
                          " | Checked-in " + dashboard.statusSnapshot.personnel.checkedIn +
                          " | Pending " + dashboard.statusSnapshot.personnel.pending }
            Text { text: "Vehicles: Assigned " + dashboard.statusSnapshot.vehicles.assigned +
                          " | Available " + dashboard.statusSnapshot.vehicles.available +
                          " | OOS " + dashboard.statusSnapshot.vehicles.oos }
            Text { text: "Aircraft: Assigned " + dashboard.statusSnapshot.aircraft.assigned +
                          " | Available " + dashboard.statusSnapshot.aircraft.available +
                          " | OOS " + dashboard.statusSnapshot.aircraft.oos }
            Text { text: "[Mini-Chart: ●●●●○ completion trend]" }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Label { text: "Recent Significant Events"; font.bold: true }
            RowLayout {
                spacing: 4
                Button { text: "Open Logs"; onClicked: dashboard.openOpsLogs() }
                Button { id: filterButton; property bool crit: false; text: crit ? "Critical" : "All"; onClicked: crit = !crit }
            }
            Repeater {
                model: dashboard.recentEvents
                delegate: Rectangle {
                    color: "transparent"
                    Layout.fillWidth: true
                    RowLayout {
                        anchors.fill: parent
                        Text { text: modelData.timeHHMM; width: 60; font.family: "monospace" }
                        Text { text: modelData.severity; width: 80; font.family: "monospace" }
                        Text { text: modelData.message; font.family: "monospace" }
                    }
                    MouseArea { anchors.fill: parent; onClicked: dashboard.openLogAt(modelData.timeHHMM) }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Label { text: "Communications / Alerts"; font.bold: true }
            Button { text: "Open Comms"; onClicked: dashboard.openCommsCenter() }
            Text { text: "High-Priority: " + dashboard.alertsHighPriority +
                          " | Unacked: " + dashboard.alertsUnacked }
            Text {
                visible: dashboard.bannerText.length > 0
                font.family: "monospace"
                text: {
                    var msg = dashboard.bannerText
                    var line = "─".repeat(msg.length + 2)
                    return "┌" + line + "┐\n| " + msg + " |\n└" + line + "┘"
                }
            }
        }
    }

    Column {
        spacing: 4
        Text {
            font.family: "monospace"
            text: "[" + dashboard.opTimelinePrev + "]───────|────[" + dashboard.opTimelineCurrent + "]─────|────[" + dashboard.opTimelineNext + "]────"
        }
        Row {
            spacing: 8
            Text { text: "Time left in OP-" + dashboard.opNumber + ": " + dashboard.timeLeftHHMMSS }
            Button { text: "Roll Over OP"; onClicked: dashboard.rollOp() }
            Button { text: "Edit Schedule"; onClicked: dashboard.openOpScheduler() }
        }
    }

    Row {
        spacing: 8
        Button { text: "New Objective"; onClicked: dashboard.createObjective() }
        Button { text: "New 214 Entry"; onClicked: dashboard.create214Entry() }
        Button { text: "Pause Incident"; onClicked: dashboard.pauseIncident() }
        Button { text: "Terminate Incident"; onClicked: dashboard.terminateIncident() }
        Button { text: "Export Snapshot (201/202)"; onClicked: dashboard.exportSnapshot() }
    }
}
