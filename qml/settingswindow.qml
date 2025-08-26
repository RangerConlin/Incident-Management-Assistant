import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15


ApplicationWindow {
    id: root
    width: 800
    height: 600

    property int currentIndex: 0

    signal settingChanged(string key, var value)

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar
        ListView {
            id: sidebar
            width: 200
            Layout.fillHeight: true
            model: ListModel {
                ListElement { name: "General" }
                ListElement { name: "Theme" }
                ListElement { name: "Notifications" }
                ListElement { name: "Incident Defaults" }
                ListElement { name: "Mapping & GPS" }
                ListElement { name: "Personnel & Teams" }
                ListElement { name: "Communications" }
                ListElement { name: "Data & Storage" }
                ListElement { name: "Advanced" }
                ListElement { name: "About" }
            }

            delegate: Rectangle {
                width: sidebar.width
                height: 40
                color: ListView.isCurrentItem ? "#2d8fcf" : "#303030"
                border.color: "#4a4a4a"

                Text {
                    anchors.centerIn: parent
                    text: name
                    color: "white"
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        sidebar.currentIndex = index
                        stack.currentIndex = index
                    }
                }
            }
        }

        // Main content area
        StackLayout {
            id: stack
            Layout.fillHeight: true
            Layout.fillWidth: true
            currentIndex: sidebar.currentIndex

            Loader { source: "../settings/General.qml" }
            Loader { source: "../settings/Theme.qml" }
            Loader { source: "../settings/Notifications.qml" }
            Loader { source: "../settings/IncidentDefaults.qml" }
            Loader { source: "../settings/Mapping.qml" }
            Loader { source: "../settings/Personnel.qml" }
            Loader { source: "../settings/Communications.qml" }
            Loader { source: "../settings/DataStorage.qml" }
            Loader { source: "../settings/Advanced.qml" }
            Loader { source: "../settings/About.qml" }
        }
    }
}
