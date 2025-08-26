import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import Qt.labs.platform 1.1

Item {
    width: 600
    height: 700

    Rectangle {
        anchors.fill: parent
        color: "#f0f0f0"
        radius: 8
        border.color: "#cccccc"
        anchors.margins: 20

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Label {
                text: "Incident Detail"
                font.pixelSize: 20
                font.bold: true
            }

            TextField {
                id: incidentName
                placeholderText: "Incident Name"
                Layout.fillWidth: true
            }

            TextField {
                id: incidentNumber
                placeholderText: "Incident Number"
                Layout.fillWidth: true
            }

            ComboBox {
                id: incidentType
                model: ["SAR", "Disaster Response", "Training", "Planned Event"]
                currentIndex: -1
                Layout.fillWidth: true
                displayText: currentIndex === -1 ? "Incident Type" : model[currentIndex]
            }

            TextField {
                id: location
                placeholderText: "Location"
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                TextField {
                    id: startDate
                    placeholderText: "Start Date (YYYY-MM-DD)"
                    Layout.fillWidth: true
                }

                TextField {
                    id: startTime
                    placeholderText: "Start Time (HH:MM)"
                    Layout.fillWidth: true
                }
            }

            CheckBox {
                id: isTraining
                text: "Is this a training incident?"
                checked: false
            }

            TextArea {
                id: description
                placeholderText: "Incident Description"
                Layout.fillWidth: true
                Layout.preferredHeight: 100
            }

            ComboBox {
                id: incidentStatus
                model: ["Active", "Standby", "Completed"]
                Layout.fillWidth: true
                displayText: currentIndex === -1 ? "Incident Status" : model[currentIndex]
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#ccc"
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 10

                Button {
                    text: "Cancel"
                    onClicked: Qt.quit()
                }

                Button {
                    text: "Save"
                    onClicked: {
                        console.log("Incident saved:")
                        console.log("Name:", incidentName.text)
                        console.log("Type:", incidentType.currentText)
                        // Hook to backend save logic here
                    }
                }
            }
        }
    }
}
