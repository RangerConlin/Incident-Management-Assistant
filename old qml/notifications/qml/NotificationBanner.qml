import QtQuick 6.5
import QtQuick.Controls 6.5

Rectangle {
    id: banner
    width: parent.width
    color: severity === "error" ? "#8B1E2D" : severity === "warning" ? "#9C6F19" : severity === "success" ? "#1E7F4F" : "#2C2C2C"
    property string title
    property string message
    property string severity: "info"
    signal dismissed
    height: content.implicitHeight + 16

    Column {
        id: content
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4
        Label { text: banner.title; color: "white"; font.bold: true }
        Label { text: banner.message; color: "white"; wrapMode: Text.WordWrap }
    }

    MouseArea { anchors.fill: parent; onClicked: banner.dismissed() }
}
