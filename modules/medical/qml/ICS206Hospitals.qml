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
        TableView {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.bottom: footer.top
            model: hospitalModel
            TableViewColumn { role: "id"; title: "ID"; width: 40 }
            TableViewColumn { role: "name"; title: "Hospital"; width: 220 }
            TableViewColumn { role: "address"; title: "Address"; width: 260 }
            TableViewColumn { role: "phone"; title: "Phone"; width: 120 }
            TableViewColumn { role: "helipad"; title: "Helipad"; width: 80 }
            TableViewColumn { role: "burn_center"; title: "Burn Ctr"; width: 80 }
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
