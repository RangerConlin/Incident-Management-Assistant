import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3
import Qt.labs.platform 1.1


Item {
    width: 600
    height: 800

    Rectangle {
        anchors.fill: parent
        color: "#f2f2f2"
        radius: 10
        border.color: "#999"
        border.width: 1
        anchors.margins: 20

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Label { text: "SAR-135: Add Clue Form"; font.bold: true; font.pixelSize: 20 }

            TextField {
                id: clueNumber
                placeholderText: "Clue Number"
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                TextField {
                    id: dateField
                    placeholderText: "Date"
                    Layout.fillWidth: true
                }
                TextField {
                    id: timeField
                    placeholderText: "Time"
                    Layout.fillWidth: true
                }
            }

            TextField {
                id: location
                placeholderText: "Location (Lat/Lon or UTM)"
                Layout.fillWidth: true
            }

            TextField {
                id: foundBy
                placeholderText: "Found By (Team or Individual)"
                Layout.fillWidth: true
            }

            TextArea {
                id: description
                placeholderText: "Clue Description"
                Layout.fillWidth: true
                Layout.preferredHeight: 100
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Button {
                    text: "Attach Photo"
                    onClicked: fileDialog.open()
                }

                Label {
                    text: fileDialog.fileUrl !== "" ? fileDialog.fileUrl.toString().split("/").pop() : "No file selected"
                    Layout.fillWidth: true
                    elide: Label.ElideRight
                }

                FileDialog {
                    id: fileDialog
                    title: "Select Photo"
                    nameFilters: ["Images (*.png *.jpg *.jpeg)"]
                    fileMode: FileDialog.OpenFile
                    onAccepted: {
                        console.log("Selected file:", fileDialog.file)
                    }
                }

            }

            TextArea {
                id: actionTaken
                placeholderText: "Action Taken"
                Layout.fillWidth: true
                Layout.preferredHeight: 100
            }

            TextField {
                id: submittedBy
                placeholderText: "Submitted By"
                Layout.fillWidth: true
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
                    text: "Submit"
                    onClicked: {
                        console.log("Submitted clue:")
                        console.log("Clue Number:", clueNumber.text)
                        console.log("Location:", location.text)
                        // Add save-to-database hook here
                    }
                }
            }
        }
    }
}
