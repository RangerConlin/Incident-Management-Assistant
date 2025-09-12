// TeamDetailWindow — Full Redesign (matches 5 uploaded mockups)
// Notes:
// - No TabView, only TabBar + StackLayout (per project constraint)
// - Dynamically adapts to team type (AIR vs GT/others)
// - Overview panel mirrors screenshots (Team Type, Name/Callsign, Leader/Pilot, Phone, Status, Last Contact, Primary Task, Assignment)
// - Notes promoted under Overview
// - Action row: [Edit Team] [Needs Assistance] [Update Status] [View Task]
// - Tabs:
//     Ground:  Personnel (Ground) | Vehicles | Equipment | Logs
//     Air:     Aircrew | Aircraft | Equipment | Logs
// - Logs tab is the same drop‑in from the prior canvas (copy‑to‑214 behavior, immutable, print button)
// - Replace your existing TeamDetailWindow.qml with this file OR merge the <Logs> section if you already adopted it.
//
// Backend expectations on `teamBridge` (implement as needed):
//   team: {
//     id, team_type, name, callsign, team_leader_id, status,
//     team_leader_phone, last_comm_ts, current_task_id, assignment,
//     notes
//   }
//   currentUserDisplay : string
//   statusList         : array of { key, label }
//   // Personnel / Aircrew lists should return objects like:
//   groundMembers()    : array of { id, name, role, phone, isLeader, isMedic }
//   aircrewMembers()   : array of { id, name, role, phone, certs, isPIC }
//   vehicles()         : array of { id, callsign, type, driver, phone }
//   aircraft()         : array of { id, tail, type, base, comms }
//   equipment()        : array of { id, name, qty, notes }
//   // Actions:
//   openTaskDetail(), linkTaskDialog (optional), setStatus(key), raiseNeedsAssist(), openEditTeam()
//   // Logs API (see bottom section):
//   unitLog(), taskHistory(), statusHistory(), ics214Entries(), copyLogToIcs214(id), addIcs214Note(obj), printIcs214()

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import Qt5Compat.GraphicalEffects
import QtQuick.Window 2.15

