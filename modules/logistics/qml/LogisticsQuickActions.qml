import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    width: 200; height: 160

    Column {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        Button { text: "New Requisition" }
        Button { text: "Check In" }
        Button { text: "Equipment Status" }
        Button { text: "Transport Ticket" }
    }
}

