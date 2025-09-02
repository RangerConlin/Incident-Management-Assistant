import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "../../../common/dialogs" as Dialogs

Window {
    id: win
    width: 1280; height: 800
    minimumWidth: 1280; minimumHeight: 800
    visible: true
    title: (teamBridge && teamBridge.team && teamBridge.team.name) ? `Team Detail - ${teamBridge.team.name}` : "Team Detail"

    property int teamId: -1

    Component.onCompleted: {
        if (teamId > 0 && teamBridge && teamBridge.loadTeam) teamBridge.loadTeam(teamId)
    }

    Rectangle { anchors.fill: parent; color: "#ffffff" }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        // Header -------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: headerRow.implicitHeight + 12
            border.color: "#cccccc"
            radius: 4
            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.margins: 8
                spacing: 12
                // Name
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: (teamBridge && teamBridge.isAircraftTeam) ? "Callsign" : "Team Name"; font.pixelSize: 12 }
                    TextField {
                        id: tfName
                        Layout.fillWidth: true
                        text: (teamBridge && teamBridge.team) ? (teamBridge.team.name || "") : ""
                        onTextChanged: if (teamBridge) teamBridge.updateFromQml({ name: text })
                    }
                }
                // Team Type dropdown
                ColumnLayout {
                    spacing: 4
                    Text { text: "Team Type"; font.pixelSize: 12 }
                    ComboBox {
                        id: cbTeamType
                        model: ["New Team", "Ground", "Aircraft"]
                        onActivated: {
                            var key = (index === 1) ? "ground" : (index === 2 ? "aircraft" : "")
                            if (teamBridge) teamBridge.updateFromQml({ team_type: key })
                        }
                        Component.onCompleted: {
                            if (teamBridge && teamBridge.team) {
                                var tt = (teamBridge.team.team_type || "").toLowerCase()
                                if (tt === "ground") currentIndex = 1
                                else if (tt === "aircraft") currentIndex = 2
                                else currentIndex = 0
                            }
                        }
                    }
                }
                // Leader chip (readonly button placeholder)
                ColumnLayout {
                    spacing: 4
                    Text { text: (teamBridge && teamBridge.isAircraftTeam) ? "Pilot" : "Team Leader"; font.pixelSize: 12 }
                    Button {
                        text: (teamBridge && teamBridge.team && teamBridge.team.team_leader_id) ? `#${teamBridge.team.team_leader_id}` : "Not Set"
                        onClicked: tabs.currentIndex = 0 // focus personnel tab
                    }
                }
                // Leader Phone input
                ColumnLayout {
                    spacing: 4
                    Text { text: "Leader Phone"; font.pixelSize: 12 }
                    TextField {
                        id: tfLeaderPhone
                        Layout.preferredWidth: 120
                        text: (teamBridge && teamBridge.team) ? (teamBridge.team.team_leader_phone || "") : ""
                        onTextChanged: if (teamBridge) teamBridge.updateFromQml({ team_leader_phone: text })
                    }
                }
                // Status pill + dropdown
                ColumnLayout {
                    spacing: 4
                    Text { text: "Status"; font.pixelSize: 12 }
                    RowLayout {
                        spacing: 6
                        Rectangle {
                            width: 18; height: 18; radius: 9
                            color: teamBridge ? teamBridge.teamStatusColor.bg : "#888"
                            border.color: "#444"
                        }
                        ComboBox {
                            id: cbStatus
                            model: teamBridge ? teamBridge.statusList : []
                            // Provide delegate + display for JS array model
                            delegate: ItemDelegate { text: (modelData && modelData.label) ? modelData.label : String(modelData) }
                            displayText: (currentIndex >= 0 && teamBridge && teamBridge.statusList && teamBridge.statusList[currentIndex]) ? teamBridge.statusList[currentIndex].label : ""
                            onActivated: {
                                var item = model[index]
                                var key = (item && item.key) ? item.key : (displayText || "")
                                if (teamBridge) teamBridge.setStatus(key)
                            }
                            Component.onCompleted: {
                                // try match current status to index
                                if (teamBridge && teamBridge.team) {
                                    var s = (teamBridge.team.status||"").toLowerCase()
                                    for (var i=0;i<count;i++) {
                                        var it = model[i]
                                        if (it && it.key && it.key.toLowerCase()===s) { currentIndex = i; break }
                                    }
                                }
                            }
                        }
                    }
                }
                // Last Contact timestamp
                ColumnLayout {
                    spacing: 4
                    Text { text: "Last Contact"; font.pixelSize: 12 }
                    Text { text: (teamBridge && teamBridge.team) ? (teamBridge.team.last_update_ts || "") : "" }
                }
                // Primary Task field
                ColumnLayout {
                    spacing: 4
                    Text { text: "Primary Task"; font.pixelSize: 12 }
                    TextField {
                        id: tfPrimaryTask
                        Layout.preferredWidth: 150
                        enabled: (teamBridge && teamBridge.team && teamBridge.team.current_task_id)
                        text: (teamBridge && teamBridge.team && teamBridge.team.current_task_id) ? (teamBridge.team.primary_task || "") : ""
                        onTextChanged: if (teamBridge) teamBridge.updateFromQml({ primary_task: text })
                    }
                }
                // Assignment field
                ColumnLayout {
                    spacing: 4
                    Text { text: "Assignment"; font.pixelSize: 12 }
                    TextField {
                        id: tfAssignment
                        Layout.preferredWidth: 180
                        enabled: (teamBridge && teamBridge.team && teamBridge.team.current_task_id)
                        text: (teamBridge && teamBridge.team && teamBridge.team.current_task_id) ? (teamBridge.team.assignment || "") : ""
                        onTextChanged: if (teamBridge) teamBridge.updateFromQml({ assignment: text })
                    }
                }
                // Clocks (local/UTC) simple labels
                ColumnLayout {
                    spacing: 2
                    Text { text: "Local"; font.pixelSize: 12 }
                    Text { id: lblLocal; text: new Date().toLocaleTimeString() }
                    Timer { interval: 1000; running: true; repeat: true; onTriggered: lblLocal.text = new Date().toLocaleTimeString() }
                }
                ColumnLayout {
                    spacing: 2
                    Text { text: "UTC"; font.pixelSize: 12 }
                    Text { id: lblUTC; text: new Date().toUTCString().split(" ")[4] }
                    Timer { interval: 1000; running: true; repeat: true; onTriggered: lblUTC.text = new Date().toUTCString().split(" ")[4] }
                }
            }
        }

        // SplitView: Basics (left) and Context (right) ----------------------
        SplitView {
            id: split
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Basics panel
            Flickable {
                SplitView.preferredWidth: 680
                contentWidth: basics.implicitWidth
                contentHeight: basics.implicitHeight
                clip: true
                ColumnLayout {
                    id: basics
                    width: parent.width
                    spacing: 8
                    // Basics Card
                    Rectangle {
                        Layout.fillWidth: true
                        border.color: "#cccccc"; radius: 4
                        ColumnLayout { anchors.fill: parent; anchors.margins: 8; spacing: 6
                            RowLayout {
                                spacing: 12
                        Text { text: `Team Type: ${((teamBridge && teamBridge.isAircraftTeam)? 'Aircraft':'Ground')}` }
                        Text { text: "Role:" }
                        TextField { id: tfRole; width: 180; text: (teamBridge && teamBridge.team) ? (teamBridge.team.role || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ role: text }) }
                        Text { text: "Current Task:" }
                        Button { text: (teamBridge && teamBridge.team && teamBridge.team.current_task_id) ? `#${teamBridge.team.current_task_id}`: "Link…"; onClicked: {/* placeholder */} }
                        Text { text: "Priority:" }
                        SpinBox { id: sbPriority; from: 0; to: 5; value: (teamBridge && teamBridge.team && teamBridge.team.priority) ? teamBridge.team.priority : 0; onValueChanged: if (teamBridge) teamBridge.updateFromQml({ priority: value }) }
                    }
                    RowLayout {
                        spacing: 12
                        Text { text: "Callsign:" }
                        TextField { id: tfCall; width: 160; text: (teamBridge && teamBridge.team) ? (teamBridge.team.callsign || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ callsign: text }) }
                        Text { text: "Phone:" }
                        TextField { id: tfPhone; width: 160; text: (teamBridge && teamBridge.team) ? (teamBridge.team.phone || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ phone: text }) }
                    }
                    ColumnLayout {
                        spacing: 4
                        Text { text: "Notes:" }
                        TextArea { id: taNotes; Layout.fillWidth: true; Layout.preferredHeight: 100; text: (teamBridge && teamBridge.team) ? (teamBridge.team.notes || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ notes: text }) }
                    }
                }
            }

                    // Tabs (Ground vs Aircraft) using TabBar + StackLayout
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 0
                        TabBar {
                            id: tabs; Layout.fillWidth: true
                            TabButton { text: (teamBridge && teamBridge.isAircraftTeam) ? "Aircrew" : "Personnel" }
                            Loader { sourceComponent: (teamBridge && teamBridge.isAircraftTeam) ? aircraftTabButton : vehicleTabButton }
                            TabButton { text: "Equipment" }
                            TabButton { text: "Tasks" }
                            TabButton { text: "Log" }
                            TabButton { text: "Attachments" }
                        }
                        StackLayout { id: tabStack; Layout.fillWidth: true; Layout.fillHeight: true; currentIndex: tabs.currentIndex
                            // 0: Personnel / Aircrew
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                property int selectedMemberId: -1
                                ListView {
                                    id: membersList
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    model: teamBridge ? teamBridge.personnelList : []
                                    delegate: ItemDelegate {
                                        width: ListView.view.width
                                        text: `ID ${modelData}`
                                        onClicked: {
                                            membersList.currentIndex = index
                                            selectedMemberId = modelData
                                        }
                                    }
                                }
                                RowLayout { spacing: 6
                                    Button {
                                        text: teamBridge.isAircraftTeam ? "+ Add Aircrew" : "+ Add Member"
                                        onClicked: personnelPicker.open()
                                    }
                                    Button {
                                        text: "− Remove"
                                        onClicked: {
                                            var id = (membersList.currentIndex >= 0) ? membersList.model[membersList.currentIndex] : null
                                            if (id !== null && id !== undefined) teamBridge.removeMember(id)
                                        }
                                    }
                                    Button {
                                        text: teamBridge.isAircraftTeam ? "Set as Pilot" : "Set as Team Leader"
                                        onClicked: {
                                            var id = (membersList.currentIndex >= 0) ? membersList.model[membersList.currentIndex] : null
                                            if (id !== null && id !== undefined) teamBridge.setTeamLeader(id)
                                        }
                                    }
                                }
                                Dialogs.PersonnelPicker {
                                    id: personnelPicker
                                    roleFilter: teamBridge ? teamBridge.memberRoleFilter : ""
                                    onPicked: function(personId){ teamBridge.addMember(personId) }
                                }
                            }
                            // 1: Vehicles or Aircraft page loaded dynamically
                            Loader { sourceComponent: (teamBridge && teamBridge.isAircraftTeam) ? aircraftPage : vehiclePage }
                            // 2: Equipment
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                ListView { id: listEquip; Layout.fillWidth: true; Layout.fillHeight: true; model: (teamBridge && teamBridge.team && teamBridge.team.equipment) ? teamBridge.team.equipment : []
                                    delegate: ItemDelegate { width: ListView.view.width; text: String(modelData); onClicked: listEquip.currentIndex = index }
                                }
                                RowLayout { spacing: 6
                                    Button { text: "+ Add Equipment"; onClicked: equipmentPicker.open() }
                                    Button {
                                        text: "− Remove"
                                        onClicked: {
                                            var id = (listEquip.currentIndex >= 0) ? listEquip.model[listEquip.currentIndex] : null
                                            if (id !== null && id !== undefined) teamBridge.removeEquipment(id)
                                        }
                                    }
                                }
                                Dialogs.EquipmentPicker { id: equipmentPicker; onPicked: function(equipmentId){ teamBridge.addEquipment(equipmentId) } }
                            }
                            // 3: Tasks
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                RowLayout { spacing: 6
                                    Text { text: "Linked Task:" }
                                    Text { text: (teamBridge && teamBridge.team && teamBridge.team.current_task_id) ? `#${teamBridge.team.current_task_id}` : "(none)" }
                                }
                                RowLayout { spacing: 6
                                    Button { text: "Link Task"; onClicked: linkTaskDialog.open() }
                                    Button { text: "Unlink"; onClicked: { if (teamBridge.team.current_task_id) teamBridge.unlinkTask(teamBridge.team.current_task_id) } }
                                    Button { text: "Open Task Detail"; onClicked: teamBridge.openTaskDetail() }
                                }
                                Dialog {
                                    id: linkTaskDialog
                                    title: "Link Task"
                                    modal: true
                                    standardButtons: Dialog.Ok | Dialog.Cancel
                                    property int enteredId: -1
                                    contentItem: Row { spacing: 8
                                        Text { text: "Task ID:" }
                                        TextField { id: tfTask; width: 160; inputMethodHints: Qt.ImhDigitsOnly }
                                    }
                                    onAccepted: {
                                        var id = parseInt(tfTask.text)
                                        if (!isNaN(id) && id > 0 && teamBridge) teamBridge.linkTask(id)
                                    }
                                }
                            }
                            // 4: Log
                            TabView {
                                Layout.margins: 8
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                Tab {
                                    title: "Unit Log"
                                    ListView {
                                        anchors.fill: parent
                                        model: teamBridge ? teamBridge.unitLog() : []
                                    }
                                }
                                Tab {
                                    title: "Task History"
                                    ListView {
                                        anchors.fill: parent
                                        model: teamBridge ? teamBridge.taskHistory() : []
                                    }
                                }
                                Tab {
                                    title: "Status History"
                                    ListView {
                                        anchors.fill: parent
                                        model: teamBridge ? teamBridge.statusHistory() : []
                                    }
                                }
                                Tab {
                                    title: "ICS-214"
                                    ColumnLayout {
                                        anchors.fill: parent
                                        spacing: 6
                                        ListView {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            model: teamBridge ? teamBridge.ics214Entries() : []
                                        }
                                        RowLayout { spacing: 6
                                            Button {
                                                text: "➕ Add ICS 214 Note"
                                                onClicked: if (teamBridge) teamBridge.addIcs214Note()
                                            }
                                        }
                                    }
                                }
                            }
                            // 5: Attachments
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                ListView { Layout.fillWidth: true; Layout.fillHeight: true; model: [] }
                                RowLayout { spacing: 6
                                    Button { text: "+ Add Attachment"; enabled: false }
                                    Button { text: "Open"; enabled: false }
                                    Button { text: "Remove"; enabled: false }
                                    Button { text: "Show in Explorer"; enabled: false }
                                }
                            }
                        }

                        // Dynamic tab components for vehicles/aircraft
                        Component { id: vehicleTabButton
                            TabButton { text: "Vehicles" }
                        }
                        Component { id: aircraftTabButton
                            TabButton { text: "Aircraft" }
                        }
                        Component { id: vehiclePage
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                ListView { id: listVehicles; Layout.fillWidth: true; Layout.fillHeight: true;
                                    model: (teamBridge && teamBridge.team && teamBridge.team.vehicles) ? teamBridge.team.vehicles : []
                                    delegate: ItemDelegate { width: ListView.view.width; text: String(modelData); onClicked: listVehicles.currentIndex = index }
                                }
                                RowLayout { spacing: 6
                                    Button { text: "+ Add Vehicle"; onClicked: vehiclePicker.open() }
                                    Button {
                                        text: "− Remove"
                                        onClicked: {
                                            var id = (listVehicles.currentIndex >= 0) ? listVehicles.model[listVehicles.currentIndex] : null
                                            if (id !== null && id !== undefined) teamBridge.removeVehicle(id)
                                        }
                                    }
                                }
                                Dialogs.VehiclePicker { id: vehiclePicker; onPicked: function(vehicleId){ teamBridge.addVehicle(vehicleId) } }
                            }
                        }
                        Component { id: aircraftPage
                            ColumnLayout { Layout.margins: 8; spacing: 6; Layout.fillWidth: true; Layout.fillHeight: true
                                ListView { id: listAircraft; Layout.fillWidth: true; Layout.fillHeight: true;
                                    model: (teamBridge && teamBridge.team && teamBridge.team.aircraft) ? teamBridge.team.aircraft : []
                                    delegate: ItemDelegate { width: ListView.view.width; text: String(modelData); onClicked: listAircraft.currentIndex = index }
                                }
                                RowLayout { spacing: 6
                                    Button { text: "+ Add Aircraft"; onClicked: aircraftPicker.open() }
                                    Button {
                                        text: "− Remove"
                                        onClicked: {
                                            var id = (listAircraft.currentIndex >= 0) ? listAircraft.model[listAircraft.currentIndex] : null
                                            if (id !== null && id !== undefined) teamBridge.removeAircraft(id)
                                        }
                                    }
                                }
                                Dialogs.AircraftPicker { id: aircraftPicker; onPicked: function(aircraftId){ teamBridge.addAircraft(aircraftId) } }
                            }
                        }
                    }
                }
            }

            // Right Context: Location & Comms cards
            Flickable {
                SplitView.preferredWidth: 520
                contentWidth: rightCol.implicitWidth
                contentHeight: rightCol.implicitHeight
                clip: true
                ColumnLayout { id: rightCol; width: parent.width; spacing: 8
                    // Location & Movement
                    Rectangle { Layout.fillWidth: true; border.color: "#ccc"; radius: 4
                        ColumnLayout { anchors.fill: parent; anchors.margins: 8; spacing: 6
                            Text { text: "Location & Movement"; font.bold: true }
                            RowLayout { spacing: 8
                                Text { text: "Lat:" }
                                TextField { width: 100; text: (teamBridge && teamBridge.team) ? (teamBridge.team.last_known_lat || "") : ""; inputMethodHints: Qt.ImhFormattedNumbersOnly; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ last_known_lat: text }) }
                                Text { text: "Lon:" }
                                TextField { width: 100; text: (teamBridge && teamBridge.team) ? (teamBridge.team.last_known_lon || "") : ""; inputMethodHints: Qt.ImhFormattedNumbersOnly; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ last_known_lon: text }) }
                                Text { text: "Updated:" }
                                Text { text: (teamBridge && teamBridge.team) ? (teamBridge.team.last_update_ts || "") : "" }
                            }
                            RowLayout { spacing: 8
                                Text { text: "Route/ETA:" }
                                TextField { Layout.fillWidth: true; text: (teamBridge && teamBridge.team) ? (teamBridge.team.route || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ route: text }) }
                            }
                            ColumnLayout { spacing: 4
                                Text { text: "Recent Updates:" }
                                ListView { Layout.fillWidth: true; Layout.preferredHeight: 120; model: [] }
                            }
                        }
                    }
                    // Communications
                    Rectangle { Layout.fillWidth: true; border.color: "#ccc"; radius: 4
                        ColumnLayout { anchors.fill: parent; anchors.margins: 8; spacing: 6
                            Text { text: "Communications"; font.bold: true }
                            RowLayout { spacing: 8
                                Text { text: "Radio IDs:" }
                                TextField { Layout.fillWidth: true; text: (teamBridge && teamBridge.team) ? (teamBridge.team.radio_ids || "") : ""; onTextChanged: if (teamBridge) teamBridge.updateFromQml({ radio_ids: text }) }
                            }
                            RowLayout { spacing: 8
                                Text { text: "Preset:" }
                                ComboBox { width: 240; model: ["(placeholder)"] }
                                Button { text: "Open ICS 205"; onClicked: if (teamBridge) teamBridge.openICS205Preview() }
                            }
                        }
                    }
                }
            }
        }

        // Footer -------------------------------------------------------------
        Rectangle { Layout.fillWidth: true; height: 56; color: "#f7f7f7"; border.color: "#cccccc"; radius: 4
            RowLayout { anchors.fill: parent; anchors.margins: 8; spacing: 8
                Button { id: btnSave; text: "Save"; onClicked: if (teamBridge) teamBridge.save() }
                Button { id: btnSaveClose; text: "Save & Close"; onClicked: { if (teamBridge) teamBridge.save(); win.close(); } }
                Button { id: btnCancel; text: "Cancel"; onClicked: win.close() }
                Item { Layout.fillWidth: true }
                Button { id: btnQuickStatus; text: "Quick Status Change"; onClicked: cbStatus.popup.open() }
                Button { id: btnPrint; text: "Print Summary"; onClicked: if (teamBridge) teamBridge.printSummary() }
            }
        }
    }
}
