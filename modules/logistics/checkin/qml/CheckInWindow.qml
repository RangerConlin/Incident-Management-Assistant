import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    width: 600
    height: 400

    Column {
        anchors.fill: parent

        // Tab selector
        TabBar {
            id: tabBar
            width: parent.width

            TabButton { text: "Personnel" }
            TabButton { text: "Equipment" }
            TabButton { text: "Vehicles" }
            TabButton { text: "Aircraft" }
        }

        // Pages that change with the TabBar
        SwipeView {
            id: swipeView
            currentIndex: tabBar.currentIndex
            anchors.fill: parent

            Loader { source: "components/LookupPanel.qml"; property string entityType: "personnel" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "equipment" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "vehicle" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "aircraft" }
        }
    }

    // Toast overlay
    Loader {
        id: toastLoader
        source: "components/Toast.qml"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
    }

    Connections {
        target: checkInBridge
        function onToast(msg) {
            if (toastLoader.item) toastLoader.item.show(msg)
        }
    }
}
