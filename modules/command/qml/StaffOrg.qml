import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        ToolBar {
            Layout.fillWidth: true
            RowLayout {
                anchors.fill: parent
                spacing: 8
                ToolButton {
                    text: "Add from Template"
                    onClicked: console.log("Add from Template clicked")
                }
                ToolButton {
                    text: "Save as Template"
                    onClicked: console.log("Save as Template clicked")
                }
                ToolButton {
                    text: "Undo"
                    onClicked: console.log("Undo clicked")
                }
                ToolButton {
                    text: "Swap Template"
                    onClicked: console.log("Swap Template clicked")
                }
                ToolButton {
                    text: "Export ICS-203"
                    onClicked: console.log("Export ICS-203 clicked")
                }
            }
        }

        SplitView {
            id: split
            Layout.fillWidth: true
            Layout.fillHeight: true

            Frame {
                SplitView.preferredWidth: 220
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4
                    Label { text: "Positions"; font.bold: true }
                    ListModel {
                        id: positionsModel
                        ListElement { title: "Incident Commander" }
                        ListElement { title: "Safety Officer" }
                        ListElement { title: "Public Information Officer" }
                        ListElement { title: "Liaison Officer" }
                        ListElement { title: "Operations Section Chief" }
                    }
                    ListView {
                        id: positionsView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: positionsModel
                        delegate: CheckBox { text: title }
                    }
                }
            }

            Frame {
                SplitView.fillWidth: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4
                    Label { text: "Org Chart"; font.bold: true }
                    ListModel {
                        id: orgModel
                        ListElement { entry: "Incident Commander: (vacant)" }
                        ListElement { entry: "PIO: Jane Smith" }
                        ListElement { entry: "Safety: (vacant)" }
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: orgModel
                        delegate: Label { text: entry; padding: 4 }
                    }
                }
            }

            Frame {
                SplitView.preferredWidth: 220
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4
                    Label { text: "Personnel Pool"; font.bold: true }
                    ListModel {
                        id: personnelModel
                        ListElement { name: "Jane Smith" }
                        ListElement { name: "John Doe" }
                        ListElement { name: "Mary Johnson" }
                    }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: personnelModel
                        delegate: Label { text: name; padding: 4 }
                    }
                }
            }
        }
    }
}
