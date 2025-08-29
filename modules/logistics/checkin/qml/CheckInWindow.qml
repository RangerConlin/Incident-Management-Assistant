import QtQuick 2.15
import QtQuick.Controls 2.15

// Main window with tabs for each entity type
Item {
    width: 600
    height: 400

    TabView {
        anchors.fill: parent
        Tab { title: "Personnel"; Loader { source: "components/LookupPanel.qml"; property string entityType: "personnel" } }
        Tab { title: "Equipment"; Loader { source: "components/LookupPanel.qml"; property string entityType: "equipment" } }
        Tab { title: "Vehicles"; Loader { source: "components/LookupPanel.qml"; property string entityType: "vehicle" } }
        Tab { title: "Aircraft"; Loader { source: "components/LookupPanel.qml"; property string entityType: "aircraft" } }
    }

    // Toast message overlay
    Loader {
        id: toastLoader
        source: "components/Toast.qml"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
    }

    Connections {
        target: checkInBridge
        function onToast(msg) { toastLoader.item.show(msg) }
    }
}
