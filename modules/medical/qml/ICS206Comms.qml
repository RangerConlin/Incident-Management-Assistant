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
        TableView {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.bottom: footer.top
            model: commModel
            TableViewColumn { role: "channel"; title: "Channel"; width: 150 }
            TableViewColumn { role: "function"; title: "Function"; width: 200 }
            TableViewColumn { role: "frequency"; title: "Freq"; width: 120 }
            TableViewColumn { role: "mode"; title: "Mode"; width: 80 }
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
