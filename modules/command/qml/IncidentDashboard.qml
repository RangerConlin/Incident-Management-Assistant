import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    anchors.fill: parent

    readonly property int pad: 10
    readonly property int gap: 12
    readonly property int breakpoint: 900
    readonly property string mono: "monospace"

    Column {
        id: page
        anchors.fill: parent
        anchors.margins: pad
        spacing: gap

        // ───────── Header ─────────
        Column {
            spacing: 6
            Text { text: "Incident Dashboard — Command"; font.bold: true; font.pixelSize: 16 }
            Text {
                text: "Mission: " + dashboard.incidentName +
                      " | #" + dashboard.incidentNumber +
                      " | Type: " + dashboard.incidentType +
                      " | Role: " + dashboard.activeUserRole
            }
            Row {
                spacing: 6
                Text { text: "OP Period: " + dashboard.opNumber }
                Button { text: "◀"; onClicked: dashboard.selectOp("prev") }
                Button { text: "current"; onClicked: dashboard.selectOp(dashboard.opNumber) }
                Button { text: "▶"; onClicked: dashboard.selectOp("next") }
                Text { text: " | Status: " + dashboard.incidentStatusText }
                Item { width: 12; height: 1 }
                Text { text: "Local " + dashboard.localClock }
                Text { text: " | UTC " + dashboard.utcClock }
            }
        }

        // ──────── Main content: wide vs narrow via Loader ────────
        Loader {
            id: mainLoader
            width: page.width
            active: true
            sourceComponent: (page.width >= breakpoint) ? wideLayout : narrowLayout
        }

        // ───────── OP timeline / countdown (full width) ─────────
        Rectangle {
            width: page.width
            color: "transparent"; border.color: "#80808080"; radius: 6
            Column {
                anchors.fill: parent; anchors.margins: pad; spacing: 6
                Text {
                    font.family: mono
                    text: "[" + dashboard.opTimelinePrev + "]───────|────[" +
                          dashboard.opTimelineCurrent + "]─────|────[" +
                          dashboard.opTimelineNext + "]────"
                }
                Row { spacing: 8
                    Text { text: "Time left in OP-" + dashboard.opNumber + ": " + dashboard.timeLeftHHMMSS }
                    Button { text: "Roll Over OP"; onClicked: dashboard.rollOp() }
                    Button { text: "Edit Schedule"; onClicked: dashboard.openOpScheduler() }
                }
            }
        }

        // ───────── Quick Actions (full width) ─────────
        Row {
            spacing: 8
            Button { text: "New Objective"; onClicked: dashboard.createObjective() }
            Button { text: "New 214 Entry"; onClicked: dashboard.create214Entry() }
            Button { text: "Pause Incident"; onClicked: dashboard.pauseIncident() }
            Button { text: "Terminate Incident"; onClicked: dashboard.terminateIncident() }
            Button { text: "Export Snapshot (201/202)"; onClicked: dashboard.exportSnapshot() }
        }
    }

    // ================= Components =================
    Component {
        id: wideLayout
        Row {
            id: wideRow
            spacing: gap
            width: page.width

            // Left column (half width)
            Column {
                spacing: gap
                width: (wideRow.width - gap) / 2
                // Objectives & Priorities
                Rectangle {
                    width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                    Column {
                        anchors.fill: parent; anchors.margins: pad; spacing: 6
                        Text { text: "Objectives & Priorities"; font.bold: true }
                        Button { text: "Manage Objectives"; onClicked: dashboard.openPlanningObjectives() }
                        Repeater {
                            model: dashboard.objectives
                            delegate: Text { font.family: mono; text: modelData.index + " [" + modelData.priority + "] " + modelData.text }
                        }
                    }
                }
                // Recent Significant Events
                Rectangle {
                    width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                    Column {
                        anchors.fill: parent; anchors.margins: pad; spacing: 6
                        Row { spacing: 6
                            Button { text: "Open Logs"; onClicked: dashboard.openOpsLogs() }
                            Button { id: filterBtn; property bool crit: false; text: crit ? "Critical" : "All"; onClicked: crit = !crit }
                        }
                        Repeater {
                            model: dashboard.recentEvents
                            delegate: Rectangle {
                                width: parent.width; color: "transparent"
                                Row { spacing: 8
                                    Text { text: modelData.timeHHMM; width: 60; font.family: mono }
                                    Text { text: modelData.severity; width: 80; font.family: mono }
                                    Text { text: modelData.message; font.family: mono; wrapMode: Text.WordWrap }
                                }
                                MouseArea { anchors.fill: parent; onClicked: dashboard.openLogAt(modelData.timeHHMM) }
                            }
                        }
                    }
                }
            }

            // Right column (half width)
            Column {
                spacing: gap
                width: (wideRow.width - gap) / 2
                // Status Snapshot
                Rectangle {
                    width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                    Column {
                        anchors.fill: parent; anchors.margins: pad; spacing: 4
                        Text { text: "Status Snapshot"; font.bold: true }
                        Text { font.family: mono; text: "Teams:     Assigned " + dashboard.statusSnapshot.teams.assigned + " | Available " + dashboard.statusSnapshot.teams.available + " | OOS " + dashboard.statusSnapshot.teams.oos }
                        Text { font.family: mono; text: "Personnel: Total " + dashboard.statusSnapshot.personnel.total + " | Checked-in " + dashboard.statusSnapshot.personnel.checkedIn + " | Pending " + dashboard.statusSnapshot.personnel.pending }
                        Text { font.family: mono; text: "Vehicles:  Assigned " + dashboard.statusSnapshot.vehicles.assigned + " | Available " + dashboard.statusSnapshot.vehicles.available + " | OOS " + dashboard.statusSnapshot.vehicles.oos }
                        Text { font.family: mono; text: "Aircraft:  Assigned " + dashboard.statusSnapshot.aircraft.assigned + " | Available " + dashboard.statusSnapshot.aircraft.available + " | OOS " + dashboard.statusSnapshot.aircraft.oos }
                        Text { font.family: mono; text: "[Mini-Chart: \u25CF\u25CF\u25CF\u25CF\u25CB completion trend]" }
                    }
                }
                // Comms / Alerts
                Rectangle {
                    width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                    Column {
                        anchors.fill: parent; anchors.margins: pad; spacing: 6
                        Row { spacing: 6
                            Button { text: "Open Comms"; onClicked: dashboard.openCommsCenter() }
                        }
                        Text { font.family: mono; text: "High-Priority: " + dashboard.alertsHighPriority + " | Unacked: " + dashboard.alertsUnacked }
                        Text {
                            visible: dashboard.bannerText && dashboard.bannerText.length > 0
                            font.family: mono
                            text: {
                                var msg = dashboard.bannerText;
                                var w = Math.max(44, Math.min( (parent.width/8)|0, msg.length + 2 ));
                                var line = "\u2500".repeat(w);
                                return "\u250C" + line + "\u2510\n| " + msg + " |\n\u2514" + line + "\u2518";
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: narrowLayout
        Column {
            spacing: gap
            width: page.width
            // Left bits stacked first
            Rectangle {
                width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                Column {
                    anchors.fill: parent; anchors.margins: pad; spacing: 6
                    Text { text: "Objectives & Priorities"; font.bold: true }
                    Button { text: "Manage Objectives"; onClicked: dashboard.openPlanningObjectives() }
                    Repeater {
                        model: dashboard.objectives
                        delegate: Text { font.family: mono; text: modelData.index + " [" + modelData.priority + "] " + modelData.text }
                    }
                }
            }
            Rectangle {
                width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                Column {
                    anchors.fill: parent; anchors.margins: pad; spacing: 6
                    Row { spacing: 6
                        Button { text: "Open Logs"; onClicked: dashboard.openOpsLogs() }
                        Button { id: filterBtn2; property bool crit: false; text: crit ? "Critical" : "All"; onClicked: crit = !crit }
                    }
                    Repeater {
                        model: dashboard.recentEvents
                        delegate: Rectangle {
                            width: parent.width; color: "transparent"
                            Row { spacing: 8
                                Text { text: modelData.timeHHMM; width: 60; font.family: mono }
                                Text { text: modelData.severity; width: 80; font.family: mono }
                                Text { text: modelData.message; font.family: mono; wrapMode: Text.WordWrap }
                            }
                            MouseArea { anchors.fill: parent; onClicked: dashboard.openLogAt(modelData.timeHHMM) }
                        }
                    }
                }
            }
            // Right bits stacked after
            Rectangle {
                width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                Column {
                    anchors.fill: parent; anchors.margins: pad; spacing: 4
                    Text { text: "Status Snapshot"; font.bold: true }
                    Text { font.family: mono; text: "Teams:     Assigned " + dashboard.statusSnapshot.teams.assigned + " | Available " + dashboard.statusSnapshot.teams.available + " | OOS " + dashboard.statusSnapshot.teams.oos }
                    Text { font.family: mono; text: "Personnel: Total " + dashboard.statusSnapshot.personnel.total + " | Checked-in " + dashboard.statusSnapshot.personnel.checkedIn + " | Pending " + dashboard.statusSnapshot.personnel.pending }
                    Text { font.family: mono; text: "Vehicles:  Assigned " + dashboard.statusSnapshot.vehicles.assigned + " | Available " + dashboard.statusSnapshot.vehicles.available + " | OOS " + dashboard.statusSnapshot.vehicles.oos }
                    Text { font.family: mono; text: "Aircraft:  Assigned " + dashboard.statusSnapshot.aircraft.assigned + " | Available " + dashboard.statusSnapshot.aircraft.available + " | OOS " + dashboard.statusSnapshot.aircraft.oos }
                    Text { font.family: mono; text: "[Mini-Chart: \u25CF\u25CF\u25CF\u25CF\u25CB completion trend]" }
                }
            }
            Rectangle {
                width: parent.width; color: "transparent"; border.color: "#80808080"; radius: 6
                Column {
                    anchors.fill: parent; anchors.margins: pad; spacing: 6
                    Row { spacing: 6
                        Button { text: "Open Comms"; onClicked: dashboard.openCommsCenter() }
                    }
                    Text { font.family: mono; text: "High-Priority: " + dashboard.alertsHighPriority + " | Unacked: " + dashboard.alertsUnacked }
                    Text {
                        visible: dashboard.bannerText && dashboard.bannerText.length > 0
                        font.family: mono
                        text: {
                            var msg = dashboard.bannerText;
                            var w = Math.max(44, Math.min( (parent.width/8)|0, msg.length + 2 ));
                            var line = "\u2500".repeat(w);
                            return "\u250C" + line + "\u2510\n| " + msg + " |\n\u2514" + line + "\u2518";
                        }
                    }
                }
            }
        }
    }
}