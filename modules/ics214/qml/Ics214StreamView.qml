import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    width: 600
    height: 400
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        TabBar {
            id: tabs
            Layout.fillWidth: true
            TabButton { text: "Narrative" }
            TabButton { text: "Related" }
            TabButton { text: "Rules" }
            TabButton { text: "Export" }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex
            ListView {
                anchors.fill: parent
            }
            Item {
                anchors.fill: parent
            }
            Item {
                anchors.fill: parent
            }
            Ics214ExportDialog {
                anchors.fill: parent
            }
        }
    }
}
