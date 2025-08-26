import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// Mission selection window with filtering and CRUD actions
ApplicationWindow {
    id: window
    width: 1100
    height: 700
    visible: true
    title: "Mission Selection"

    // Currently selected proxy row (-1 means none)
    property int selectedRow: -1

    // --- Header with filters -------------------------------------------------
    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 8

            // Free text search
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Search name/number/ICP/area…"
                onTextChanged: proxy.setTextFilter(text)
            }

            // Status filter
            ComboBox {
                id: statusBox
                model: ["All", "Active", "Planned", "Completed", "Archived"]
                onCurrentTextChanged: proxy.setStatusFilter(currentText)
            }

            // Type filter
            ComboBox {
                id: typeBox
                // Known mission types; expand as needed
                model: ["All", "Search and Rescue", "Disaster Relief", "Other"]
                onCurrentTextChanged: proxy.setTypeFilter(currentText)
            }

            // Training filter
            ComboBox {
                id: trainingBox
                model: ["All", "Only Training", "Only Real"]
                onCurrentIndexChanged: proxy.setTrainingFilter(currentIndex)
            }

            // Reset all filters
            Button {
                text: "Reset"
                onClicked: {
                    searchField.text = ""
                    statusBox.currentIndex = 0
                    typeBox.currentIndex = 0
                    trainingBox.currentIndex = 0
                    proxy.setTextFilter("")
                    proxy.setStatusFilter("All")
                    proxy.setTypeFilter("All")
                    proxy.setTrainingFilter(0)
                }
            }
        }
    }

    // --- Main content -------------------------------------------------------
    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        // Table of missions
        TableView {
            id: table
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: proxy
            columnSpacing: 1
            rowSpacing: 1
            rowHeightProvider: function(row) { return 36 }
            sortIndicatorVisible: true
            onSortIndicatorColumnChanged: proxy.sort(sortIndicatorColumn, sortIndicatorOrder)
            onSortIndicatorOrderChanged: proxy.sort(sortIndicatorColumn, sortIndicatorOrder)

            // Row background + hover/selection handling
            rowDelegate: Rectangle {
                required property int row
                implicitHeight: 36
                color: window.selectedRow === row ? "#cce8ff" : (hovered ? "#f5f5f5" : "transparent")
                border.width: 0
                property bool hovered: false

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: parent.hovered = true
                    onExited: parent.hovered = false
                    onClicked: window.selectedRow = row
                    onDoubleClicked: controller.loadMission(proxy, row)
                }
            }

            // Columns with per-column delegates
            TableViewColumn {
                role: "id"
                title: "ID"
                width: 50
                delegate: Text {
                    required property var model
                    text: model.id
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "number"
                title: "Number"
                width: 100
                delegate: Text {
                    required property var model
                    text: model.number
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "name"
                title: "Mission Name"
                width: 200
                delegate: Text {
                    required property var model
                    text: model.name
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "type"
                title: "Type"
                width: 120
                delegate: Text {
                    required property var model
                    text: model.type
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "status"
                title: "Status"
                width: 100
                delegate: Text {
                    required property var model
                    text: model.status
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "start_time"
                title: "Start (UTC)"
                width: 150
                delegate: Text {
                    required property var model
                    text: model.start_time
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "end_time"
                title: "End (UTC)"
                width: 150
                delegate: Text {
                    required property var model
                    text: model.end_time
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "is_training"
                title: "Training"
                width: 80
                delegate: Text {
                    required property var model
                    text: model.is_training ? "Yes" : "No"
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
            TableViewColumn {
                role: "icp_location"
                title: "ICP"
                width: 200
                delegate: Text {
                    required property var model
                    text: model.icp_location
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 4
                    rightPadding: 4
                    elide: Text.ElideRight
                }
            }
        }

        // CRUD action buttons
        ColumnLayout {
            spacing: 8
            Layout.preferredWidth: 140

            Button {
                text: "Load"
                enabled: window.selectedRow >= 0
                onClicked: controller.loadMission(proxy, window.selectedRow)
            }

            Button {
                text: "Edit"
                enabled: window.selectedRow >= 0
                onClicked: controller.editMission(proxy, window.selectedRow)
            }

            Button {
                text: "Delete"
                enabled: window.selectedRow >= 0
                onClicked: controller.deleteMission(proxy, window.selectedRow)
            }

            Button {
                text: "New Mission"
                onClicked: controller.newMission()
            }
        }
    }

    // Friendly empty state if model is empty
    Label {
        anchors.centerIn: parent
        text: "No missions found. Check filters or ensure data/master.db has a missions table."
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        width: parent.width * 0.6
        visible: proxy.rowCount === 0
    }
}