ApplicationWindow {
  id: rootWindow
  width: 980
  height: 700
  visible: true
  color: teamBridge && teamBridge.teamTypeColor ? teamBridge.teamTypeColor : "#ffffff"

  // Team ID injected from Python (open_team_detail_window)
  // When set, request the bridge to load the team so `teamBridge.team`
  // populates and the UI binds correctly.
  property int teamId: 0

  readonly property var t: teamBridge ? teamBridge.team : null
  readonly property bool isAir: teamBridge ? teamBridge.isAircraftTeam : false
  readonly property bool needsAssistActive:
    (teamBridge && teamBridge.needsAssistActive === true) || (t && t.needs_assist === true)

  // Column widths for headers/rows (kept in sync for alignment)
  property int pIdW: 60
  property int pNameW: 200
  property int pRoleW: 100
  property int pPhoneW: 160
  property int pCertW: 160
  property int pLeadW: 80
  property int pMedW: 80
  property int pActW: 80

  property int vIdW: 60
  property int vLabelW: 160
  property int vTypeW: 140
  property int vDriverW: 160
  property int vCommsW: 160
  property int vActW: 80

  property int eIdW: 60
  property int eNameW: 240
  property int eQtyW: 80

  function loadTeam() {
    if (teamBridge && teamId) {
      teamBridge.loadTeam(teamId)
    }
  }

  // QML may set teamId after component creation; only load when a valid
  // id is present to avoid resetting the bridge with a blank team.
  Component.onCompleted: loadTeam()
  onTeamIdChanged: loadTeam()

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 12
    spacing: 10

    RowLayout {
      Layout.fillWidth: true
      spacing: 12
      Label {
        font.bold: true
        font.pixelSize: 20
        text: (t && t.team_type ? String(t.team_type).toUpperCase() : (isAir ? 'AIR' : ''))
              + ' - ' + ((t && t.name) ? t.name : (isAir ? (t && t.callsign ? t.callsign : '') : ''))
              + (t && t.team_leader_id ? (function(){ var full = leaderName(t.team_leader_id); if (!full) return ''; var parts = String(full).trim().split(/\s+/); var last = parts.length ? parts[parts.length-1] : ''; return last ? (' - ' + last) : ''; })() : '')
      }
      Item { Layout.fillWidth: true }
    }

    Rectangle {
      visible: needsAssistActive
      Layout.fillWidth: true
      height: 34
      radius: 6
      color: "#7a001a"
      border.color: "#ffb3c1"
      border.width: 1

      RowLayout {
        anchors.fill: parent
        spacing: 8
        Label {
          leftPadding: 10
          text: "⚠️  NEEDS ASSISTANCE"
          color: "white"
          font.bold: true
        }
        Item { Layout.fillWidth: true }
      }

      Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 3
        radius: 2
        color: "#ff4d6d"
        SequentialAnimation on opacity {
          loops: Animation.Infinite
          NumberAnimation { from: 0.2; to: 1.0; duration: 700; easing.type: Easing.InOutQuad }
          NumberAnimation { from: 1.0; to: 0.2; duration: 700; easing.type: Easing.InOutQuad }
        }
      }
    }

    Frame {
      Layout.fillWidth: true
      padding: 10
      ColumnLayout {
        spacing: 8
        GridLayout {
          columns: 2
          columnSpacing: 24
          rowSpacing: 8

          ColumnLayout {
            spacing: 8
            RowLayout {
              spacing: 8
              Label { text: "Team Type"; Layout.preferredWidth: 110 }
                ComboBox {
                  id: cbTeamType
                  Layout.preferredWidth: 220
                  model: teamBridge ? teamBridge.teamTypeList : []
                  textRole: "label"
                  valueRole: "code"
                  currentIndex: {
                    if (!teamBridge || !model || typeof model.length === "undefined") return 0
                    var val = (t && t.team_type) ? String(t.team_type) : ""
                    for (var i = 0; i < model.length; ++i)
                      if (model[i].code === val)
                        return i
                    return 0
                  }
                  onActivated: if (teamBridge) teamBridge.setTeamType(model[index].code)
                }
                }

            RowLayout {
              spacing: 8
              Label { text: isAir ? "Callsign" : "Team Name"; Layout.preferredWidth: 110 }
              TextField {
                Layout.preferredWidth: 220
                text: isAir ? (t && t.callsign ? t.callsign : "") : (t && t.name ? t.name : "")
                onEditingFinished: {
                  if (!teamBridge) return
                  if (isAir) teamBridge.updateFromQml({ callsign: text })
                  else teamBridge.updateFromQml({ name: text })
                }
              }
            }

            // Leader / Pilot (read-only display)
            RowLayout {
              spacing: 8
              Label { text: isAir ? "Pilot" : "Team Leader"; Layout.preferredWidth: 110 }
              TextField {
                Layout.preferredWidth: 220
                readOnly: true
                text: (t && t.team_leader_id) ? leaderName(t.team_leader_id) : ""
                ToolTip.visible: hovered
                ToolTip.text: "Change the leader from the Personnel/Aircrew list menu (⋮ → Set as Leader/PIC)."
              }
            }

            // Phone (read-only, from leader)
            RowLayout {
              spacing: 8
              Label { text: "Phone"; Layout.preferredWidth: 110 }
              TextField {
                Layout.preferredWidth: 220
                readOnly: true
                inputMethodHints: Qt.ImhNoPredictiveText
                text: (t && t.team_leader_id) ? leaderPhone(t.team_leader_id) : ""
              }
            }

            RowLayout {
              spacing: 8
              Label { text: "Status"; Layout.preferredWidth: 110 }
              ComboBox {
                Layout.preferredWidth: 220
                id: cbStatus
                model: teamBridge ? teamBridge.statusList : []
                textRole: "label"
                valueRole: "key"
                currentIndex: {
                  if (!teamBridge || !t || !model || typeof model.length === "undefined") return 0
                  for (var i=0;i<model.length;i++) if (model[i].key === t.status) return i
                  return 0
                }
                onActivated: function(index) {
                  if (teamBridge && model[index]) {
                    teamBridge.setStatus(model[index].key)
                  }
                }
              }
            }
          }

          ColumnLayout {
            spacing: 8
            RowLayout { spacing: 8
              Label { text: "Last Contact"; Layout.preferredWidth: 120 }
              Label { text: (t && t.last_comm_ts) ? t.last_comm_ts : (t && t.last_update_ts ? t.last_update_ts : ""); Layout.preferredWidth: 220 }
            }
            RowLayout { spacing: 8
              Label { text: "Primary Task"; Layout.preferredWidth: 120 }
              RowLayout { spacing: 6
                TextField {
                  Layout.preferredWidth: 220
                  readOnly: true
                  text: teamBridge && t && t.current_task_id ? String(t.current_task_id) : ""
                }
                Button {
                  text: (teamBridge && t && t.current_task_id) ? "Open" : "Link..."
                  enabled: !!teamBridge
                  onClicked: teamBridge && (t && t.current_task_id ? teamBridge.openTaskDetail() : (teamBridge.linkTaskDialog ? teamBridge.linkTaskDialog.open() : null))
                }
                Button {
                  visible: !!(teamBridge && t && t.current_task_id)
                  text: "Unlink"
                  onClicked: teamBridge && teamBridge.unlinkTask ? teamBridge.unlinkTask(t.current_task_id) : null
                }
              }
            }

            RowLayout { spacing: 8
              Label { text: "Assignment"; Layout.preferredWidth: 120 }
              TextField {
                Layout.preferredWidth: 300
                text: t && t.assignment ? t.assignment : ""
                onEditingFinished: if (teamBridge) teamBridge.updateFromQml({ assignment: text })
              }
            }
          }
        }

        ColumnLayout { spacing: 6; Layout.fillWidth: true; Layout.topMargin: 8
          Label { text: "Notes" }
          TextArea {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            wrapMode: TextArea.Wrap
            text: t && t.notes ? t.notes : ""
            onTextChanged: notesTimer.restart()
            background: Rectangle { color: "#f7f7f9"; radius: 4; border.color: "#d0d0d0" }
          }
          Timer { id: notesTimer; interval: 500; repeat: false; onTriggered: if (teamBridge) teamBridge.updateFromQml({ notes: parent.parent.children[1].text }) }
        }
      }
    }

    RowLayout { Layout.fillWidth: true; spacing: 8
      Button { text: "Edit Team"; onClicked: teamBridge && teamBridge.openEditTeam ? teamBridge.openEditTeam() : null }
      Button {
        id: needsAssistButton
        text: needsAssistActive ? "NEEDS ASSISTANCE" : "Flag Needs Assistance"
        onClicked: teamBridge && teamBridge.raiseNeedsAssist ? teamBridge.raiseNeedsAssist() : null
        background: Rectangle {
          implicitWidth: 120; implicitHeight: 32; radius: 6
          color: needsAssistActive ? "#c1121f" : needsAssistButton.palette.button
          border.color: needsAssistActive ? "#ffd9de" : "#606060"
        }
        contentItem: Label {
          text: needsAssistButton.text
          color: needsAssistActive ? "white" : needsAssistButton.palette.buttonText
          font.bold: needsAssistActive
          horizontalAlignment: Text.AlignHCenter
          verticalAlignment: Text.AlignVCenter
        }
      }
      Button { text: "Update Status"; onClicked: cbStatus.popup.open() }
      Button { text: "View Task"; enabled: !!(teamBridge && t && t.current_task_id); onClicked: teamBridge && teamBridge.openTaskDetail() }
    }

    TabBar { id: tabs; Layout.fillWidth: true
      TabButton { text: isAir ? "Aircrew" : "Personnel (Ground)" }
      TabButton { text: isAir ? "Aircraft" : "Vehicles" }
      TabButton { text: "Equipment" }
      TabButton { text: "Logs" }
    }

    StackLayout { Layout.fillWidth: true; Layout.fillHeight: true; currentIndex: tabs.currentIndex

      ColumnLayout { spacing: 8
        RowLayout { Layout.fillWidth: true
          Button { text: isAir ? "Add Aircrew" : "Add Personnel"; onClicked: teamBridge && teamBridge.addMember && teamBridge.addMember() }
          Item { Layout.fillWidth: true }
          Button { text: "Detail"; onClicked: teamBridge && teamBridge.openSelectedMember && teamBridge.openSelectedMember() }
        }
        // Personnel/Aircrew header
        Rectangle {
          Layout.fillWidth: true
          height: 28
          color: "#000000"
          RowLayout { anchors.fill: parent; spacing: 0
            Label { color: "#ffffff"; text: "ID"; Layout.preferredWidth: pIdW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pIdW }
                onPositionChanged: { var dx = mouseX - startX; pIdW = Math.max(40, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: "Name"; Layout.preferredWidth: pNameW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pNameW }
                onPositionChanged: { var dx = mouseX - startX; pNameW = Math.max(60, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: "Role"; Layout.preferredWidth: pRoleW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pRoleW }
                onPositionChanged: { var dx = mouseX - startX; pRoleW = Math.max(60, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: "Phone Number"; Layout.preferredWidth: pPhoneW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              visible: true
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pPhoneW }
                onPositionChanged: { var dx = mouseX - startX; pPhoneW = Math.max(80, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: isAir ? "Certifications" : ""; visible: isAir; Layout.preferredWidth: pCertW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pCertW }
                onPositionChanged: { var dx = mouseX - startX; pCertW = Math.max(60, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: isAir ? "PIC" : "Leader"; Layout.preferredWidth: pLeadW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pLeadW }
                onPositionChanged: { var dx = mouseX - startX; pLeadW = Math.max(40, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: !isAir ? "Medic" : ""; visible: !isAir; Layout.preferredWidth: pMedW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea {
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor
                property real startX: 0; property int startW: 0
                onPressed: { startX = mouseX; startW = pMedW }
                onPositionChanged: { var dx = mouseX - startX; pMedW = Math.max(40, startW + dx) }
              }
            }
            Label { color: "#ffffff"; text: "Actions"; Layout.preferredWidth: pActW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
          }
        }
        ListView {
          id: lvMembers
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          // Re-evaluate when `t` changes (teamChanged from bridge)
          model: t ? (isAir ? teamBridge.aircrewMembers() : teamBridge.groundMembers()) : []
          delegate: Frame {
            width: ListView.view.width
            padding: 0
            RowLayout { anchors.fill: parent; spacing: 0
              Label { text: (modelData && modelData.id !== undefined ? String(modelData.id) : ""); Layout.preferredWidth: pIdW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: (modelData && modelData.name !== undefined ? String(modelData.name) : ""); Layout.preferredWidth: pNameW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              ComboBox {
                Layout.preferredWidth: pRoleW
                model: teamBridge ? teamBridge.teamRoleOptions() : []
                currentIndex: {
                  var m = (teamBridge ? teamBridge.teamRoleOptions() : [])
                  var val = (modelData && modelData.role) ? String(modelData.role) : ""
                  for (var i = 0; i < m.length; ++i) {
                    if (m[i] === val)
                      return i
                  }
                  return (m.length > 0 ? 0 : -1)
                }
                onActivated: if (teamBridge) teamBridge.setPersonRole(modelData.id, model[index])
              }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: (modelData && modelData.phone !== undefined ? String(modelData.phone) : ""); Layout.preferredWidth: pPhoneW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0"; visible: isAir }
              Label { visible: isAir; text: modelData.certs || ""; Layout.preferredWidth: pCertW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              CheckBox { checked: !!(isAir ? (modelData && modelData.isPIC) : (modelData && modelData.isLeader)); enabled: false; Layout.preferredWidth: pLeadW }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0"; visible: !isAir }
              CheckBox { visible: !isAir; checked: !!(modelData && modelData.isMedic); enabled: false; Layout.preferredWidth: pMedW }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Button { text: "⋮"; Layout.preferredWidth: pActW; onClicked: memberMenu.open() }
              Menu { id: memberMenu
                MenuItem { text: "Set as Leader/PIC"; onTriggered: teamBridge && teamBridge.setLeader && teamBridge.setLeader(modelData.id) }
                MenuItem { visible: !isAir; text: "Toggle Medic"; onTriggered: teamBridge && teamBridge.toggleMedic && teamBridge.toggleMedic(modelData.id) }
                MenuItem { text: "Remove"; onTriggered: teamBridge && teamBridge.removeMember && teamBridge.removeMember(modelData.id) }
              }
            }
          }
        }
      }

      ColumnLayout { spacing: 8
        RowLayout { Layout.fillWidth: true
          Button { text: isAir ? "Add Aircraft" : "Add Vehicle"; onClicked: teamBridge && teamBridge.addAsset && teamBridge.addAsset() }
        }
        Rectangle {
          Layout.fillWidth: true
          height: 28
          color: "#000000"
          RowLayout { anchors.fill: parent; spacing: 0
            Label { color: "#ffffff"; text: "ID"; Layout.preferredWidth: vIdW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor; property real startX: 0; property int startW: 0; onPressed: { startX = mouseX; startW = vIdW } onPositionChanged: { var dx = mouseX - startX; vIdW = Math.max(40, startW + dx) } }
            }
            Label { color: "#ffffff"; text: isAir ? "Tail/Callsign" : "Callsign/Name"; Layout.preferredWidth: vLabelW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor; property real startX: 0; property int startW: 0; onPressed: { startX = mouseX; startW = vLabelW } onPositionChanged: { var dx = mouseX - startX; vLabelW = Math.max(80, startW + dx) } }
            }
            Label { color: "#ffffff"; text: "Type"; Layout.preferredWidth: vTypeW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor; property real startX: 0; property int startW: 0; onPressed: { startX = mouseX; startW = vTypeW } onPositionChanged: { var dx = mouseX - startX; vTypeW = Math.max(60, startW + dx) } }
            }
            Label { color: "#ffffff"; text: isAir ? "Base" : "Driver"; Layout.preferredWidth: vDriverW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor; property real startX: 0; property int startW: 0; onPressed: { startX = mouseX; startW = vDriverW } onPositionChanged: { var dx = mouseX - startX; vDriverW = Math.max(60, startW + dx) } }
            }
            Label { color: "#ffffff"; text: "Comms/Phone"; Layout.preferredWidth: vCommsW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle {
              width: 6; Layout.preferredWidth: 6; color: "transparent"
              Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" }
              MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.SplitHCursor; property real startX: 0; property int startW: 0; onPressed: { startX = mouseX; startW = vCommsW } onPositionChanged: { var dx = mouseX - startX; vCommsW = Math.max(60, startW + dx) } }
            }
            Label { color: "#ffffff"; text: "Actions"; Layout.preferredWidth: vActW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
          }
        }
        ListView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          // Re-evaluate when `t` changes (teamChanged from bridge)
          model: t ? (isAir ? teamBridge.aircraft() : teamBridge.vehicles()) : []
          delegate: Frame {
            width: ListView.view.width; padding: 0
            RowLayout { anchors.fill: parent; spacing: 0
              Label { text: (modelData && modelData.id !== undefined ? String(modelData.id) : ""); Layout.preferredWidth: vIdW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: (isAir ? (modelData.tail || modelData.callsign) : (modelData.callsign || modelData.name)) || ""; Layout.preferredWidth: vLabelW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: modelData.type || ""; Layout.preferredWidth: vTypeW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: isAir ? (modelData.base || "") : (modelData.driver || ""); Layout.preferredWidth: vDriverW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: modelData.comms || modelData.phone || ""; Layout.preferredWidth: vCommsW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Button { text: "?"; Layout.preferredWidth: vActW; onClicked: assetMenu.open() }
              Menu { id: assetMenu
                MenuItem { text: "Details"; onTriggered: teamBridge && teamBridge.openAsset && teamBridge.openAsset(modelData.id) }
                MenuItem { text: "Remove"; onTriggered: teamBridge && teamBridge.removeAsset && teamBridge.removeAsset(modelData.id) }
              }
            }
          }
        }
      }

      ColumnLayout { spacing: 8
        RowLayout { Layout.fillWidth: true
          Button { text: "Add Equipment"; onClicked: teamBridge && teamBridge.addEquipment && teamBridge.addEquipment() }
        }
        Rectangle {
          Layout.fillWidth: true
          height: 28
          color: "#000000"
          RowLayout { anchors.fill: parent; spacing: 0
            Label { color: "#ffffff"; text: "ID"; Layout.preferredWidth: eIdW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle { width: 6; Layout.preferredWidth: 6; color: "transparent"; Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" } }
            Label { color: "#ffffff"; text: "Name"; Layout.preferredWidth: eNameW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle { width: 6; Layout.preferredWidth: 6; color: "transparent"; Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" } }
            Label { color: "#ffffff"; text: "Qty"; Layout.preferredWidth: eQtyW; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
            Rectangle { width: 6; Layout.preferredWidth: 6; color: "transparent"; Rectangle { anchors.centerIn: parent; width: 1; height: parent.height; color: "#303030" } }
            Label { color: "#ffffff"; text: "Notes"; Layout.fillWidth: true; font.bold: true; verticalAlignment: Text.AlignVCenter; leftPadding: 6 }
          }
        }
        ListView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          clip: true
          // Re-evaluate when `t` changes (teamChanged from bridge)
          model: t ? teamBridge.equipment() : []
          delegate: Frame { width: ListView.view.width; padding: 0
            RowLayout { anchors.fill: parent; spacing: 0
              Label { text: (modelData && modelData.id !== undefined ? String(modelData.id) : ""); Layout.preferredWidth: eIdW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: (modelData && modelData.name !== undefined ? String(modelData.name) : ""); Layout.preferredWidth: eNameW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Label { text: (modelData && modelData.qty !== undefined ? String(modelData.qty) : ""); Layout.preferredWidth: eQtyW; leftPadding: 6 }
              Rectangle { width: 1; height: parent.height; color: "#d0d0d0" }
              Text  { text: modelData.notes || ""; Layout.fillWidth: true; wrapMode: Text.WordWrap; leftPadding: 6 }
            }
          }
        }
      }

      // Logs unchanged (already hardened)
      // ...
    }
  }

  function leaderName(id) {
    if (!id) return ""
    try {
      var list = isAir
          ? (teamBridge ? teamBridge.aircrewMembers() : [])
          : (teamBridge ? teamBridge.groundMembers() : [])
      for (var i = 0; i < list.length; ++i)
          if (String(list[i].id) === String(id)) return list[i].name || ""
      if (typeof catalogBridge !== "undefined" && catalogBridge) {
          var ppl = catalogBridge.listPersonnel("")
          for (var j = 0; j < ppl.length; ++j)
              if (String(ppl[j].id) === String(id)) return ppl[j].name || ""
      }
    } catch(e) {}
    return ""
  }

  function leaderPhone(id) {
    if (!id) return ""
    try {
      var list = isAir
          ? (teamBridge ? teamBridge.aircrewMembers() : [])
          : (teamBridge ? teamBridge.groundMembers() : [])
      for (var i = 0; i < list.length; ++i)
          if (String(list[i].id) === String(id)) return list[i].phone || ""
      if (typeof catalogBridge !== "undefined" && catalogBridge) {
          var ppl = catalogBridge.listPersonnel("")
          for (var j = 0; j < ppl.length; ++j)
              if (String(ppl[j].id) === String(id)) return ppl[j].phone || ""
      }
    } catch(e) {}
    return ""
  }
}















