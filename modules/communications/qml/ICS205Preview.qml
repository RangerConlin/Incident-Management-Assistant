import QtQuick 6.5
import QtQuick.Controls 6.5
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 800; height: 600

    signal back()
    signal exportPdf()
    signal printRequested()
    signal closeRequested()

    ListModel { id: previewModel }

    Component.onCompleted: {
        var rows = ics205.getPreviewRows();
        for (var i = 0; i < rows.length; ++i) {
            previewModel.append(rows[i]);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Header
            Row {
                id: header
                spacing: 0
                Layout.fillWidth: true
                height: 30
                Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Function" } }
                Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Channel" } }
                Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Assignment" } }
                Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "RX" } }
                Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "TX" } }
                Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Tone/NAC" } }
                Rectangle { width: 80;  height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Mode" } }
                Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Encryption" } }
                Rectangle { width: 160; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "#fff"; text: "Notes" } }
                Rectangle { Layout.fillWidth: true; height: parent.height; color: "#333"; border.color: "#555" }
            }

            // Rows
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: previewModel
                delegate: Row {
                    spacing: 0
                    height: 28
                    Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.Function } }
                    Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.Channel } }
                    Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.Assignment } }
                    Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.RX } }
                    Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.TX } }
                    Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.ToneNAC } }
                    Rectangle { width: 80;  height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.Mode } }
                    Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.Encryption } }
                    Rectangle { width: 160; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.Notes } }
                    Rectangle { Layout.fillWidth: true; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
                }
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight
            spacing: 6
            Button { text: "Back"; onClicked: root.back() }
            Button { text: "Export PDF"; onClicked: root.exportPdf() }
            Button { text: "Print"; onClicked: root.printRequested() }
            Button { text: "Close"; onClicked: root.closeRequested() }
        }
    }
}
