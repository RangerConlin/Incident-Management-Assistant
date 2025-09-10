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
        TableView {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.bottom: footer.top
            model: airAmbModel
            TableViewColumn { role: "id"; title: "ID"; width: 40 }
            TableViewColumn { role: "name"; title: "Agency"; width: 200 }
            TableViewColumn { role: "phone"; title: "Phone"; width: 120 }
            TableViewColumn { role: "base"; title: "Base"; width: 200 }
            TableViewColumn { role: "contact"; title: "Contact"; width: 200 }
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
