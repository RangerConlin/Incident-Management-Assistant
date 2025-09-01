import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

Window {
    id: teamDetailWindow
    property int teamId: -1
    visible: true
    width: 600
    height: 360
    title: teamId > 0 ? `Team Detail - #${teamId}` : "Team Detail"

    Rectangle {
        anchors.fill: parent
        color: "white"

        Column {
            anchors.centerIn: parent
            spacing: 12
            Text { text: teamId > 0 ? `Team ID: ${teamId}` : "No Team Selected"; font.pixelSize: 20 }
            Text { text: "Placeholder window. Full Team Detail coming soon."; font.pixelSize: 14; color: "#555" }
        }
    }
}
