import QtQuick 6.5
import QtQuick.Controls 6.5
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 1000; height: 600

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ToolBar {
            Layout.fillWidth: true
            Row {
                spacing: 6
                ToolButton { text: "Validate"; onClicked: ics205.runValidation() }
                ToolButton { text: "Close"; onClicked: root.Window.window.close() }
            }
        }

        SplitView {
            id: split
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Master list -------------------------------------------------
            ListView {
                id: masterList
                model: ics205.masterModel
                clip: true
                width: 200
                header: TextField {
                    placeholderText: "Search"
                    onTextChanged: ics205.setFilter("search", text)
                }
                delegate: ItemDelegate {
                    width: ListView.view.width
                    text: model.display_name
                    onDoubleClicked: ics205.addMasterIdToPlan(model.id)
                }
            }

        // Plan table --------------------------------------------------
            Column {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // Header
                Row {
                    id: header
                    spacing: 0
                    Layout.fillWidth: true
                    height: 30
                    Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Chan" } }
                    Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Function" } }
                    Rectangle { width: 80;  height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Div" } }
                    Rectangle { width: 80;  height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Team" } }
                    Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "RX" } }
                    Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "TX" } }
                    Rectangle { width: 80;  height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Mode" } }
                    Rectangle { width: 80;  height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Band" } }
                    Rectangle { Layout.fillWidth: true; height: parent.height; color: "#333"; border.color: "#555" }
                }

                // Rows
                ListView {
                    id: planList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: ics205.planModel
                    currentIndex: -1
                    delegate: MouseArea {
                        hoverEnabled: true
                        onClicked: planList.currentIndex = index
                        height: 28
                        width: parent ? parent.width : 0
                        Row {
                            anchors.fill: parent
                            spacing: 0
                            Rectangle { width: 100; height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#111"; text: model.channel || "" } }
                            Rectangle { width: 120; height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.function || "" } }
                            Rectangle { width: 80;  height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.assignment_division || "" } }
                            Rectangle { width: 80;  height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.assignment_team || "" } }
                            Rectangle { width: 100; height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.rx_freq || "" } }
                            Rectangle { width: 100; height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.tx_freq || "" } }
                            Rectangle { width: 80;  height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.mode || "" } }
                            Rectangle { width: 80;  height: parent.height; color: index === planList.currentIndex ? "#d0eaff" : (index % 2 ? "#232323" : "#1e1e1e"); border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.band || "" } }
                            Rectangle { Layout.fillWidth: true; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
                        }
                    }
                }
            }
        }

        // Status line ----------------------------------------------------
        Label {
            Layout.fillWidth: true
            text: ics205.statusLine
            padding: 4
        }

        // Bottom editor ---------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            color: "#f0f0f0"
            height: 120

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 4

                Row {
                    spacing: 6
                    Label { text: "Channel:" }
                    TextField {
                        width: 150
                        text: ics205.getPlanRow(planList.currentIndex).channel || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "channel", text)
                    }
                    Label { text: "Function:" }
                    TextField {
                        width: 120
                        text: ics205.getPlanRow(planList.currentIndex).function || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "function", text)
                    }
                    Label { text: "Division:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planList.currentIndex).assignment_division || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "assignment_division", text)
                    }
                    Label { text: "Team:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planList.currentIndex).assignment_team || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "assignment_team", text)
                    }
                }

                Row {
                    spacing: 6
                    Label { text: "RX:" }
                    TextField {
                        width: 100
                        text: ics205.getPlanRow(planList.currentIndex).rx_freq || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "rx_freq", parseFloat(text))
                    }
                    Label { text: "TX:" }
                    TextField {
                        width: 100
                        text: ics205.getPlanRow(planList.currentIndex).tx_freq || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "tx_freq", parseFloat(text))
                    }
                    Label { text: "Mode:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planList.currentIndex).mode || ""
                        onEditingFinished: ics205.updatePlanCell(planList.currentIndex, "mode", text)
                    }
                    CheckBox {
                        text: "Include on 205"
                        checked: ics205.getPlanRow(planList.currentIndex).include_on_205 || false
                        onToggled: ics205.updatePlanCell(planList.currentIndex, "include_on_205", checked ? 1 : 0)
                    }
                }
            }
        }
    }
}
