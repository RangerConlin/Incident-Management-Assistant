// modules/planning/qml/IncidentObjectives.qml
// Clean split layout: left list | right detail, no TabView/RowLayout. Qt6/PySide6-safe.

import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    id: root
    anchors.fill: parent

    // Provided by Python:
    // contextProperty("objectiveBridge", ObjectiveBridge)
    property int selectedObjectiveId: -1

    // ===== HEADER =====
    Column {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 8
        padding: 8

        Row {
            spacing: 8
            ComboBox { id: statusTop;   width: 180; model: ["All","Pending","Approved","Assigned","In Progress","Completed","Cancelled"] }
            ComboBox { id: priorityTop; width: 180; model: ["All","Low","Normal","High","Urgent"] }
            ComboBox { id: sectionTop;  width: 180; model: ["All","Command","Planning","Operations","Logistics","Comms","Medical","Intel","Liaison"] }
            Button {
                text: "Refresh"
                onClicked: objectiveBridge.loadObjectives(statusTop.currentText, priorityTop.currentText, sectionTop.currentText)
            }
        }

        Row {
            spacing: 8
            TextField { id: customerFilter; width: 200; placeholderText: "Customer" }
            TextField { id: search;         width: 280; placeholderText: "Search description…" }
            ComboBox  { id: quickPrio;     width: 160; model: ["Normal","Low","High","Urgent"]; currentIndex: 0 }
            Button {
                text: "Add"
                onClicked: if (search.text.length>0) {
                    objectiveBridge.createObjective(search.text, quickPrio.currentText, 1)
                    search.clear()
                }
            }
        }
    }

    // ===== MAIN SPLIT =====
    SplitView {
        id: split
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        orientation: Qt.Horizontal

        // ---- LEFT: LIST ----
        Pane {
            id: leftPane
            SplitView.preferredWidth: Math.max(520, root.width * 0.45)
            SplitView.minimumWidth: 420
            padding: 0
            clip: true

            Column {
                id: leftCol
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    id: listHeader
                    width: parent.width
                    height: 36
                    color: Qt.darker(palette.window, 1.2)
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left; anchors.leftMargin: 12
                        text: "Incident Objectives (ICS 202)"
                        font.bold: true
                    }
                }

                ScrollView {
                    id: listScroll
                    width: parent.width
                    height: parent.height - listHeader.height
                    clip: true

                    ListView {
                        id: listView
                        width: parent.width
                        height: parent.height
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: objectiveBridge.objectivesModel

                        delegate: Rectangle {
                            width: listView.width
                            height: 44
                            color: (root.selectedObjectiveId === model.id) ? Qt.darker(palette.highlight, 1.3) : "transparent"
                            border.color: "#333"
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    root.selectedObjectiveId = model.id
                                    objectiveBridge.loadObjectiveDetail(model.id)
                                }
                            }
                            Row {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 12
                                Text { text: model.code; width: 56 }
                                Text { text: "• " + model.status;   width: 110; elide: Text.ElideRight }
                                Text { text: "• " + model.priority; width: 90;  elide: Text.ElideRight }
                                Text { text: "• " + (model.customer || ""); width: 260; elide: Text.ElideRight }
                                Text { text: "• Due: " + (model.due || "—"); elide: Text.ElideRight }
                            }
                        }
                    }
                }
            }
        }

        // ---- RIGHT: DETAIL ----
        Pane {
            id: rightPane
            SplitView.preferredWidth: Math.max(520, root.width * 0.55)
            SplitView.minimumWidth: 420
            padding: 0
            clip: true

            Column {
                anchors.fill: parent
                spacing: 8
                padding: 8

                Row {
                    id: titleRow
                    spacing: 8
                    Label { text: root.selectedObjectiveId > 0 ? ("#" + root.selectedObjectiveId) : "No selection"; font.pixelSize: 18; font.bold: true }
                    Item { width: 8; height: 1 }
                    Button { text: "Approve"; enabled: root.selectedObjectiveId>0; onClicked: objectiveBridge.changeStatus(root.selectedObjectiveId, "Approved") }
                    Button { text: "Reject";  enabled: root.selectedObjectiveId>0; onClicked: objectiveBridge.changeStatus(root.selectedObjectiveId, "Cancelled") }
                }

                Row {
                    id: seg
                    spacing: 6
                    property int index: 0
                    function set(i){ index = i; stack.currentIndex = i }
                    Button { text: "Narrative";    onClicked: seg.set(0) }
                    Button { text: "Strategies";   onClicked: seg.set(1) }
                    Button { text: "Linked Tasks"; onClicked: seg.set(2) }
                    Button { text: "Approvals";    onClicked: seg.set(3) }
                    Button { text: "Customer";     onClicked: seg.set(4) }
                    Button { text: "Log";          onClicked: seg.set(5) }
                }

                StackView {
                    id: stack
                    width: parent.width
                    height: parent.height - (titleRow.height + seg.height + 16)
                    clip: true
                    initialItem: narrativePage

                    // ===== Narrative =====
                    Component {
                        id: narrativePage
                        ScrollView {
                            clip: true
                            Column {
                                width: parent.width
                                spacing: 8
                                Row {
                                    spacing: 6
                                    TextField { id: narInput; placeholderText: "Add narrative…"; width: Math.min(560, parent.width - 170) }
                                    CheckBox { id: narCrit; text: "Critical" }
                                    Button {
                                        text: "Add"
                                        enabled: root.selectedObjectiveId>0 && narInput.text.length>0
                                        onClicked: {
                                            objectiveBridge.addNarrative(root.selectedObjectiveId, narInput.text, narCrit.checked)
                                            narInput.clear(); narCrit.checked = false
                                        }
                                    }
                                }
                                ListView {
                                    clip: true
                                    height: Math.max(200, parent.height - 64)
                                    model: objectiveBridge.narrativeModel
                                    delegate: Rectangle {
                                        width: parent.width
                                        height: implicitHeight
                                        color: (critical === 1 || critical === true) ? "#ffe5e5" : "transparent"
                                        Column {
                                            anchors.margins: 8; anchors.fill: parent; spacing: 2
                                            Text {
                                                // Format ts as MM-DD-YY HH:MM:SS
                                                text: (function(){
                                                    function pad(n){ return (n<10?('0'+n):String(n)); }
                                                    try {
                                                        var s = String(ts);
                                                        var dot = s.indexOf('.');
                                                        if (dot > 0) {
                                                            var tz = '';
                                                            var tzStart = s.indexOf('Z', dot) >= 0 ? s.indexOf('Z', dot) : s.indexOf('+', dot);
                                                            if (tzStart > 0) { tz = s.substring(tzStart); s = s.substring(0, tzStart); }
                                                            s = s.substring(0, dot) + tz;
                                                        }
                                                        var d = new Date(s);
                                                        if (isNaN(d.getTime())) return (ts + " • " + user);
                                                        var mm = pad(d.getUTCMonth()+1);
                                                        var dd = pad(d.getUTCDate());
                                                        var yy = String(d.getUTCFullYear()).slice(-2);
                                                        var HH = pad(d.getUTCHours());
                                                        var MM = pad(d.getUTCMinutes());
                                                        var SS = pad(d.getUTCSeconds());
                                                        return (mm + '-' + dd + '-' + yy + ' ' + HH + ':' + MM + ':' + SS + ' • ' + user);
                                                    } catch(e) { return (ts + " • " + user); }
                                                })()
                                                font.pixelSize: 12; opacity: 0.8
                                            }
                                            Text { text: text; wrapMode: Text.Wrap }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ===== Strategies =====
                    Component {
                        id: strategiesPage
                        ScrollView {
                            clip: true
                            Column {
                                spacing: 8
                                Row {
                                    spacing: 6
                                    TextField { id: stratInput; placeholderText: "Add strategy…"; width: Math.min(560, parent.width - 110) }
                                    Button {
                                        text: "Add"
                                        enabled: root.selectedObjectiveId>0 && stratInput.text.length>0
                                        onClicked: {
                                            objectiveBridge.addStrategy(root.selectedObjectiveId, stratInput.text)
                                            stratInput.clear()
                                        }
                                    }
                                }
                                ListView {
                                    clip: true
                                    height: Math.max(200, parent.height - 64)
                                    model: objectiveBridge.strategiesModel
                                    delegate: Rectangle {
                                        width: parent.width
                                        height: 42
                                        color: "transparent"
                                        Row {
                                            anchors.fill: parent; anchors.margins: 8; spacing: 8
                                            Text { text: text; elide: Text.ElideRight; width: parent.width - 24 }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ===== Linked Tasks =====
                    Component {
                        id: tasksPage
                        ScrollView {
                            clip: true
                            ListView {
                                clip: true
                                model: objectiveBridge.linkedTasksModel
                                delegate: Rectangle {
                                    width: parent.width
                                    height: 40
                                    Row {
                                        anchors.fill: parent; anchors.margins: 8; spacing: 12
                                        Text { text: id; width: 70 }
                                        Text { text: summary; width: 280; elide: Text.ElideRight }
                                        Text { text: team; width: 160; elide: Text.ElideRight }
                                        Text { text: status; width: 120 }
                                    }
                                }
                            }
                        }
                    }

                    // ===== Approvals =====
                    Component {
                        id: approvalsPage
                        ScrollView {
                            clip: true
                            Column {
                                spacing: 8
                                Row {
                                    spacing: 6
                                    TextField { id: apprNote; placeholderText: "Optional note…"; width: Math.min(560, parent.width - 170) }
                                    Button { text: "Approve"; enabled: root.selectedObjectiveId>0; onClicked: objectiveBridge.changeStatus(root.selectedObjectiveId, "Approved") }
                                    Button { text: "Reject";  enabled: root.selectedObjectiveId>0; onClicked: objectiveBridge.changeStatus(root.selectedObjectiveId, "Cancelled") }
                                }
                                ListView {
                                    clip: true
                                    height: Math.max(200, parent.height - 64)
                                    model: objectiveBridge.approvalsModel
                                    delegate: Rectangle {
                                        width: parent.width
                                        height: implicitHeight
                                        Column {
                                            anchors.margins: 8; anchors.fill: parent; spacing: 2
                                            Text { text: ts + " • " + user; font.pixelSize: 12; opacity: 0.8 }
                                            Text { text: action + (note && note.length>0 ? (": " + note) : ""); wrapMode: Text.Wrap }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ===== Customer =====
                    Component {
                        id: customerPage
                        ScrollView {
                            clip: true
                            Column {
                                width: parent.width
                                spacing: 8
                                // Bind to your model fields when available
                                Text { text: "Customer details bound to model fields…" }
                            }
                        }
                    }

                    // ===== Log =====
                    Component {
                        id: logPage
                        ScrollView {
                            clip: true
                            ListView {
                                clip: true
                                model: objectiveBridge.logModel
                                delegate: Rectangle {
                                    width: parent.width
                                    height: implicitHeight
                                    Column {
                                        anchors.fill: parent; anchors.margins: 8; spacing: 2
                                        Text { text: ts + " • " + user + " • " + type; font.pixelSize: 12; opacity: 0.8 }
                                        Text { text: text; wrapMode: Text.Wrap }
                                        Text { text: details; wrapMode: Text.Wrap; visible: details && details.length>0; opacity: 0.8 }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Initial load
    Component.onCompleted: objectiveBridge.loadObjectives("All","All","All")
}
