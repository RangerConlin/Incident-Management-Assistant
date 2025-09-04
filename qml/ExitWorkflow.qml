import QtQuick 2.15
import QtQuick.Controls 2.15

Item { anchors.fill: parent
    Column { anchors.fill: parent; anchors.margins: 16; spacing: 8
        Label { text: "Exit Workflow"; font.bold: true; font.pointSize: 14 }
        TextArea { text: "Placeholder for save/discard/cancel workflow before exit."; readOnly: true; wrapMode: Text.WordWrap
            background: Rectangle { color: "transparent"; border.color: "#ccc"; radius: 6 } }
    }
}

