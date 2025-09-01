import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    anchors.fill: parent

    // Local properties (fed from context on load)
    property var rowsData: []
    property var headersData: []
    property int statusIdx: 2

    Component.onCompleted: {
        if (typeof taskRows !== 'undefined') rowsData = taskRows
        if (typeof taskHeaders !== 'undefined') headersData = taskHeaders
        if (typeof statusColumn !== 'undefined') statusIdx = statusColumn
    }

    function styleFor(status) {
        if (!status || !status.toLowerCase) return null;
        switch (status.toLowerCase()) {
        case "created":     return { bg: "#6e7b8b", fg: "#333333" };
        case "planned":     return { bg: "#ce93d8", fg: "#333333" };
        case "assigned":    return { bg: "#ffeb3b", fg: "#333333" };
        case "in progress": return { bg: "#17c4e8", fg: "#333333" };
        case "complete":    return { bg: "#386a3c", fg: "#333333" };
        case "cancelled":   return { bg: "#d32f2f", fg: "#333333" };
        default: return null;
        }
    }

    function toTitle(s) {
        if (!s) return "";
        return s.toString().split(" ").map(function(w){ return w.charAt(0).toUpperCase() + w.slice(1); }).join(" ");
    }

    property var statusOptions: ["Created","Planned","Assigned","In Progress","Complete","Cancelled"]

    Column {
        id: layoutRoot
        anchors.fill: parent
        spacing: 4

        // Compute column count and width so cells align like a table
        // Robust counter for Python-provided lists (may not expose length/count)
        function listCount(v) {
            if (v === undefined || v === null) return 0;
            if (v.length !== undefined) return v.length;
            if (v.count !== undefined) return v.count;
            var i = 0; while (v[i] !== undefined) i++; return i;
        }
        function cellValue(r, c) {
            // Access value directly; Python-provided arrays may not expose length/count reliably in QML
            var row = root.rowsData ? root.rowsData[r] : null;
            if (!row) return "";
            var val = row[c];
            return (val !== undefined && val !== null) ? ("" + val) : "";
        }
        property int columns: (listCount(root.headersData) > 0)
                              ? listCount(root.headersData)
                              : ((root.rowsData && listCount(root.rowsData) > 0 && root.rowsData[0])
                                  ? listCount(root.rowsData[0])
                                  : 0)
        property var columnWidths: []
        property int minColWidth: 80
        function initColumnWidths() {
            // Always recompute on width/columns changes to avoid stale zeros
            columnWidths = [];
            var c = columns > 0 ? columns : 1;
            var w = (width && width > 0) ? (width / c) : 100;
            for (var i=0;i<c;i++) columnWidths.push(w);
            console.log("[TaskStatus.qml] initColumnWidths ->", c, "cols, width=", width, "each=", w)
        }
        onWidthChanged: initColumnWidths()
        Component.onCompleted: {
            initColumnWidths();
            // Debug diagnostics
            console.log("[TaskStatus.qml] headersData length:", headersData && headersData.length,
                        "rowsData length:", rowsData && rowsData.length,
                        "computed columns:", columns);
            if (rowsData && rowsData[0] !== undefined)
                console.log("[TaskStatus.qml] first row sample:", rowsData[0]);
        }
        onColumnsChanged: {
            initColumnWidths();
            console.log("[TaskStatus.qml] columns changed ->", columns);
        }
        Connections {
            target: root
            function onRowsDataChanged() { layoutRoot.initColumnWidths(); }
            function onHeadersDataChanged() { layoutRoot.initColumnWidths(); }
        }

        // Sorting
        property int sortCol: -1
        property bool sortAsc: true
        function sortBy(col) {
            if (col < 0 || col >= columns) return;
            if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = true; }
            rowsData.sort(function(a,b){
                var av = (a && a[col] !== undefined && a[col] !== null) ? a[col].toString().toLowerCase() : "";
                var bv = (b && b[col] !== undefined && b[col] !== null) ? b[col].toString().toLowerCase() : "";
                if (av < bv) return sortAsc ? -1 : 1;
                if (av > bv) return sortAsc ? 1 : -1;
                return 0;
            });
            rowsData = rowsData.slice(0);
        }

        Rectangle { // header
            color: "#000000"; border.color: "#000000"; implicitHeight: 28; width: parent.width
            Row { width: parent.width; height: parent.height; spacing: 6
                Repeater {
                    model: root.columns
                    Rectangle {
                        id: headerCell
                        width: (index < root.columnWidths.length && root.columnWidths[index] > 0) ? root.columnWidths[index] : (root.width / Math.max(1, root.columns));
                        height: parent.height; color: "transparent"
                        Row { width: parent.width; height: parent.height; spacing: 4
                            Text {
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                text: (listCount(root.headersData) > index) ? root.headersData[index] : ""
                                color: "#ffffff"; elide: Text.ElideRight; clip: true
                            }
                            Text { anchors.verticalCenter: parent.verticalCenter; color: "#ffffff"; text: root.sortCol === index ? (root.sortAsc ? "▲" : "▼") : "" }
                        }
                        MouseArea { anchors.fill: parent; anchors.rightMargin: 8; onClicked: root.sortBy(index); hoverEnabled: true; cursorShape: Qt.PointingHandCursor }
                        Rectangle { id: divider; anchors.right: parent.right; width: 6; height: parent.height; color: maDivider.pressed || maDivider.containsMouse ? "#888" : "#555"
                            MouseArea { id: maDivider; anchors.fill: parent; cursorShape: Qt.SplitHCursor
                                property real startX: 0; property real startLeft: 0; property real startRight: 0
                                onPressed: function(mouse){ startX = mouse.x; startLeft = root.columnWidths[index]; startRight = (index+1<root.columnWidths.length?root.columnWidths[index+1]:0) }
                                onPositionChanged: function(mouse){ if(!pressed) return; var dx = mouse.x - startX; var left = Math.max(root.minColWidth, startLeft + dx); var right = startRight; if(index+1<root.columnWidths.length){ var total = startLeft + startRight; right = Math.max(root.minColWidth, total - left); left = total - right; root.columnWidths[index]=left; root.columnWidths[index+1]=right; } else { root.columnWidths[index]=left; } }
                            }
                        }
                    }
                }
            }
        }

        ScrollView {
            id: sv
            clip: true
            width: parent.width
            height: parent.height - 28 - 4

            Column {
                id: rowsCol
                width: sv.width
                Repeater {
                    id: rowRepeater
                    model: root.rowsData.length
                    Rectangle {
                        id: rowRect
                        implicitHeight: 28
                        width: rowsCol.width
                        property int rowIndex: index
                        color: {
                            var row = root.rowsData[rowRect.rowIndex]
                            var s = row ? (row[root.statusIdx] || "") : ""
                            var st = root.styleFor(s);
                            return st ? st.bg : "transparent";
                        }
                        Row { width: parent.width; height: parent.height; spacing: 6
                            Repeater { id: colRepeater; model: root.columns
                                Rectangle {
                                    width: (index < root.columnWidths.length && root.columnWidths[index] > 0) ? root.columnWidths[index] : (root.width / Math.max(1, root.columns));
                                    height: parent.height; color: "transparent"
                                    Text {
                                        renderType: Text.NativeRendering
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: root.cellValue(rowRect.rowIndex, index)
                                        color: { var row = root.rowsData[rowRect.rowIndex]; var s = row ? (row[root.statusIdx] || "") : ""; var st = root.styleFor(s); return st ? st.fg : "#000"; }
                                        elide: Text.ElideRight; clip: true
                                        onTextChanged: { if (rowRect.rowIndex === 0 && index < 2) console.log("[TaskStatus.qml] cell[0,", index, "]:", text) }
                                    }
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            onPressed: function(mouse){
                                if (mouse.button === Qt.RightButton) {
                                    contextMenu.rowIndex = rowRect.rowIndex
                                    contextMenu.popup()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Menu {
        id: contextMenu
        property int rowIndex: -1
        Repeater {
            model: root.statusOptions
            delegate: MenuItem {
                text: modelData
                onTriggered: {
                    if (contextMenu.rowIndex >= 0) {
                        root.rowsData[contextMenu.rowIndex][root.statusIdx] = text
                        root.rowsData = root.rowsData.slice(0)
                    }
                }
            }
        }
    }
}
