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
                ToolButton { text: "Add from Template" }
                ToolButton { text: "Save as Template" }
                ToolButton { text: "Undo" }
                ToolButton { text: "Swap Template" }
                ToolButton { text: "Export ICS-203" }
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
                    ListView {
                        id: positionsView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: ["Incident Commander", "Safety Officer", "Public Information Officer", "Liaison Officer", "Operations Section Chief"]
                        delegate: CheckBox { text: modelData }
                    }
                }
            }

            Frame {
                SplitView.fillWidth: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4
                    Label { text: "Org Chart"; font.bold: true }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: ["Incident Commander: (vacant)", "PIO: Jane Smith", "Safety: (vacant)"]
                        delegate: Label { text: modelData; padding: 4 }
                    }
                }
            }

            Frame {
                SplitView.preferredWidth: 220
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4
                    Label { text: "Personnel Pool"; font.bold: true }
                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: ["Jane Smith", "John Doe", "Mary Johnson"]
                        delegate: Label { text: modelData; padding: 4 }
                    }
                }
            }
        }
    }
}
