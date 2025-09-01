import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    anchors.fill: parent

    // Injected from Python
    property string panelTitle: panelTitle || ""
    property string panelBody: panelBody || ""

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        Label {
            text: root.panelTitle
            font.bold: true
            font.pointSize: 14
        }
        TextArea {
            text: root.panelBody
            readOnly: true
            wrapMode: Text.WordWrap
            background: Rectangle { color: "transparent"; border.color: "#ccc"; radius: 6 }
        }
    }
}

