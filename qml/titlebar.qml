import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: parent.width
    height: 40
    color: "#2b2f3a"

    property var window  // Set from Python to enable close action

    RowLayout {
        anchors.fill: parent
        anchors.margins: 10

        Text {
            text: "SARApp"
            color: "white"
            font.bold: true
            font.pixelSize: 16
            Layout.alignment: Qt.AlignVCenter
        }

        Item { Layout.fillWidth: true }

        Button {
            text: "X"
            onClicked: window.close()
            background: Rectangle {
                color: "transparent"
                border.color: "transparent"
            }
            contentItem: Text {
                text: parent.text
                color: "white"
                font.pixelSize: 16
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            hoverEnabled: true
        }
    }
}
