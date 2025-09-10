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
        TableView {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.bottom: notes.top
            model: ambulanceModel
            TableViewColumn { role: "id"; title: "ID"; width: 50 }
            TableViewColumn { role: "name"; title: "Service"; width: 220 }
            TableViewColumn { role: "type"; title: "Type"; width: 120 }
            TableViewColumn { role: "phone"; title: "Phone"; width: 120 }
            TableViewColumn { role: "location"; title: "Location"; width: 200 }
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
