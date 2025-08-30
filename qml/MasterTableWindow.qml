import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "./" as Shared
import "./components" as C

Item {
    id: root
    focus: true

    // Injected API/config
    property string windowTitle: "Master Catalog"
    property var columns: []                 // [{ key, label, width?, editable?, type?, required? }]
    property string primaryKey: "id"
    property string searchPlaceholder: "Search..."
    property var bridgeListFn: function(q){ return [] }
    property var bridgeCreateFn: function(m){ return -1 }
    property var bridgeUpdateFn: function(id,m){ return false }
    property var bridgeDeleteFn: function(id){ return false }
    // Optional Qt model (QAbstractItemModel). When set, rows[] is ignored for display.
    property var model: null
    property var defaultSort: ({ key: primaryKey, order: "asc" })
    property string editFormTitle: "Edit"

    width: 1000
    height: 640

    signal rowsRefreshed(int count)

    property var rows: []     // legacy array mode when no Qt model provided
    property int selectedRow: -1
    property var selectedId: null

    // Sum of configured column widths (fallback 140 each)
    function columnsTotalWidth() {
        var w = 0;
        for (var i=0; i<columns.length; ++i) w += (columns[i].width || 140);
        return w;
    }

    function _sortRows(list) {
        var k = defaultSort && defaultSort.key ? defaultSort.key : primaryKey;
        var asc = !defaultSort || (defaultSort.order || "asc") === "asc";
        list.sort(function(a,b){
            var va = (a && a[k] !== undefined) ? a[k] : null;
            var vb = (b && b[k] !== undefined) ? b[k] : null;
            if (va === vb) return 0;
            if (va === null) return asc ? -1 : 1;
            if (vb === null) return asc ? 1 : -1;
            if (typeof va === "number" && typeof vb === "number") return asc ? va - vb : vb - va;
            va = String(va).toLowerCase();
            vb = String(vb).toLowerCase();
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });
    }

    function refresh(q) {
        var keepSelId = (selectedRow >= 0 && rows[selectedRow]) ? rows[selectedRow][primaryKey] : null;
        var keepY = table.contentY;

        if (model) {
            // In Qt model mode, Python side handles refresh; just emit count if available
            try {
                rowsRefreshed(model.rowCount ? model.rowCount() : 0)
            } catch (e) { rowsRefreshed(0) }
        } else {
            try {
                var data = bridgeListFn(q || searchBar.text) || [];
                _sortRows(data);
                rows = data;
                rowsRefreshed(rows.length);
            } catch (e) { console.log("list error:", e); }
        }

        // restore selection
        selectedRow = -1;
        if (keepSelId !== null) {
            for (var i=0; i<rows.length; i++) {
                if (rows[i][primaryKey] === keepSelId) { selectedRow = i; break; }
            }
        }
        // restore vertical position
        table.contentY = keepY;
    }

    function addRow() {
        editor.titleText = editFormTitle || "Add";
        editor.data = {};
        editor.onSubmit = function(map){
            var id = bridgeCreateFn(map);
            if (id && id > 0) { refresh(""); return true; }
            return false;
        }
        editor.open();
    }

    function editRow() {
        if (selectedRow < 0 || selectedRow >= rows.length) return;
        var current = rows[selectedRow];
        editor.titleText = editFormTitle || "Edit";
        editor.data = current;
        editor.onSubmit = function(map){
            var id = current[primaryKey];
            var ok = bridgeUpdateFn(id, map);
            if (ok === true) { refresh(""); return true; }
            return false;
        }
        editor.open();
    }

    property var _pendingDeleteId: null
    function deleteRow() {
        if (selectedRow < 0 || selectedRow >= rows.length) return;
        var current = rows[selectedRow];
        _pendingDeleteId = current[primaryKey];
        confirm.text = "Delete selected item?";
        confirm.open();
    }

    Keys.onPressed: (ev) => {
        if (ev.modifiers & Qt.ControlModifier && ev.key === Qt.Key_F) { searchBar.forceActiveFocus(); ev.accepted = true; }
        else if (ev.modifiers & Qt.ControlModifier && ev.key === Qt.Key_N) { addRow(); ev.accepted = true; }
        else if (ev.key === Qt.Key_Return || ev.key === Qt.Key_Enter) { editRow(); ev.accepted = true; }
        else if (ev.key === Qt.Key_Delete) { deleteRow(); ev.accepted = true; }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8

        // Top toolbar
        ToolBar {
            Layout.fillWidth: true
            RowLayout {
                anchors.fill: parent
                spacing: 8
                C.SearchBar {
                    id: searchBar
                    placeholder: searchPlaceholder
                    Layout.fillWidth: true
                    onSearchChanged: function(newText) { refresh(newText) }
                }
                Button { text: "Add"; onClicked: addRow() }
                Button { text: "Edit"; enabled: selectedRow >= 0; onClicked: editRow() }
                Button { text: "Delete"; enabled: selectedRow >= 0; onClicked: deleteRow() }
            }
        }

        ScrollView {
            id: hScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff

            Item {
                id: tableContainer
                implicitWidth: columnsTotalWidth()
                implicitHeight: headerBar.height + table.contentHeight
                width: implicitWidth
                height: Math.max(hScroll.height, implicitHeight)

                Rectangle {
                    id: headerBar
                    x: 0
                    y: 0
                    width: columnsTotalWidth()
                    height: 28
                    color: "#f0f0f0"
                    border.color: "#d0d0d0"
                    clip: true

                    Row {
                        id: colsRow
                        anchors.fill: parent
                        spacing: 0
                        Repeater {
                            model: columns
                            delegate: Rectangle {
                                width: (modelData.width || 140)
                                height: 28
                                color: "transparent"
                                border.color: "#d0d0d0"
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label || modelData.key
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                ListView {
                    id: table
                    x: 0
                    y: headerBar.height
                    width: columnsTotalWidth()
                    height: Math.max(0, hScroll.height - headerBar.height)
                    clip: true
                    model: (root.model ? root.model : rows)
                    boundsBehavior: Flickable.DragAndOvershootBounds
                    flickableDirection: Flickable.VerticalFlick
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    highlight: Rectangle { color: "#e0f0ff" }
                    currentIndex: selectedRow

                    delegate: Item {
                        width: columnsTotalWidth()
                        height: 28
                        Rectangle { anchors.fill: parent; color: (index % 2 === 0 ? "#ffffff" : "#f7f7f7"); border.color: "#eaeaea" }

                        property int rowIndex: index

                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 0
                            Repeater {
                                model: columns
                                delegate: Rectangle {
                                    width: (modelData.width || 140)
                                    height: 28
                                    color: "transparent"
                                    border.color: "#eaeaea"
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.left: parent.left
                                        anchors.leftMargin: 6
                                        // New binding: in Qt-model mode, use __row map
                                        text: root.model
                                              ? ((__row && __row[modelData.key] !== undefined && __row[modelData.key] !== null)
                                                  ? String(__row[modelData.key]) : "")
                                              : ((rows[rowIndex] && rows[rowIndex][modelData.key] !== undefined && rows[rowIndex][modelData.key] !== null)
                                                  ? String(rows[rowIndex][modelData.key]) : "")
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                selectedRow = index;
                                if (root.model) {
                                    try { selectedId = __row && __row[primaryKey] !== undefined ? __row[primaryKey] : null; }
                                    catch (e) { selectedId = null }
                                } else {
                                    selectedId = (rows[index] ? rows[index][primaryKey] : null)
                                }
                            }
                            onDoubleClicked: editRow()
                        }
                    }
                }
            }
        }

        ToolBar {
            Layout.fillWidth: true
            Label {
                padding: 8
                text: root.model ? (root.model.rowCount() + " items") : (rows.length + " items")
            }
        }
    }

    C.ConfirmDialog {
        id: confirm
        onAccepted: {
            if (_pendingDeleteId !== null) {
                try {
                    var ok = bridgeDeleteFn(_pendingDeleteId);
                    if (ok === true) refresh("");
                } catch(e) { console.log("delete error", e); }
                _pendingDeleteId = null;
            }
        }
    }

    Shared.MasterEditDialog { id: editor; columns: root.columns }

    Component.onCompleted: refresh("")
}
