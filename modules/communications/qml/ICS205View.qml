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
            TableView {
                id: planView
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: ics205.planModel
                clip: true
                selectionModel: ItemSelectionModel {}
                columnSpacing: 1
                rowSpacing: 1

                delegate: Rectangle {
                    implicitHeight: 28
                    color: (planView.selectionModel.currentIndex.row === row && planView.selectionModel.currentIndex.column === column) ? "#d0eaff" : "transparent"
                    border.color: "#cccccc"
                    Text {
                        anchors.centerIn: parent
                        text: model.display || model[planView.columns[column].role] || ""
                    }
                }

                columns: [
                    TableViewColumn { role: "channel"; title: "Chan"; width: 100 },
                    TableViewColumn { role: "function"; title: "Function"; width: 120 },
                    TableViewColumn { role: "assignment_division"; title: "Div"; width: 80 },
                    TableViewColumn { role: "assignment_team"; title: "Team"; width: 80 },
                    TableViewColumn { role: "rx_freq"; title: "RX"; width: 100 },
                    TableViewColumn { role: "tx_freq"; title: "TX"; width: 100 },
                    TableViewColumn { role: "mode"; title: "Mode"; width: 80 },
                    TableViewColumn { role: "band"; title: "Band"; width: 80 }
                ]
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
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).channel || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "channel", text)
                    }
                    Label { text: "Function:" }
                    TextField {
                        width: 120
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).function || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "function", text)
                    }
                    Label { text: "Division:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).assignment_division || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "assignment_division", text)
                    }
                    Label { text: "Team:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).assignment_team || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "assignment_team", text)
                    }
                }

                Row {
                    spacing: 6
                    Label { text: "RX:" }
                    TextField {
                        width: 100
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).rx_freq || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "rx_freq", parseFloat(text))
                    }
                    Label { text: "TX:" }
                    TextField {
                        width: 100
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).tx_freq || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "tx_freq", parseFloat(text))
                    }
                    Label { text: "Mode:" }
                    TextField {
                        width: 80
                        text: ics205.getPlanRow(planView.selectionModel.currentIndex.row).mode || ""
                        onEditingFinished: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "mode", text)
                    }
                    CheckBox {
                        text: "Include on 205"
                        checked: ics205.getPlanRow(planView.selectionModel.currentIndex.row).include_on_205 || false
                        onToggled: ics205.updatePlanCell(planView.selectionModel.currentIndex.row, "include_on_205", checked ? 1 : 0)
                    }
                }
            }
        }
    }
}
