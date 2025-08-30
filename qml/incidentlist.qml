import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 800
    height: 500

    // Emitted to Python when a incident is chosen
    signal incidentselected(string incidentNumber)

    // Tracks which row is highlighted/selected
    property string selectedIncidentNumber: ""

    Rectangle {
        anchors.fill: parent
        color: "#f0f0f0"
        anchors.margins: 10

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "Select Active Incident"
                font.pixelSize: 20
                Layout.alignment: Qt.AlignHCenter
            }

            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: incidentModel
                spacing: 5
                clip: true
                focus: true

                delegate: Rectangle {
                    width: listView.width
                    height: 40
                    color: ListView.isCurrentItem ? "#d0f0ff" : "#ffffff"
                    border.color: "#cccccc"

                    RowLayout {
                        anchors.fill: parent
                        spacing: 20

                        // NOTE: Use role names directly (number/name/etc.)
                        Text { text: number;       Layout.preferredWidth: 100 }
                        Text { text: name;         Layout.fillWidth: true }
                        Text { text: type;         Layout.preferredWidth: 100 }
                        Text { text: status;       Layout.preferredWidth: 80 }
                        Text { text: icp_location; Layout.preferredWidth: 200 }
                    }

                    MouseArea {
                        id: clickArea
                        anchors.fill: parent
                        property int clickCount: 0

                        Timer {
                            id: clickTimer
                            interval: 300
                            repeat: false
                            onTriggered: clickCount = 0
                        }

                        onClicked: {
                            // highlight the row and store the incident number
                            listView.currentIndex = index
                            root.selectedIncidentNumber = number

                            // double-click detection
                            clickCount += 1
                            if (!clickTimer.running) clickTimer.start()
                            if (clickCount === 2) {
                                clickTimer.stop()
                                clickCount = 0
                                root.incidentselected(number)
                            }
                        }
                    }
                }

                // Enter/Return triggers Select on the highlighted row
                Keys.onReturnPressed: {
                    if (root.selectedIncidentNumber !== "")
                        root.incidentselected(root.selectedIncidentNumber)
                }
            }

            // --- Select button ---
            Button {
                id: selectBtn
                text: "Select"
                Layout.alignment: Qt.AlignHCenter
                enabled: root.selectedIncidentNumber !== ""
                onClicked: {
                    if (root.selectedIncidentNumber !== "")
                        root.incidentselected(root.selectedIncidentNumber)
                }
            }
        }
    }
}
