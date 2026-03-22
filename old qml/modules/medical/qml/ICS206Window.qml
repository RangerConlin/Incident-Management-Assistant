import QtQuick 6.5
import QtQuick.Controls 6.5
import QtQuick.Layouts 1.15
import "."

ApplicationWindow {
    id: window
    visible: true
    title: "ICS 206 - Medical Plan"
    width: 1200; height: 800

    Column {
        anchors.fill: parent
        spacing: 6

        // Header ---------------------------------------------------------
        Row {
            spacing: 20
            Text { text: "Incident: " + appState.activeIncident }
            Text { text: "Op Period: " + appState.activeOpPeriod }
        }

        // Toolbar --------------------------------------------------------
        Row {
            spacing: 8
            Button { text: "New"; onClicked: ics206Bridge.duplicate_last_op() }
            Button { text: "Save"; onClicked: ics206Bridge.save_procedures(proceduresArea.text) }
            Button { text: "Duplicate Last OP"; onClicked: ics206Bridge.duplicate_last_op() }
            // Replaced undefined MenuButton with a standard Button to avoid type error
            Button { text: "Import" }
            Button { text: "PDF"; onClicked: ics206Bridge.save_pdf() }
            Button { text: "Print" }
        }

        // Segmented control (tabs) --------------------------------------
        Row {
            id: tabButtons
            spacing: 4
            ButtonGroup { id: tabGroup }
            Repeater {
                model: [
                    "Aid Stations",
                    "Ambulance",
                    "Hospitals",
                    "Air Ambulance",
                    "Procedures",
                    "Comms",
                    "Signatures"
                ]
                delegate: Button {
                    text: modelData
                    checkable: true
                    checked: index === 0
                    ButtonGroup.group: tabGroup
                    onClicked: stack.currentIndex = index
                }
            }
        }

        // StackLayout for tab content -----------------------------------
        StackLayout {
            id: stack
            anchors.fill: parent
            currentIndex: 0
            ICS206AidStations { }
            ICS206Ambulance { }
            ICS206Hospitals { }
            ICS206AirAmbulance { }
            ICS206Procedures { id: proceduresArea }
            ICS206Comms { }
            ICS206Signatures { }
        }
    }
}

