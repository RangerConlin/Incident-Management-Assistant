import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    anchors.fill: parent
    Column {
        anchors.fill: parent
        spacing: 6
        Row {
            spacing: 6
            Button { text: "+ Add"; onClicked: ics206Bridge.add_hospital({}) }
            Button { text: "Edit" }
            Button { text: "Remove" }
            Button { text: "Import"; onClicked: ics206Bridge.import_hospitals() }
        }
        // Header row
        Row {
            id: header
            spacing: 0
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top
            height: 30
            Rectangle { width: 40; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "ID" } }
            Rectangle { width: 220; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Hospital" } }
            Rectangle { width: 260; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Address" } }
            Rectangle { width: 120; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Phone" } }
            Rectangle { width: 80; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Helipad" } }
            Rectangle { width: 80; height: parent.height; color: "#333"; border.color: "#555"; Text { anchors.centerIn: parent; color: "white"; text: "Burn Ctr" } }
            Rectangle { anchors.right: parent.right; width: Math.max(0, parent.width - (40+220+260+120+80+80)); height: parent.height; color: "#333"; border.color: "#555" }
        }
        // Rows
        ListView {
            id: list
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: header.bottom; anchors.bottom: footer.top
            clip: true
            model: hospitalModel
            delegate: Row {
                spacing: 0
                height: 28
                Rectangle { width: 40; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.id } }
                Rectangle { width: 220; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.name } }
                Rectangle { width: 260; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 6; color: "#ddd"; text: model.address } }
                Rectangle { width: 120; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.phone } }
                Rectangle { width: 80; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.helipad } }
                Rectangle { width: 80; height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444"; Text { anchors.centerIn: parent; color: "#ddd"; text: model.burn_center } }
                Rectangle { anchors.right: parent.right; width: Math.max(0, list.width - (40+220+260+120+80+80)); height: parent.height; color: index % 2 ? "#232323" : "#1e1e1e"; border.color: "#444" }
            }
        }
        Row {
            id: footer
            spacing: 6
            TextField { placeholderText: "Address"; width: 300 }
            CheckBox { text: "Helipad" }
        }
        ListModel { id: hospitalModel }
        Component.onCompleted: {
            var rows = ics206Bridge.load_hospitals();
            for (var i=0; i<rows.length; ++i) hospitalModel.append(rows[i]);
        }
    }
}
