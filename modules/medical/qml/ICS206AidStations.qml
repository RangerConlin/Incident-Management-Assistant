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
        TableView {
            id: table
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.bottom: notes.top
            model: aidStationsModel
            TableViewColumn { role: "id"; title: "ID"; width: 50 }
            TableViewColumn { role: "name"; title: "Name"; width: 200 }
            TableViewColumn { role: "type"; title: "Type"; width: 120 }
            TableViewColumn { role: "level"; title: "Level"; width: 100 }
            TableViewColumn { role: "is_24_7"; title: "24/7"; width: 60 }
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
