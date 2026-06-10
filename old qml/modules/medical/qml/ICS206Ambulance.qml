import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            Button { text: "+ Add"; onClicked: ics206Bridge.add_ambulance_service({}) }
            Button { text: "Edit" }
            Button { text: "Remove" }
            Button { text: "Import"; onClicked: ics206Bridge.import_ambulance_services() }
        }
        // Header row
        Row {
            id: header
            spacing: 0
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            height: 30
            Rectangle { width: 50; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "ID" } }
            Rectangle { width: 220; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Service" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Type" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Phone" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Location" } }
            Rectangle { anchors.right: parent.right; width: Math.max(0, parent.width - (50+220+120+120+200)); height: parent.height; color: "#333"; border.color: "#555" }
        }
        // Rows
        ListView {
            id: list
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: header.bottom; anchors.bottom: notes.top
            clip: true
            model: ambulanceModel
            delegate: Row {
                spacing: 0
                height: 28
                Rectangle { width: 50; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.id } }
                Rectangle { width: 220; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.name } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.type } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.phone } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.location } }
                Rectangle { anchors.right: parent.right; width: Math.max(0, list.width - (50+220+120+120+200)); height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
            }
        }
        TextArea {
            id: notes
            placeholderText: "Staging notes..."
            anchors.left: parent.left; anchors.right: parent.right
            height: 80
        }
        ListModel { id: ambulanceModel }
        Component.onCompleted: {
            var rows = ics206Bridge.load_ambulance_services();
            for (var i=0; i<rows.length; ++i) ambulanceModel.append(rows[i]);
        }
    }
}
