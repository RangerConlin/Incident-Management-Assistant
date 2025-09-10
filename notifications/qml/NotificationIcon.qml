import QtQuick 6.5

Item {
    id: icon
    width: 16
    height: 16
    property string severity: "info"

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: severity === "error" ? "#8B1E2D" : severity === "warning" ? "#9C6F19" : severity === "success" ? "#1E7F4F" : "#2C2C2C"
    }
}
