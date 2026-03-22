// =============================
// components/LookupPanel.qml
// =============================
// A reusable search + results + detail form for check-in of any entity type.
// Props:
//   - entityType: "personnel" | "equipment" | "vehicle" | "aircraft"
// Exposed methods:
//   - refresh() — rerun current search

// Save as: components/LookupPanel.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: panel
    property alias entityType: panel._entityType
    property string _entityType: "personnel"

    signal requestRefresh()

    function refresh() {
        searchTimer.restart()
    }

    // Local state
    property var selectedItem: null
    property bool loading: false

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        anchors.margins: 12

        // Search row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: panel._entityType === "personnel" ? "Search name, ID, callsign..." : "Search by name, ID, callsign..."
                onTextEdited: searchTimer.restart()
                onAccepted: searchTimer.restart()
            }
            ComboBox {
                id: filterStatus
                visible: panel._entityType === "personnel"
                model: ["Any","Available","Assigned","Pending","Unavailable","Demobilized"]
            }
            Button {
                text: "Clear"
                onClicked: {
                    searchField.text = ""
                    searchTimer.restart()
                }
            }
        }

        // Results list
        Frame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0

            ListView {
                id: list
                anchors.fill: parent
                clip: true
                model: resultsModel
                delegate: ItemDelegate {
                    width: list.width
                    text: display
                    onClicked: {
                        list.currentIndex = index
                        panel.selectedItem = resultsModel.get(index)
                        panel.loadDetails(panel.selectedItem)
                    }
                }
                ScrollBar.vertical: ScrollBar {}
            }
        }

        // Detail + check-in form
        Loader {
            id: detailLoader
            Layout.fillWidth: true
            Layout.preferredHeight: panel.selectedItem ? implicitHeight : 0
            active: !!panel.selectedItem
            sourceComponent: detailForm
        }

        // Action row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: "Check In"
                enabled: panel.selectedItem && formState.valid
                onClicked: panel.doCheckIn()
            }
            Button {
                text: "Close"
                onClicked: panel.selectedItem = null
            }
            Item { Layout.fillWidth: true }
            Label { text: resultsModel.count + " result(s)"; opacity: 0.7 }
        }
    }

    // Results model (simple stringly model for UI; backend holds full data)
    ListModel { id: resultsModel }

    Timer {
        id: searchTimer
        interval: 250; repeat: false
        onTriggered: panel.search()
    }

    // ---------- Backend calls ----------
    function search() {
        loading = true
        let q = searchField.text || ""
        let status = (panel._entityType === "personnel" && filterStatus.currentIndex > 0) ? filterStatus.currentText : ""
        // Expect backend to return an array of objects with at least { id, display }
        checkInBridge.searchEntity(panel._entityType, q, status, function(results) {
            resultsModel.clear()
            for (var i=0; i<results.length; ++i) {
                resultsModel.append(results[i])
            }
            loading = false
        })
    }

    function loadDetails(item) {
        if (!item) return
        loading = true
        checkInBridge.getDetails(panel._entityType, item.id, function(details) {
            formState.details = details
            // Reset transient fields
            formState.checkinStatus = panel._entityType === "personnel" ? "Checked In" : "Checked In"
            formState.personnelStatus = panel._entityType === "personnel" ? (details.suggestedStatus || "Available") : ""
            formState.location = ""
            formState.notes = ""
            loading = false
        })
    }

    function doCheckIn() {
        var payload = {
            id: panel.selectedItem.id,
            entityType: panel._entityType,
            checkinStatus: formState.checkinStatus,
            personnelStatus: panel._entityType === "personnel" ? formState.personnelStatus : "",
            location: formState.location,
            notes: formState.notes
        }
        // UI-side enforcement of known rules (backend is source of truth)
        if (panel._entityType === "personnel") {
            if (payload.checkinStatus === "Pending") payload.personnelStatus = "Pending"
            if (payload.checkinStatus === "No Show") payload.personnelStatus = "Unavailable"
            if (payload.checkinStatus === "Demobilized") payload.personnelStatus = "Demobilized"
            if (payload.checkinStatus === "Checked In" && (!payload.personnelStatus || payload.personnelStatus === "")) {
                payload.personnelStatus = "Available"
            }
        }

        panel.loading = true
        checkInBridge.checkInEntity(payload, function(ok, message) {
            panel.loading = false
            if (ok) {
                toastLoader.item && toastLoader.item.show("Check-in saved")
                panel.selectedItem = null
                panel.refresh()
            } else {
                toastLoader.item && toastLoader.item.show(message || "Failed to save check-in")
            }
        })
    }

    // ---------- Detail form component ----------
    property var formState: ({
        details: ({}),
        checkinStatus: "Checked In",
        personnelStatus: "Available",
        location: "",
        notes: "",
        get valid() {
            return !!panel.selectedItem
        }
    })

    Component {
        id: detailForm
        Frame {
            padding: 12
            ColumnLayout {
                width: parent.width
                spacing: 8

                // Header summary
                Label { text: formState.details.display || panel.selectedItem.display; font.pixelSize: 16; font.bold: true }
                RowLayout { spacing: 12
                    Label { text: panel._entityType.toUpperCase(); color: "#777" }
                    Label { text: formState.details.callsign ? ("Callsign: " + formState.details.callsign) : ""; visible: !!formState.details.callsign }
                    Label { text: formState.details.role ? ("Role: " + formState.details.role) : ""; visible: !!formState.details.role }
                }

                // Grid of fields
                GridLayout {
                    columns: 2; columnSpacing: 16; rowSpacing: 10
                    Layout.fillWidth: true

                    Label { text: "Check-In Status" }
                    ComboBox { id: cbCheckin
                        model: ["Checked In", "Pending", "No Show", "Demobilized"]
                        currentIndex: model.indexOf(formState.checkinStatus)
                        onActivated: formState.checkinStatus = currentText
                    }

                    Label { text: "Personnel Status"; visible: panel._entityType === "personnel" }
                    ComboBox { id: cbPers
                        visible: panel._entityType === "personnel"
                        model: ["Available","Assigned","Pending","Unavailable","Demobilized"]
                        currentIndex: model.indexOf(formState.personnelStatus)
                        onActivated: formState.personnelStatus = currentText
                    }

                    Label { text: panel._entityType === "personnel" ? "Staging / Location" : "Location" }
                    TextField { text: formState.location; onTextChanged: formState.location = text; placeholderText: "e.g. ICP, Staging, FOB 2" }

                    Label { text: "Notes" }
                    TextArea { text: formState.notes; onTextChanged: formState.notes = text; placeholderText: "Any quick notes for the log (ICS 211/218)"; Layout.preferredHeight: 80 }
                }
            }
        }
    }
}

