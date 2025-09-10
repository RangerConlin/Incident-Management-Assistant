import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            Button { text: "+ Add"; onClicked: ics206Bridge.add_air_ambulance({}) }
            Button { text: "Edit" }
            Button { text: "Remove" }
            Button { text: "Import"; onClicked: ics206Bridge.import_air_ambulance() }
        }
        // Header row
        Row {
            id: header
            spacing: 0
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            height: 30
            Rectangle { width: 40; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "ID" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Agency" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Phone" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Base" } }
            Rectangle { width: 200; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Contact" } }
            Rectangle { anchors.right: parent.right; width: Math.max(0, parent.width - (40+200+120+200+200)); height: parent.height; color: "#333"; border.color: "#555" }
        }
        // Rows
        ListView {
            id: list
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: header.bottom; anchors.bottom: footer.top
            clip: true
            model: airAmbModel
            delegate: Row {
                spacing: 0
                height: 28
                Rectangle { width: 40; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.id } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.name } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.phone } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.base } }
                Rectangle { width: 200; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.contact } }
                Rectangle { anchors.right: parent.right; width: Math.max(0, list.width - (40+200+120+200+200)); height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
            }
        }
        Row {
            id: footer
            spacing: 6
            Button { text: "LZ Plan" }
        }
        ListModel { id: airAmbModel }
        Component.onCompleted: {
            var rows = ics206Bridge.load_air_ambulance();
            for (var i=0; i<rows.length; ++i) airAmbModel.append(rows[i]);
        }
    }
}
