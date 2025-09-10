import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            Button { text: "+ Add"; onClicked: ics206Bridge.add_aid_station({}) }
            Button { text: "Edit" }
            Button { text: "Remove" }
            Button { text: "Copy From 205"; onClicked: ics206Bridge.import_aid_stations() }
        }
        // Simple table replacement (Qt 6 Controls has no TableViewColumn)
        Row {
            id: header
            spacing: 0
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            height: 30
            Rectangle { width: 50; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "ID" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Name" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Type" } }
            Rectangle { width: 100; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Level" } }
            Rectangle { width: 60; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "24/7" } }
            Rectangle { anchors.left: undefined; anchors.right: parent.right; width: Math.max(0, parent.width - (50+200+120+100+60)); height: parent.height; color: "#333"; border.color: "#555" }
        }
        ListView {
            id: list
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: header.bottom; anchors.bottom: notes.top
            clip: true
            model: aidStationsModel
            delegate: Row {
                spacing: 0
                height: 28
                Rectangle { width: 50; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.id } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.name } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.type } }
                Rectangle { width: 100; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.level } }
                Rectangle { width: 60; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.is_24_7 } }
                Rectangle { anchors.left: undefined; anchors.right: parent.right; width: Math.max(0, list.width - (50+200+120+100+60)); height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
            }
        }
        TextArea {
            id: notes
            placeholderText: "Notes..."
            anchors.left: parent.left; anchors.right: parent.right
            height: 80
        }
        ListModel { id: aidStationsModel }
        Component.onCompleted: {
            var rows = ics206Bridge.load_aid_stations();
            for (var i=0; i<rows.length; ++i) aidStationsModel.append(rows[i]);
        }
    }
}
