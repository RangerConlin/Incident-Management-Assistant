import QtQuick 2.15
import QtQuick.Controls 2.15

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 1280
    height: 720
    title: "SARApp - Incident Management Assistant"

    menuBar: MenuBar {
            Menu {
                title: "File"
                MenuItem { text: "New Incident" }
                MenuItem { text: "Open Incident" }
                MenuItem { text: "Save" }
                MenuItem { text: "Exit"; onTriggered: Qt.quit() }
            }
            Menu {
                title: "Edit"
                MenuItem { text: "Preferences" }
                MenuItem {
                    enabled: false
                    text: "Templates"
                    font.bold: true
                }
                MenuItem { text: "Canned Comm Log Entries" }
            }
            Menu {
                title: "Command"
                MenuItem { text: "Incident Overview" }
            }
            Menu {
                title: "Planning"
                MenuItem { text: "Situation Reports" }
                MenuItem {
                        text: "Strategic Tasks"
                        onTriggered: {
                            var component = Qt.createComponent("StrategicTasks.qml");
                            if (component.status === Component.Ready) {
                                var window = component.createObject();
                                window.show();
                            } else {
                                console.log("Failed to load StrategicTasks.qml");

                            }
                        }
                    }
            }
            Menu {
                title: "Operations"
                MenuItem { text: "Assign Teams" }
            }
            Menu {
                title: "Logistics"
                MenuItem { text: "Resource Tracker" }
                MenuItem { text: "Member Needs" }
            }
            Menu {
                title: "Communications"
                MenuItem { text: "Comms Log" }
                MenuSeparator {}
                MenuItem { text: "ICS-205 Comms Plan" }
            }
            Menu {
                title: "Safety"
                MenuItem { text: "Incident Hazards" }
            }
            Menu {
                title: "Medical"
                MenuItem { text: "ICS-206 Medical Plan" }
            }
            Menu {
                title: "Toolkits"
                Menu { title: "SAR Toolkit"
                    MenuItem { text: "Matteson"}
                    MenuItem { text: "POD Calculator"}
                    }
                Menu { title: "Disaster Response Toolkit"
                    MenuItem { text: "Matteson"}
                    MenuItem { text: "POD Calculator"}
                    }
                Menu { title: "Planned Event Toolkit"
                    MenuItem { text: "Event Promotion and Communication"}
                    MenuItem { text: "Vendor & Permitting Coordination"}
                    MenuItem { text: "Public Safety & Incident Management"}
                    MenuItem { text: "Mini-Tasking Module"}
                    MenuItem { text: "Public Health & Sanitation Oversight"}
                    }
            }
            Menu {
                title: "Help"
                MenuItem { text: "User Guide" }
                MenuItem { text: "About SARApp" }
            }
        }


    // Main background
    Rectangle {
        anchors.fill: parent
        color: "#f5f5f5"

        Column {
            spacing: 20
            anchors.centerIn: parent

            Text {
                text: "Incident Dashboard"
                font.pixelSize: 30
                font.bold: true
                color: "#003a67"
            }

            Button {
                text: "Check In Personnel"
                onClicked: console.log("Check In clicked")
            }

            Button {
                text: "Assign Task"
                onClicked: console.log("Assign Task clicked")
            }

            Button {
                text: "View Map"
                onClicked: console.log("View Map clicked")
            }
        }
    }
}
