// =============================
// components/Toast.qml
// =============================
// Simple toast used app-wide
// Save as: components/Toast.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: toast
    width: implicitWidth
    height: implicitHeight
    property int duration: 2500
    property alias text: msg.text

    function show(t) {
        msg.text = t
        toast.visible = true
        fadeIn.restart()
        timer.restart()
    }

    anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
    anchors.bottom: parent ? parent.bottom : undefined
    anchors.bottomMargin: 16

    Rectangle {
        id: card
        radius: 10
        color: "#323232"
        opacity: 0.0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 0
        width: Math.max(msg.implicitWidth + 24, 240)
        height: 44
        Label { id: msg; anchors.centerIn: parent; color: "white" }
    }

    NumberAnimation { id: fadeIn; target: card; property: "opacity"; from: 0; to: 0.95; duration: 200 }
    NumberAnimation { id: fadeOut; target: card; property: "opacity"; from: card.opacity; to: 0; duration: 300 }
    Timer {
        id: timer
        interval: toast.duration; repeat: false
        onTriggered: fadeOut.restart()
    }
}
