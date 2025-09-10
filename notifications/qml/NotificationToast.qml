import QtQuick 6.5
import QtQuick.Controls 6.5

Popup {
    id: toast
    property string mode: "auto"
    property int durationMs: 4500
    property string title
    property string message
    property string severity: "info"

    signal dismissed

    background: Rectangle {
        radius: 10
        color: severity === "error" ? "#8B1E2D" : severity === "warning" ? "#9C6F19" : severity === "success" ? "#1E7F4F" : "#2C2C2C"
        opacity: 0.95
    }
    contentItem: Column {
        spacing: 6; padding: 14
        Row {
            spacing: 10
            Label { text: toast.title; font.bold: true; color: "white" }
            Button { text: "✕"; onClicked: toast.close() }
        }
        Label { text: toast.message; color: "white"; wrapMode: Text.WordWrap; width: 320 }
    }

    Timer {
        interval: toast.durationMs
        running: toast.visible && toast.mode === "auto"
        repeat: false
        onTriggered: toast.close()
    }

    onClosed: dismissed()
}
