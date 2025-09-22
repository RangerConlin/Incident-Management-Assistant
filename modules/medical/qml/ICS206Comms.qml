import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            Button { text: "+ Add"; onClicked: ics206Bridge.add_medical_comm({}) }
            Button { text: "Edit" }
            Button { text: "Remove" }
            Button { text: "Import"; onClicked: ics206Bridge.import_medical_comms() }
        }
        // Header row
        Row {
            id: header
            spacing: 0
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            height: 30
            Rectangle { width: 150; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Channel" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Function" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Freq" } }
            Rectangle { width: 80; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Mode" } }
            Rectangle { anchors.right: parent.right; width: Math.max(0, parent.width - (150+200+120+80)); height: parent.height; color: "#333"; border.color: "#555" }
        }
        // Rows
        ListView {
            id: list
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: header.bottom; anchors.bottom: footer.top
            clip: true
            model: commModel
            delegate: Row {
                spacing: 0
                height: 28
                Rectangle { width: 150; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.channel } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.function } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.frequency } }
                Rectangle { width: 80; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.mode } }
                Rectangle { anchors.right: parent.right; width: Math.max(0, list.width - (150+200+120+80)); height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
            }
        }
        Row {
            id: footer
            spacing: 6
            Button { text: "ICS 205" }
        }
        ListModel { id: commModel }
        Component.onCompleted: {
            var rows = ics206Bridge.load_medical_comms();
            for (var i=0; i<rows.length; ++i) commModel.append(rows[i]);
        }
    }
}
