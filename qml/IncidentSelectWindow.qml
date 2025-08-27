// qml/IncidentSelectWindow.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

// Python must provide these as context properties:
//   proxy: IncidentProxyModel
//   controller: IncidentController

Item {
    id: root
    width: 1000
    height: 640

    // ---- Palette ----
    property color cBg:           "#0b1220"
    property color cHeaderBg:     "#111827"
    property color cHeaderBorder: "#374151"
    property color cRowHover:     "#1f2937"
    property color cRowSelected:  "#27496d"
    property color cText:         "#e5e7eb"

    // Selection & sorting
    property int selectedRow: -1
    property int sortColumn: 4
    property int sortOrder: Qt.DescendingOrder

    // ---- Column model (ListModel so width updates propagate) ----
    ListModel {
        id: columnModel
        // Use colWidth (not "width") to avoid clashing with Item.width
        ListElement { title: "Number";        roleName: "number";      colWidth: 140 }
        ListElement { title: "Incident Name"; roleName: "name";        colWidth: 320 }
        ListElement { title: "Type";          roleName: "type";        colWidth: 140 }
        ListElement { title: "Status";        roleName: "status";      colWidth: 140 }
        ListElement { title: "Start (UTC)";   roleName: "start_time";  colWidth: 160 }
        ListElement { title: "End (UTC)";     roleName: "end_time";    colWidth: 160 }
        ListElement { title: "Training";      roleName: "is_training"; colWidth: 120 }
        ListElement { title: "ICP";           roleName: "icp_location"; colWidth: 220 }
    }

    property int minColumnWidth: 80
    function totalColumnWidth() {
        var w = 0;
        for (var i = 0; i < columnModel.count; ++i) w += columnModel.get(i).colWidth;
        return w;
    }

    // Background
    Rectangle { anchors.fill: parent; color: cBg }

    // ---------------- Top filter bar ----------------
    Frame {
        id: filterBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        padding: 10

        RowLayout {
            anchors.fill: parent
            spacing: 10

            TextField {
                id: searchBox
                Layout.fillWidth: true
                placeholderText: "Search name/number/ICP/area…"
                onTextChanged: controller.setFilterText(text)
            }
            ComboBox {
                id: statusBox
                Layout.preferredWidth: 160
                model: ["All", "Active", "Planned", "Completed", "Archived"]
                onCurrentTextChanged: proxy.setStatusFilter(currentIndex === 0 ? "" : currentText)
            }
            ComboBox {
                id: typeBox
                Layout.preferredWidth: 160
                model: ["All", "SAR", "Fire", "Planned Event", "Disaster"]
                onCurrentTextChanged: proxy.setTypeFilter(currentIndex === 0 ? "" : currentText)
            }
            ComboBox {
                id: trainingBox
                Layout.preferredWidth: 160
                model: ["All", "Only Training", "Only Real"]   // 0,1,2
                onCurrentIndexChanged: controller.setTrainingFilter(currentIndex)
            }

            Button {
                text: "Reset"
                onClicked: {
                    searchBox.text = "";
                    statusBox.currentIndex = 0;
                    typeBox.currentIndex = 0;
                    trainingBox.currentIndex = 0;
                }
            }
        } // close RowLayout

        // Ensure default state on open
        Component.onCompleted: {
            searchBox.text = "";
            statusBox.currentIndex = 0;   // clears status filter
            typeBox.currentIndex = 0;     // clears type filter
            trainingBox.currentIndex = 0; // clears training filter
        }
    } // close Frame (filterBar)

    // ---------------- Main content ----------------
    Item {
        id: content
        anchors.top: filterBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 10

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            // --- Header (resizable columns, NO scrollbar) ---
            Rectangle {
                Layout.fillWidth: true
                height: 36
                color: cHeaderBg
                border.color: cHeaderBorder

                Flickable {
                    id: headerF
                    anchors.fill: parent
                    contentWidth: totalColumnWidth()
                    contentHeight: parent.height
                    interactive: false
                    clip: true

                    Row {
                        id: headerRow
                        spacing: 0
                        height: parent.height
                        width: totalColumnWidth()

                        Repeater {
                            model: columnModel
                            delegate: Rectangle {
                                height: parent.height
                                width: colWidth
                                color: "transparent"

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 6

                                    Label {
                                        text: title
                                        font.bold: true
                                        color: cText
                                        verticalAlignment: Text.AlignVCenter
                                        elide: Text.ElideRight
                                    }

                                    ToolButton {
                                        text: (root.sortColumn === index
                                               ? (root.sortOrder === Qt.AscendingOrder ? "↑" : "↓")
                                               : "⇅")
                                        onClicked: {
                                            if (root.sortColumn === index) {
                                                root.sortOrder = (root.sortOrder === Qt.AscendingOrder
                                                                  ? Qt.DescendingOrder
                                                                  : Qt.AscendingOrder);
                                            } else {
                                                root.sortColumn = index;
                                                root.sortOrder = Qt.AscendingOrder;
                                            }
                                            proxy.sort(root.sortColumn, root.sortOrder)
                                        }
                                    }
                                }

                                // Visible divider + resize grip on right edge
                                Rectangle {
                                    id: grip
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 8
                                    color: "transparent"

                                    // divider line that highlights on hover/drag
                                    Rectangle {
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 1
                                        height: parent.height - 8
                                        color: headerGripMa.pressed ? "#9CA3AF"
                                             : (headerGripMa.containsMouse ? "#6B7280" : "#374151")
                                    }

                                    MouseArea {
                                        id: headerGripMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.SizeHorCursor
                                        property real startX: 0
                                        property real startW: 0
                                        onPressed: {
                                            startX = mouse.x
                                            startW = columnModel.get(index).colWidth
                                        }
                                        onPositionChanged: if (pressed) {
                                            var delta = mouse.x - startX
                                            var nw = Math.max(minColumnWidth, startW + delta)
                                            columnModel.setProperty(index, "colWidth", nw)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // --- Table area (only THIS shows scrollbars) ---
            Item {
                id: tableArea
                Layout.fillWidth: true
                Layout.fillHeight: true

                Flickable {
                    id: bodyF
                    anchors.fill: parent
                    contentWidth: totalColumnWidth()
                    contentHeight: list.contentHeight
                    flickableDirection: Flickable.HorizontalAndVerticalFlick
                    interactive: true

                    // Sync header position to body scroll
                    onContentXChanged: headerF.contentX = contentX

                    // Only the body exposes scrollbars
                    ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                    ScrollBar.vertical:   ScrollBar { policy: ScrollBar.AsNeeded; parent: bodyF }

                    // Vertical list; width equals total columns
                    ListView {
                        id: list
                        width: totalColumnWidth()
                        height: Math.max(parent.height, contentHeight)
                        anchors.top: parent.top
                        anchors.left: parent.left
                        clip: true
                        model: proxy
                        interactive: true
                        currentIndex: root.selectedRow

                        delegate: Rectangle {
                            id: rowRect
                            width: totalColumnWidth()
                            height: 38
                            color: (index === root.selectedRow)
                                   ? cRowSelected
                                   : (rowMa.containsMouse ? cRowHover : cBg)
                            border.color: cHeaderBorder

                            MouseArea {
                                id: rowMa
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: root.selectedRow = index
                                onDoubleClicked: controller.loadIncident(proxy, index)
                            }

                            // Values align with column order
                            property var values: [
                                (model.number        || ""),
                                (model.name          || ""),
                                (model.type          || ""),
                                (model.status        || ""),
                                (model.start_time    ? String(model.start_time) : ""),
                                (model.end_time      ? String(model.end_time)   : ""),
                                (model.is_training   ? "Yes" : "No"),
                                (model.icp_location  || "")
]


                            Row {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 0

                                Repeater {
                                    model: columnModel
                                    delegate: Item {
                                        width: colWidth
                                        height: parent.height

                                        Label {
                                            anchors.fill: parent
                                            text: (rowRect.values[index] !== undefined && rowRect.values[index] !== null)
                                                ? String(rowRect.values[index])
                                                : ""
                                            color: cText
                                            elide: Text.ElideRight
                                            wrapMode: Text.NoWrap
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty overlay
                    Rectangle {
                        anchors.fill: parent
                        visible: list.count === 0
                        color: "transparent"
                        Label {
                            anchors.centerIn: parent
                            text: "No incidents found. Check filters or create a new mission."
                            color: cText
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            // --- Bottom action bar (fixed; never overlaps) ---
            Frame {
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                background: Rectangle { color: cHeaderBg; border.color: cHeaderBorder; radius: 0 }
                padding: 8

                RowLayout {
                    anchors.fill: parent
                    spacing: 10

                    Label {
                        text: (root.selectedRow >= 0 && proxy.rowCount() > 0)
                              ? "Row " + (root.selectedRow + 1) + " selected"
                              : "Select an incident to enable actions"
                        color: cText
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignLeft
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Button {
                        text: "Select"
                        enabled: root.selectedRow >= 0 && proxy.rowCount() > 0
                        onClicked: controller.loadIncident(proxy, root.selectedRow)
                    }
                    Button {
                        text: "Load"
                        enabled: root.selectedRow >= 0 && proxy.rowCount() > 0
                        onClicked: controller.loadIncident(proxy, root.selectedRow)
                    }
                    Button {
                        text: "Edit"
                        enabled: root.selectedRow >= 0 && proxy.rowCount() > 0
                        onClicked: controller.editIncident(proxy, root.selectedRow)
                    }
                    Button {
                        text: "Delete"
                        enabled: root.selectedRow >= 0 && proxy.rowCount() > 0
                        onClicked: controller.deleteIncident(proxy, root.selectedRow)
                    }
                    Button {
                        text: "New Incident"
                        onClicked: controller.newIncident()
                    }
                }
            }
        }
    }
}    
