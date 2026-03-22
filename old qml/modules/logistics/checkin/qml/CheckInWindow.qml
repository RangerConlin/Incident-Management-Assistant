// CheckInWindow.qml — fleshed out per SARApp requirements
// - Tabs: Personnel, Equipment, Vehicles, Aircraft
// - Each tab uses a shared LookupPanel with entityType prop
// - Adds header actions, search, detail drawer, and check-in form
// - Wires to checkInBridge (Python/C++ backend) for search, fetch, and check-in
// - Emits toasts via Toast.qml

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import Qt5Compat.GraphicalEffects

Item {
    id: root
    width: 1000
    height: 680

    // ---------- Global State ----------
    property bool busy: false
    property string currentEntityType: ["personnel","equipment","vehicle","aircraft"][tabBar.currentIndex]

    // Shared status enums (mirror backend constants if available)
    readonly property var checkin_statuses: ["Pending", "Checked In", "No Show", "Demobilized"]
    readonly property var personnel_statuses: [
        // UI hints — backend enforces the autosync rules (Pending->status Pending, No Show->Unavailable, Demobilized->Demobilized, default->Available)
        {label: "Available", value: "Available"},
        {label: "Assigned", value: "Assigned"},
        {label: "Pending", value: "Pending"},
        {label: "Unavailable", value: "Unavailable"},
        {label: "Demobilized", value: "Demobilized"}
    ]

    // ---------- Header Bar ----------
    Rectangle {
        id: header
        color: Qt.darker(palette.window, 1.02)
        anchors.left: parent.left
        anchors.right: parent.right
        height: 52
        border.color: palette.mid

        RowLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 8

            Label { text: "Check-In"; font.pixelSize: 20; font.bold: true; Layout.alignment: Qt.AlignVCenter }
            Rectangle { Layout.fillWidth: true; opacity: 0 }

            Button {
                id: refreshBtn
                text: "Refresh"
                onClicked: {
                    var loader = stackLayout.children[tabBar.currentIndex]
                    if (loader && loader.item && loader.item.refresh) {
                        loader.item.refresh()
                    }
                }
            }
            Button {
                id: helpBtn
                text: "Help"
                onClicked: toastLoader.item && toastLoader.item.show("Type to search. Select a row to open details. Fill fields and press Check In.")
            }
        }
    }

    // ---------- Main Body ----------
    ColumnLayout {
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: 0

        // Tab selector
        TabBar {
            id: tabBar
            Layout.fillWidth: true
            TabButton { text: "Personnel" }
            TabButton { text: "Equipment" }
            TabButton { text: "Vehicles" }
            TabButton { text: "Aircraft" }
        }

        // Pages that change with the TabBar
        StackLayout {
            id: stackLayout
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // Note: components/LookupPanel.qml provided below in this canvas
            Loader { source: "components/LookupPanel.qml"; property string entityType: "personnel" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "equipment" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "vehicle" }
            Loader { source: "components/LookupPanel.qml"; property string entityType: "aircraft" }
        }
    }

    // Busy overlay
    Rectangle {
        visible: root.busy
        anchors.fill: parent
        color: "#80000000"
        z: 999
        Column {
            anchors.centerIn: parent
            spacing: 8
            BusyIndicator { running: true; width: 42; height: 42 }
            Label { text: "Working..."; color: "white" }
        }
        MouseArea { anchors.fill: parent } // absorb clicks
    }

    // Toast overlay
    Loader {
        id: toastLoader
        source: "components/Toast.qml"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        z: 1000
    }

    // Backend signal hookup
    Connections {
        target: checkInBridge
        // Show ephemeral messages from backend
        function onToast(msg) {
            if (toastLoader.item) toastLoader.item.show(msg)
        }
        function onBusyChanged(b) { root.busy = b }
    }
}

