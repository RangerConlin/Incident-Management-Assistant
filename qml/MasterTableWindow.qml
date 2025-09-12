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
    property var columns: []                 // [{ key, label, width?, editable?, type?, required?, valueMap?, toDisplay?(v), fromDisplay?(v) }]
    // Resizable columns: user overrides applied on top of column.width
    property var columnWidthOverrides: []    // number[] same length as columns
    property string primaryKey: "id"
    property string searchPlaceholder: "Search..."
    property var bridgeListFn: function(q){ return [] }
    property var bridgeCreateFn: function(m){ return -1 }
    property var bridgeUpdateFn: function(id,m){ return false }
    property var bridgeDeleteFn: function(id){ return false }
    // Optional Qt model (QAbstractItemModel). When set, rows[] is ignored for display.
    property var model: null
    property var defaultSort: ({ key: primaryKey, order: "asc" })
    // Optional: enable model-driven ORDER BY when a Qt model is provided
    property string tableName: ""
    // Optional: override select columns; defaults to '*' when empty
    property var selectColumns: []
    property string editFormTitle: "Edit"

    width: 1000
    height: 640

    // initial refresh handled at end of component

    signal rowsRefreshed(int count)

    property var rows: []     // legacy array mode when no Qt model provided
    property int selectedRow: -1
    property var selectedId: null
    // Optional: function(rowIndex:int) -> color string or null for default
    property var rowColorForIndex: null

    // Sum of configured column widths (fallback 140 each)
    function _colWidth(i) {
        var hasCols = (columns && columns.length !== undefined);
        var defw = (hasCols && columns[i] && columns[i].width) ? columns[i].width : 140;
        if (columnWidthOverrides && columnWidthOverrides.length > i && columnWidthOverrides[i] > 0) return columnWidthOverrides[i];
        return defw;
    }
    function columnsTotalWidth() {
        var w = 0;
        var cols = (columns && columns.length !== undefined) ? columns : [];
        for (var i=0; i<cols.length; ++i) w += _colWidth(i);
        return w;
    }
    function setColumnWidth(i, w) {
        var arr = columnWidthOverrides ? columnWidthOverrides.slice() : [];
        while (arr.length <= i) arr.push(0);
        arr[i] = Math.max(60, Math.floor(w));
        columnWidthOverrides = arr; // reassign to trigger bindings
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

    function _isNumericKey(k) {
        var cols = (columns && columns.length !== undefined) ? columns : [];
        for (var i=0; i<cols.length; ++i) {
            if (cols[i].key === k) {
                var t = (cols[i].type || "").toLowerCase();
                return (t === "int" || t === "number");
            }
        }
        return false;
    }

    function _orderClause() {
        var k = defaultSort && defaultSort.key ? defaultSort.key : primaryKey;
        var ord = !defaultSort || (defaultSort.order || "asc") === "asc" ? "ASC" : "DESC";
        return _isNumericKey(k) ? (k + " " + ord) : (k + " COLLATE NOCASE " + ord);
    }

    function refresh(q) {
        var keepSelId = (selectedRow >= 0 && rows[selectedRow]) ? rows[selectedRow][primaryKey] : null;
        var keepY = table.contentY;

        if (model) {
            // In Qt model mode, if tableName is provided, build a sorted SELECT
            try {
                if (tableName && model.setQuery) {
                    var cols = (selectColumns && selectColumns.length > 0)
                              ? selectColumns.join(", ")
                              : "*";
                    var sql = "SELECT " + cols + " FROM " + tableName + " ORDER BY " + _orderClause();
                    model.setQuery(sql);
                } else if (model.reload) {
                    model.reload();
                }
            } catch (e) { /* ignore */ }
            try {
                var cnt = model.rowCount ? model.rowCount() : 0;
                rowsRefreshed(cnt)
                console.log('[MasterTableWindow] model mode refresh; rowCount=', cnt)
            } catch (e) { rowsRefreshed(0) }
        } else {
            try {
                var data = bridgeListFn(q || searchBar.text) || [];
                _sortRows(data);
                rows = data;
                rowsRefreshed(rows.length);
                console.log('[MasterTableWindow] list mode refresh; rows=', rows.length)
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
        if (selectedRow < 0) return;
        var current = null;
        if (root.model && root.model.rowMap) {
            try { current = root.model.rowMap(selectedRow); } catch (e) { current = null }
        }
        if (!current) {
            if (selectedRow >= 0 && selectedRow < rows.length) current = rows[selectedRow];
        }
        if (!current) return;
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
                implicitHeight: headerBar.height + table.height
                width: implicitWidth
                height: hScroll.height

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
                            model: (columns || [])
                            delegate: Rectangle {
                                width: _colWidth(index)
                                height: 28
                                color: "transparent"
                                border.color: "#d0d0d0"
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label || modelData.key
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: function() {
                                        var k = modelData.key;
                                        if (!k) return;
                                        if (defaultSort && defaultSort.key === k) {
                                            defaultSort = { key: k, order: ((defaultSort.order || "asc") === "asc" ? "desc" : "asc") };
                                        } else {
                                            defaultSort = { key: k, order: "asc" };
                                        }
                                        refresh("");
                                    }
                                }
                                // Resize handle on the right edge
                                MouseArea {
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    anchors.right: parent.right
                                    width: 6
                                    cursorShape: Qt.SplitHCursor
                                    acceptedButtons: Qt.LeftButton
                                    property real __startX
                                    property real __startW
                                    onPressed: { __startX = mouse.x; __startW = parent.width; }
                                    onPositionChanged: {
                                        if (!pressed) return;
                                        var dx = mouse.x - __startX;
                                        setColumnWidth(index, __startW + dx);
                                    }
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
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    highlight: Rectangle { color: "#e0f0ff" }
                    currentIndex: selectedRow

                    delegate: Item {
                        width: columnsTotalWidth()
                        height: 28
                        Rectangle {
                            anchors.fill: parent
                            color: (rowIndex === selectedRow
                                   ? "#dbeafe"
                                   : (rowColorForIndex && rowColorForIndex(rowIndex))
                                     ? rowColorForIndex(rowIndex)
                                     : (index % 2 === 0 ? "#ffffff" : "#f7f7f7"))
                            border.color: "#eaeaea"
                        }

                        property int rowIndex: index
                        // When using a Qt model, fetch values per cell via model.value(row,key)

                        Row {
                            anchors.fill: parent
                            spacing: 0
                            Repeater {
                                model: (columns || [])
                                delegate: Rectangle {
                                    width: _colWidth(index)
                                    height: 28
                                    color: "transparent"
                                    border.color: "#eaeaea"
                                Text {
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.leftMargin: 6
                                    anchors.topMargin: 6
                                    // In Qt-model mode, query by role name via value(row,key)
                                    text: (function(){
                                        var v = root.model
                                                ? root.model.value(rowIndex, modelData.key)
                                                : (rows[rowIndex] ? rows[rowIndex][modelData.key] : null);
                                        // Per-column formatter first
                                        if (modelData.toDisplay && typeof modelData.toDisplay === 'function') {
                                            try { var dv = modelData.toDisplay(v, rowIndex); if (dv !== undefined && dv !== null) return String(dv); } catch(e) {}
                                        }
                                        // Then value map
                                        if (modelData.valueMap) {
                                            try { if (v in modelData.valueMap) return String(modelData.valueMap[v]); } catch(e) {}
                                        }
                                        return (v !== undefined && v !== null) ? String(v) : "";
                                    })()
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
                                    try { var v = root.model.value(index, primaryKey); selectedId = (v !== undefined && v !== null) ? v : null; }
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

    // Trigger initial load after the event loop ticks to ensure context models are ready
    Component.onCompleted: Qt.callLater(function(){ refresh("") })
}
