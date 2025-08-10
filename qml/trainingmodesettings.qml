import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

Window {
    id: strategicTasksWindow
    visible: true
    width: 800
    height: 600
    title: "Strategic Tasks"

    Rectangle {
        anchors.fill: parent
        color: "white"

        Text {
            anchors.centerIn: parent
            text: "Strategic Tasks Module"
            font.pixelSize: 28
        }
    }
}
