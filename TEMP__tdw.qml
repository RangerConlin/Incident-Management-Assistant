import QtQuick 2.15
import QtQuick.Controls 2.15 as C
import QtQuick.Layouts 1.15

// Floating, modeless, resizable window.
// Invoke with: TaskDetailWindow { taskId: someInt; visible: true }

C.ApplicationWindow {
    id: root
    // Title: TaskID - Title - Primary Team - Status (text-only)
    title: titleText()
    visible: false
    modality: Qt.NonModal
    flags: Qt.Window
    width: 1100
    height: 720

    // --- State ---
    property int taskId: -1
    property var lookups: ({ categories: [], priorities: [], task_statuses: [], task_types_by_category: ({}) })
    property var taskDetail: null
    property var taskTeams: []
    property var taskPersonnel: []
    property bool editMode: false
    ListModel { id: narrativeModel }

    // Column sizing for Narrative list
    property int narTimeW: 160
    property int narByW: 160
    property int narTeamW: 140
    property int narCritW: 90
    function _setWidth(prop, w) {
        var mw = 60; var mx = 800;
        var v = Math.max(mw, Math.min(mx, Math.floor(w)));
        if (prop === 'time') narTimeW = v;
        else if (prop === 'by') narByW = v;
        else if (prop === 'team') narTeamW = v;
        else if (prop === 'crit') narCritW = v;
    }
    function narEntryW() {
        // Remaining width inside the row: subtract margins (2*6) and spacing (4*12)
        var vw = (typeof narrativeList !== 'undefined' && narrativeList && narrativeList.width) ? narrativeList.width : 800;
        var used = (narTimeW + narByW + narTeamW + narCritW) + (4*12) + (2*6);
        return Math.max(120, vw - used);
    }
    function _fmtTs(ts) {
        if (!ts) return "";
        try {
            var s = String(ts);
            var dot = s.indexOf('.');
            if (dot > 0) {
                var tz = '';
                var tzStart = (s.indexOf('Z', dot) >= 0) ? s.indexOf('Z', dot) : s.indexOf('+', dot);
                if (tzStart > 0) { tz = s.substring(tzStart); s = s.substring(0, tzStart); }
                s = s.substring(0, dot) + tz;
            }
            var d = new Date(s);
            if (isNaN(d.getTime())) return s;
            function pad(n){ return (n<10?('0'+n):String(n)); }
            var mm = pad(d.getUTCMonth()+1);
            var dd = pad(d.getUTCDate());
            var yy = String(d.getUTCFullYear()).slice(-2);
            var HH = pad(d.getUTCHours());
            var MM = pad(d.getUTCMinutes());
            var SS = pad(d.getUTCSeconds());
            return mm + '-' + dd + '-' + yy + ' ' + HH + ':' + MM + ':' + SS;
        } catch(e) { return String(ts); }
    }
    function _isCrit(v) {
        return v === true || v === 1 || v === '1' || v === 'true' || v === 'True' || v === 'YES' || v === 'Yes';
    }

    signal requestClose()

    function isNewTask() {
        try { return taskDetail && taskDetail.task && taskDetail.task.category === "<New Task>"; } catch(e) { return false }
    }
    function metadataEditable() { return editMode || isNewTask() }
    function primaryTeamObj() {
        if (taskTeams && taskTeams.length > 0) {
            for (var i=0;i<taskTeams.length;i++) if (taskTeams[i].primary === true) return taskTeams[i];
            return taskTeams[0];
        }
        return null;
    }
    function primaryTeamName() { var t = primaryTeamObj(); return t ? (t.team_name||"") : "" }
    function titleText() {
        var idtxt = taskDetail && taskDetail.task ? taskDetail.task.task_id : "";
        var ttitle = taskDetail && taskDetail.task ? (taskDetail.task.assignment || taskDetail.task.title || "") : "";
        var prim = primaryTeamName();
        var st = taskDetail && taskDetail.task ? taskDetail.task.status : "";
        var parts = [];
        if (idtxt) parts.push(idtxt);
        if (ttitle) parts.push(ttitle);
        if (prim) parts.push(prim);
        if (st) parts.push(st);
        return parts.length ? parts.join(" - ") : "Task Detail";
    }

    // --- Data loaders (replace with app bridge) ---
    Item { id: dataApi
        function get(url, cb) {
            // Use Python bridge only; no fallback/demo data
            if (typeof taskingsBridge !== 'undefined' && taskingsBridge) {
                try {
                    if (url.endsWith('/lookups')) { cb(taskingsBridge.getLookups()); return }
                    var m
                    if (m = url.match(/\/api\/operations\/taskings\/(\d+)$/)) { cb(taskingsBridge.getTaskDetail(parseInt(m[1]))); return }
                    if (m = url.match(/\/api\/operations\/taskings\/(\d+)\/narrative$/)) { cb(taskingsBridge.listNarrative(parseInt(m[1]))); return }
                    if (m = url.match(/\/api\/operations\/taskings\/(\d+)\/teams$/)) { cb(taskingsBridge.listTeams(parseInt(m[1]))); return }
                } catch (e) { console.log('bridge get error', e) }
            }
            // No bridge available; ignore silently to avoid log spam
            if (cb) cb(null)
        }
        function post(url, payload, cb) {
            if (typeof taskingsBridge !== 'undefined' && taskingsBridge) {
                try {
                    var m
                    if (m = url.match(/\/api\/operations\/taskings\/(\d+)\/narrative$/)) { var saved = taskingsBridge.addNarrative(parseInt(m[1]), payload); if (cb) cb(saved); return }
                } catch (e) { console.log('bridge post error', e) }
            }
            // No bridge available; ignore
            if (cb) cb(null)
        }
        function patch(url, payload, cb) {
            // No bridge available; ignore
            if (cb) cb(null)
        }
    }
    QtObject { id: lookupsLoader
        function load() {
            dataApi.get("/api/operations/taskings/lookups", function(resp){ if (resp) { root.lookups = resp; if (typeof syncHeaderFromTask === "function") syncHeaderFromTask() } })
        }
    }
    QtObject { id: taskLoader
        function load(id) {
            dataApi.get(`/api/operations/taskings/${id}`, function(resp){ if (resp) root.taskDetail = resp })
        }
    }
    QtObject { id: teamsLoader
        function load(id) {
            dataApi.get(`/api/operations/taskings/${id}/teams`, function(resp){ if (resp && resp.teams) root.taskTeams = resp.teams })
        }
    }
    QtObject { id: narrativeLoader
        function load(id) {
            dataApi.get(`/api/operations/taskings/${id}/narrative`, function(resp){
                narrativeModel.clear()
                var entries = (resp && resp.entries) ? resp.entries : []
                for (var i=0;i<entries.length;i++) {
                    narrativeModel.append(entries[i])
                }
            })
        }
    }
    QtObject { id: personnelLoader
        function load(id) {
            dataApi.get(`/api/operations/taskings/${id}/personnel`, function(resp){
                taskPersonnel = (resp && resp.people) ? resp.people : []
            })
        }
    }

    Component.onCompleted: {
        if (typeof taskingsBridge !== 'undefined' && taskingsBridge) {
            lookupsLoader.load()
            if (taskId > 0) { taskLoader.load(taskId); teamsLoader.load(taskId); narrativeLoader.load(taskId); personnelLoader.load(taskId) }
        }
    }

    // --- Header: Responsive Metadata (GridLayout) ---
    header: C.ToolBar {
        // Ensure toolbar grows in height to fit wrapped rows
        implicitHeight: Math.max(44, (metaGrid ? (metaGrid.implicitHeight + 8) : 44))
        GridLayout {
            id: metaGrid
            anchors.fill: parent
            columns: (width > 980 ? 5 : (width > 760 ? 4 : (width > 580 ? 3 : 2)))
            rowSpacing: 6; columnSpacing: 10

            C.ComboBox {
                id: categoryBox; Layout.fillWidth: true; enabled: metadataEditable(); model: root.lookups.categories
                onCurrentTextChanged: {
                    try {
                        var types = (root.lookups && root.lookups.task_types_by_category) ? root.lookups.task_types_by_category[currentText] : []
                        typeBox.model = types && types.length ? types : ["(select category)"]
                        // reset selection when category changes
                        typeBox.currentIndex = 0
                    } catch(e) { /* ignore */ }
                }
            }
            C.ComboBox { id: typeBox; Layout.fillWidth: true; enabled: metadataEditable(); model: ["(filtered by category)"] }
            C.ComboBox { id: priorityBox; Layout.fillWidth: true; enabled: metadataEditable(); model: root.lookups.priorities }
            C.ComboBox { id: statusBox; Layout.fillWidth: true; model: root.lookups.task_statuses }
            C.TextField { id: taskIdField; Layout.fillWidth: true; placeholderText: "Task ID"; readOnly: !metadataEditable() }
        }
    }

    footer: C.ToolBar {
        RowLayout { anchors.fill: parent; spacing: 8
            C.Button { text: "Close"; onClicked: { root.requestClose(); root.close() } }
        }
    }

    // --- Body ---
    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // Primary Assignment (read-only) — 2x2 grid
        ColumnLayout { Layout.fillWidth: true
            // Header labels for each column in grid below
            RowLayout { Layout.fillWidth: true; spacing: 18
                C.Label { text: "Primary Team"; color: "#666"; Layout.alignment: Qt.AlignLeft }
                Item { Layout.fillWidth: true }
                C.Label { text: "Team Contact"; color: "#666"; Layout.alignment: Qt.AlignRight }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 2; rowSpacing: 6; columnSpacing: 10
                // Upper-left: Team name (expands)
                C.TextField {
                    readOnly: true
                    text: primaryTeamName()
                    Layout.fillWidth: true
                }
                // Upper-right: empty to form 2x2 with 3 fields
                Item { Layout.preferredWidth: 140 }
                // Bottom-left: Team leader
                C.TextField {
                    readOnly: true
                    text: (primaryTeamObj() ? (primaryTeamObj().team_leader||"") : "")
                    Layout.fillWidth: true
                }
                // Bottom-right: Team leader phone
                C.TextField {
                    readOnly: true
                    text: (primaryTeamObj() ? (primaryTeamObj().team_leader_phone||"") : "")
                    Layout.preferredWidth: 220
                }
            }
        }

        // Assignment Field
        C.TextField { id: assignmentField; Layout.fillWidth: true; placeholderText: "Assignment"; readOnly: !metadataEditable() }

        // Location / Assignment name
        C.TextField { id: locationField; Layout.fillWidth: true; placeholderText: "Location / Assignment"; readOnly: !metadataEditable() }

        // Narrative Quick Entry
        RowLayout {
            Layout.fillWidth: true
            C.TextArea {
                id: narrativeEntry; Layout.fillWidth: true; placeholderText: "Type narrative; Enter=submit, Shift+Enter=newline"; wrapMode: TextEdit.Wrap
                Keys.onPressed: function(e){
                    if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
                        if (e.modifiers & Qt.ShiftModifier) { insert("\n"); e.accepted = true; }
                        else { submitNarrative(); e.accepted = true; }
                    }
                }
            }
            C.ComboBox {
                id: narCritical
                // shrink to content width (label + padding)
                width: (contentItem && contentItem.implicitWidth ? contentItem.implicitWidth + 24 : 100)
                model: ["No","Yes"]; currentIndex: 0
            }
            C.Button { text: "Add"; onClicked: submitNarrative }
        }

        // Action Buttons
        RowLayout { Layout.fillWidth: true; spacing: 8
            C.Button { text: editMode ? "Editing..." : "Edit"; onClicked: editMode = true }
            C.Button { text: "Save"; enabled: editMode; onClicked: { /* TODO persist */ editMode = false } }
            C.Button { text: "Cancel"; enabled: editMode; onClicked: { /* TODO revert */ editMode = false } }
            Item { Layout.fillWidth: true }
            C.Button { text: "Flag: Needs Assistance" }
            C.Button { text: "Add Clue" }
            C.Button { text: "Export ICS-214" }
            C.Button { text: "Assign Team"
                onClicked: {
                    if (!root.taskId || root.taskId < 1) return;
                    // Minimal flow: create a new team assignment with autogenerated team and sortie
                    var payload = { sortie_number: "T" + root.taskId + "-" + (teamList.count+1), primary: (teamList.count===0) };
                    var resp = taskingsBridge && taskingsBridge.addTeam ? taskingsBridge.addTeam(root.taskId, payload) : null;
                    if (resp && resp.teams) { root.taskTeams = resp.teams }
                }
            }
            C.Button { text: "Change Status" }
            C.Button { text: "Quick Message" }
        }

        // Tabs
        ColumnLayout { Layout.fillWidth: true; Layout.fillHeight: true
            C.TabBar { id: tabbar; Layout.fillWidth: true
                C.TabButton { text: "Narrative" }
                C.TabButton { text: "Teams" }
                C.TabButton { text: "Personnel" }
                C.TabButton { text: "Vehicles" }
                C.TabButton { text: "Assignment Details" }
                C.TabButton { text: "Communications" }
                C.TabButton { text: "Debriefing" }
                C.TabButton { text: "Log" }
                C.TabButton { text: "Attachments/Forms" }
                C.TabButton { text: "Planning" }
            }

            StackLayout { Layout.fillWidth: true; Layout.fillHeight: true; currentIndex: tabbar.currentIndex
                // 1. Narrative (embedded list)
                Item { Layout.fillWidth: true; Layout.fillHeight: true
                    C.ScrollView { anchors.fill: parent
                        ListView {
                            id: narrativeList
                            anchors.fill: parent
                            model: narrativeModel
                            header: Rectangle { height: 32; color: "#000"; width: parent.width
                                Row { anchors.fill: parent; anchors.margins: 6; spacing: 12
                                    // Time (resizable)
                                    Rectangle { width: narTimeW; color: "transparent"
                                        C.Label { anchors.centerIn: parent; text: "Date/Time"; color: "#fff" }
                                        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                            property real __startX; property real __w
                                            onPressed: { __startX = mouse.x; __w = narTimeW }
                                            onPositionChanged: { if (pressed) _setWidth('time', __w + (mouse.x-__startX)) }
                                        }
                                    }
                                    // Entry (fills remaining)
                                    Rectangle { width: narEntryW(); color: "transparent"
                                        C.Label { anchors.centerIn: parent; text: "Entry"; color: "#fff" }
                                    }
                                    // Entered By (resizable)
                                    Rectangle { width: narByW; color: "transparent"
                                        C.Label { anchors.centerIn: parent; text: "Entered By"; color: "#fff" }
                                        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                            property real __startX; property real __w
                                            onPressed: { __startX = mouse.x; __w = narByW }
                                            onPositionChanged: { if (pressed) _setWidth('by', __w + (mouse.x-__startX)) }
                                        }
                                    }
                                    // Team (resizable)
                                    Rectangle { width: narTeamW; color: "transparent"
                                        C.Label { anchors.centerIn: parent; text: "Team"; color: "#fff" }
                                        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                            property real __startX; property real __w
                                            onPressed: { __startX = mouse.x; __w = narTeamW }
                                            onPositionChanged: { if (pressed) _setWidth('team', __w + (mouse.x-__startX)) }
                                        }
                                    }
                                    // Critical (resizable)
                                    Rectangle { width: narCritW; color: "transparent"
                                        C.Label { anchors.centerIn: parent; text: "Critical"; color: "#fff" }
                                        MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                            property real __startX; property real __w
                                            onPressed: { __startX = mouse.x; __w = narCritW }
                                            onPositionChanged: { if (pressed) _setWidth('crit', __w + (mouse.x-__startX)) }
                                        }
                                    }
                                }
                            }
                            delegate: Rectangle {
                                width: ListView.view.width; height: 36
                                color: (_isCrit(model.critical_flag) || _isCrit(model.critical)) ? "#ffe5e5" : "#ffffff"
                                border.color: "#c0c0c0"
                                Row { anchors.fill: parent; anchors.margins: 6; spacing: 12
                                    C.Label { text: _fmtTs(model.timestamp || model.time || ""); width: narTimeW }
                                    C.Label { text: (model.entry_text || model.text || ""); width: narEntryW() }
                                    C.Label { text: (model.entered_by || model.by || ""); width: narByW }
                                    C.Label { text: (model.team_name || model.team || ""); width: narTeamW }
                                    C.Label { text: (_isCrit(model.critical_flag || model.critical) ? "Yes" : "No"); width: narCritW; horizontalAlignment: Text.AlignHCenter }
                                    C.ToolButton {
                                        text: "214+"
                                        onClicked: { try { taskingsBridge.addIcs214Entry(String(model.entry_text || model.text || ""), _isCrit(model.critical_flag || model.critical)) } catch(e) {} }
                                    }
                                }
                                // Right-click menu (debug delete)
                                MouseArea {
                                    anchors.fill: parent; acceptedButtons: Qt.RightButton
                                    onPressed: function(m){ if (m.button === Qt.RightButton) { narMenu.rowIndex = index; narMenu.entryId = (model.id || -1); narMenu.popup() } }
                                }
                            }
                            C.Menu { id: narMenu; property int rowIndex: -1; property int entryId: -1
                                C.MenuItem { text: "Delete Entry (debug)"; onTriggered: {
                                        if (entryId > 0) {
                                            var ok = taskingsBridge.deleteNarrative(root.taskId, entryId)
                                            if (ok) { narrativeModel.remove(rowIndex); }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                // 2. Teams
                Item { Layout.fillWidth: true; Layout.fillHeight: true
                    // Column widths and sorting
                    property int colPrimW: 28
                    property int colSortieW: 100
                    property int colNameW: 180
                    property int colLeaderW: 180
                    property int colPhoneW: 130
                    property int colStatusW: 120
                    property int colTsW: 120
                    property string sortKey: "id"
                    property bool sortAsc: true
                    function _fmtDate(ts){
                        try{ var d = new Date(ts); if (isNaN(d.getTime())) return ""; function pad(n){return n<10?('0'+n):n}
                            return pad(d.getUTCMonth()+1)+"-"+pad(d.getUTCDate())+"-"+String(d.getUTCFullYear()).slice(-2) }catch(e){ return "" }
                    }
                    function _fmtTime(ts){
                        try{ var d = new Date(ts); if (isNaN(d.getTime())) return ""; function pad(n){return n<10?('0'+n):n}
                            return pad(d.getUTCHours())+":"+pad(d.getUTCMinutes())+":"+pad(d.getUTCSeconds()) }catch(e){ return "" }
                    }
                    function sortTeams(key){
                        try{
                            sortKey = key; sortAsc = !sortAsc;
                            var arr = (root.taskTeams||[]).slice(0)
                            arr.sort(function(a,b){ var av=a[key]||""; var bv=b[key]||""; if (av==bv) return 0; return (av<bv? (sortAsc?-1:1) : (sortAsc?1:-1)) })
                            root.taskTeams = arr
                        }catch(e){}
                    }
                    ColumnLayout { anchors.fill: parent
                        RowLayout { Layout.fillWidth: true; spacing: 8
                            C.Button { text: "Add Team"; onClicked: {
                                    var all = taskingsBridge.listAllTeams();
                                    // Simple prompt for now: pick first team not already assigned
                                    if (all && all.teams && all.teams.length){
                                        var existing = {}
                                        for (var i=0;i<root.taskTeams.length;i++){ existing[root.taskTeams[i].team_id] = true }
                                        var picked = null
                                        for (var j=0;j<all.teams.length;j++){ var tm = all.teams[j]; if (!existing[tm.team_id]) { picked = tm; break } }
                                        var payload = { team_id: picked ? picked.team_id : null, primary: (teamList.count===0) }
                                        var resp = taskingsBridge.addTeam(root.taskId, payload)
                                        if (resp && resp.teams) root.taskTeams = resp.teams
                                    }
                                }
                            }
                            C.Button { text: "Edit Team" }
                            C.Button { text: "Change Status"; onClicked: { if (teamList.currentIndex>=0) teamMenu.changeStatus(teamList.currentIndex) } }
                            C.Button { text: "Set Primary"; onClicked: { if (teamList.currentIndex>=0) teamMenu.setPrimary(teamList.currentIndex) } }
                            Item { Layout.fillWidth: true }
                        }
                        C.ScrollView { Layout.fillWidth: true; Layout.fillHeight: true
                            ListView {
                                id: teamList
                                anchors.fill: parent
                                clip: true
                                model: root.taskTeams
                                header: Rectangle { height: 32; width: parent.width; color: "#000"
                                    Row { anchors.fill: parent; anchors.margins: 6; spacing: 8
                                        Rectangle { width: colPrimW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "P"; color: "#fff" } }
                                        Rectangle { width: colSortieW; color: "transparent"
                                            C.Label { anchors.centerIn: parent; text: "Sortie"; color: "#fff" }
                                            MouseArea { anchors.fill: parent; onDoubleClicked: sortTeams('sortie_number') }
                                            MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                                property real __sx; property real __w
                                                onPressed: { __sx = mouse.x; __w = colSortieW }
                                                onPositionChanged: { if (pressed) { var v = __w + (mouse.x-__sx); if (v>60 && v<500) colSortieW = v } }
                                            }
                                        }
                                        Rectangle { width: colNameW; color: "transparent"
                                            C.Label { anchors.centerIn: parent; text: "Team Name"; color: "#fff" }
                                            MouseArea { anchors.fill: parent; onDoubleClicked: sortTeams('team_name') }
                                            MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                                property real __sx; property real __w
                                                onPressed: { __sx = mouse.x; __w = colNameW }
                                                onPositionChanged: { if (pressed) { var v = __w + (mouse.x-__sx); if (v>100 && v<600) colNameW = v } }
                                            }
                                        }
                                        Rectangle { width: colLeaderW; color: "transparent"
                                            C.Label { anchors.centerIn: parent; text: "Team Leader"; color: "#fff" }
                                            MouseArea { anchors.fill: parent; onDoubleClicked: sortTeams('team_leader') }
                                            MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                                property real __sx; property real __w
                                                onPressed: { __sx = mouse.x; __w = colLeaderW }
                                                onPositionChanged: { if (pressed) { var v = __w + (mouse.x-__sx); if (v>100 && v<600) colLeaderW = v } }
                                            }
                                        }
                                        Rectangle { width: colPhoneW; color: "transparent"
                                            C.Label { anchors.centerIn: parent; text: "Phone"; color: "#fff" }
                                            MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                                property real __sx; property real __w
                                                onPressed: { __sx = mouse.x; __w = colPhoneW }
                                                onPositionChanged: { if (pressed) { var v = __w + (mouse.x-__sx); if (v>100 && v<300) colPhoneW = v } }
                                            }
                                        }
                                        Rectangle { width: colStatusW; color: "transparent"
                                            C.Label { anchors.centerIn: parent; text: "Status"; color: "#fff" }
                                            MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 6; cursorShape: Qt.SplitHCursor
                                                property real __sx; property real __w
                                                onPressed: { __sx = mouse.x; __w = colStatusW }
                                                onPositionChanged: { if (pressed) { var v = __w + (mouse.x-__sx); if (v>100 && v<240) colStatusW = v } }
                                            }
                                        }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Assigned"; color: "#fff" } }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Briefed"; color: "#fff" } }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Enroute"; color: "#fff" } }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Arrival"; color: "#fff" } }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Discovery"; color: "#fff" } }
                                        Rectangle { width: colTsW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Complete"; color: "#fff" } }
                                    }
                                }
                                delegate: Rectangle {
                                    width: teamList.width; height: 40
                                    color: (index % 2 ? "#fafafa" : "#ffffff"); border.color: "#ddd"
                                    Row { anchors.fill: parent; anchors.margins: 6; spacing: 8
                                        // Primary checkbox
                                        C.CheckBox { width: colPrimW; checked: !!model.primary; enabled: true
                                            onToggled: if (checked) { var res = taskingsBridge.setPrimary(root.taskId, model.id); if (res && res.teams) root.taskTeams = res.teams }
                                        }
                                        // Sortie (editable)
                                        C.TextField { text: (model.sortie_number||""); width: colSortieW; onEditingFinished: taskingsBridge.updateSortie(model.id, text) }
                                        // Team name
                                        C.Label { text: (model.team_name||""); width: colNameW }
                                        // Leader name
                                        C.Label { text: (model.team_leader||""); width: colLeaderW }
                                        // Phone
                                        C.Label { text: (model.team_leader_phone||""); width: colPhoneW }
                                        // Status dropdown (limited by category)
                                        C.ComboBox { width: colStatusW
                                            model: (function(){
                                                try { var cat = root.taskDetail && root.taskDetail.task ? root.taskDetail.task.category : "Other";
                                                      var m = root.lookups && root.lookups.team_status_by_category ? root.lookups.team_status_by_category[cat] : [];
                                                      return m || []
                                                } catch(e) { return [] }
                                            })()
                                            currentIndex: {
                                                var st = String(model.status||"").toLowerCase();
                                                var opts = (function(){ try { var cat = root.taskDetail && root.taskDetail.task ? root.taskDetail.task.category : "Other"; return root.lookups.team_status_by_category[cat] || [] }catch(e){ return [] }})();
                                                for (var i=0;i<opts.length;i++){ if (String(opts[i]).toLowerCase()===st) return i } return -1
                                            }
                                            onActivated: function(i){
                                                var val = (typeof textAt === 'function') ? textAt(i) : (currentText || "");
                                                var ok = taskingsBridge.changeTeamStatus(model.id, val);
                                                if (ok) {
                                                    var resp = taskingsBridge.listTeams(root.taskId);
                                                    if (resp && resp.teams) root.taskTeams = resp.teams;
                                                }
                                            }
                                        }
                                        // Timestamps (two-row: date/time)
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.assigned_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.assigned_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.briefed_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.briefed_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.enroute_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.enroute_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.arrival_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.arrival_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.discovery_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.discovery_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                        Column { width: colTsW; spacing: 0
                                            C.Label { text: _fmtDate(model.complete_ts||""); horizontalAlignment: Text.AlignHCenter }
                                            C.Label { text: _fmtTime(model.complete_ts||""); color: "#666"; horizontalAlignment: Text.AlignHCenter }
                                        }
                                    }
                                    MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton
                                        onPressed: function(m){ if(m.button===Qt.RightButton){ teamMenu.rowIndex=index; teamMenu.popup() } }
                                        onClicked: { teamList.currentIndex = index }
                                    }
                                }
                            }
                        }
                        C.Menu {
                            id: teamMenu; property int rowIndex: -1
                            function changeStatus(idx){ try { var item = root.taskTeams[idx]; if (!item) return; /* Open inline combo is preferred; keep stub here */ } catch(e){} }
                            function setPrimary(idx){ try { var item = root.taskTeams[idx]; if (!item) return; var res = taskingsBridge.setPrimary(root.taskId, item.id); if (res && res.teams) root.taskTeams = res.teams } catch(e){} }
                            C.MenuItem { text: "Change Status"; onTriggered: changeStatus(rowIndex) }
                            C.MenuItem { text: "Open Team Detail Window"; onTriggered: { try { var item = root.taskTeams[rowIndex]; if (item && item.team_id) taskingsBridge.openTeamDetail(item.team_id) } catch(e){} } }
                            C.MenuItem { text: "Set as Primary"; onTriggered: setPrimary(rowIndex) }
                            C.MenuSeparator {}
                            C.MenuItem { text: "Remove Team"; onTriggered: { try { var item = root.taskTeams[rowIndex]; if (!item) return; if (taskingsBridge.removeTeam(item.id)) { root.taskTeams.splice(rowIndex,1) } } catch(e){} } }
                        }
                    }
                }

                // 3. Personnel
                Item { Layout.fillWidth: true; Layout.fillHeight: true
                    property int colActW: 40
                    property int colNameW: 200
                    property int colIdW: 80
                    property int colRankW: 100
                    property int colRoleW: 140
                    property int colOrgW: 160
                    property int colPhoneW: 140
                    property int colTeamW: 160
                    property string sortKey: "name"
                    property bool sortAsc: true
                    function sortPeople(key){ try{ sortKey=key; sortAsc=!sortAsc; var arr=(taskPersonnel||[]).slice(0); arr.sort(function(a,b){ var av=a[key]||""; var bv=b[key]||""; if(av==bv) return 0; return (av<bv?(sortAsc?-1:1):(sortAsc?1:-1))}); taskPersonnel=arr }catch(e){} }
                    ColumnLayout { anchors.fill: parent
                        C.ScrollView { Layout.fillWidth: true; Layout.fillHeight: true
                            ListView {
                                id: pplList
                                anchors.fill: parent
                                model: taskPersonnel
                                clip: true
                                header: Rectangle { height: 32; width: parent.width; color: "#000"
                                    Row { anchors.fill: parent; anchors.margins: 6; spacing: 8
                                        Rectangle { width: colActW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "A"; color: "#fff" } }
                                        Rectangle { width: colNameW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Name"; color: "#fff" } ; MouseArea { anchors.fill: parent; onDoubleClicked: sortPeople('name') } }
                                        Rectangle { width: colIdW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "ID"; color: "#fff" } }
                                        Rectangle { width: colRankW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Rank"; color: "#fff" } }
                                        Rectangle { width: colRoleW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Role"; color: "#fff" } ; MouseArea { anchors.fill: parent; onDoubleClicked: sortPeople('role') } }
                                        Rectangle { width: colOrgW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Organization"; color: "#fff" } }
                                        Rectangle { width: colPhoneW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Phone"; color: "#fff" } }
                                        Rectangle { width: colTeamW; color: "transparent"; C.Label { anchors.centerIn: parent; text: "Team"; color: "#fff" } ; MouseArea { anchors.fill: parent; onDoubleClicked: sortPeople('team_name') } }
                                    }
                                }
                                delegate: Rectangle {
                                    width: pplList.width; height: 36
                                    color: index % 2 ? "#fafafa" : "#ffffff"; border.color: "#ddd"
                                    Row { anchors.fill: parent; anchors.margins: 6; spacing: 8
                                        C.CheckBox { width: colActW; checked: !!model.active; enabled: false }
                                        C.Label { text: (model.name||""); width: colNameW }
                                        C.Label { text: String(model.id||""); width: colIdW }
                                        C.Label { text: (model.rank||""); width: colRankW }
                                        C.Label { text: (model.role||""); width: colRoleW }
                                        C.Label { text: (model.organization||""); width: colOrgW }
                                        C.Label { text: (model.phone||""); width: colPhoneW }
                                        C.Label { text: (model.team_name||""); width: colTeamW }
                                    }
                                }
                            }
                        }
                    }
                }

                // 4. Vehicles
                Item { C.Label { anchors.centerIn: parent; text: "Vehicles table placeholder" } }

                // 5. Assignment Details
                Item { ColumnLayout { anchors.fill: parent
                        C.TabBar { id: subTab; Layout.fillWidth: true
                            C.TabButton { text: "Ground Info" }
                            C.TabButton { text: "Air Info" }
                        }
                        StackLayout { Layout.fillWidth: true; Layout.fillHeight: true; currentIndex: subTab.currentIndex
                            Item { C.Label { anchors.centerIn: parent; text: "Ground information fields" } }
                            Item { C.Label { anchors.centerIn: parent; text: "Air information fields" } }
                        }
                } }

                // 6. Communications
                Item { C.Label { anchors.centerIn: parent; text: "ICS 205-style table placeholder" } }

                // 7. Debriefing
                Item { ColumnLayout { anchors.fill: parent
                        C.Button { text: "Add Debrief" }
                        ListView { Layout.fillWidth: true; Layout.fillHeight: true; model: [] }
                } }

                // 8. Log
                Item { C.Label { anchors.centerIn: parent; text: "Audit trail placeholder" } }

                // 9. Attachments/Forms
                Item { C.Label { anchors.centerIn: parent; text: "Attachments table placeholder" } }

                // 10. Planning
                Item { C.Label { anchors.centerIn: parent; text: "Strategic linkages placeholder" } }
            }
        }
    }

    // --- Actions ---
    function submitNarrative() {
        if (!narrativeEntry.text || !taskId || taskId < 1) return;
        var payload = { timestamp: new Date().toISOString(), entry_text: narrativeEntry.text, entered_by: "", team_name: "", critical_flag: (narCritical.currentIndex === 1) };
        dataApi.post(`/api/operations/taskings/${taskId}/narrative`, payload, function(saved){
            // Append to model optimistically
            var obj = saved || payload
            narrativeModel.append(obj)
            narrativeEntry.text = ""
            narCritical.currentIndex = 0
            // scroll to bottom
            if (narrativeList && narrativeList.count>0) narrativeList.positionViewAtEnd()
        });
    }

    // Trigger data load when taskId is set or when the window becomes visible
    onTaskIdChanged: {
        if (root.taskId && root.taskId > 0) {
            lookupsLoader.load();
            taskLoader.load(root.taskId);
            teamsLoader.load(root.taskId);
            narrativeLoader.load(root.taskId);
            personnelLoader.load(root.taskId);
        }
    }

    onVisibleChanged: {
        if (visible && root.taskId && root.taskId > 0) {
            // Refresh on show in case data changed while hidden
            taskLoader.load(root.taskId);
            teamsLoader.load(root.taskId);
            narrativeLoader.load(root.taskId);
            personnelLoader.load(root.taskId);
        }
    }

    // --- Helpers to sync UI from loaded task detail ---
    function _indexOfInsensitive(arr, value) {
        try {
            var v = (value||"").toString().toLowerCase();
            for (var i=0;i<arr.length;i++) if ((arr[i]||"").toString().toLowerCase()===v) return i;
        } catch(e) {}
        return -1;
    }
    function syncHeaderFromTask() {
        try {
            var t = (taskDetail && taskDetail.task) ? taskDetail.task : null;
            if (!t) return;
            taskIdField.text = t.task_id || "";
            var ci = _indexOfInsensitive(root.lookups.categories||[], t.category||""); if (ci >= 0) categoryBox.currentIndex = ci;
            // set type list and selection when detail is loaded
            try {
                var types = (root.lookups && root.lookups.task_types_by_category) ? root.lookups.task_types_by_category[t.category] : []
                typeBox.model = types && types.length ? types : ["(select category)"]
                var ti = _indexOfInsensitive(types||[], t.task_type||""); if (ti >= 0) typeBox.currentIndex = ti; else typeBox.currentIndex = 0
            } catch(e) {}
            var pi = _indexOfInsensitive(root.lookups.priorities||[], t.priority||""); if (pi >= 0) priorityBox.currentIndex = pi;
            var si = _indexOfInsensitive(root.lookups.task_statuses||[], t.status||""); if (si >= 0) statusBox.currentIndex = si;
            locationField.text = t.location || "";
        } catch (e) { console.log('syncHeaderFromTask error', e) }
    }
    onTaskDetailChanged: syncHeaderFromTask()
}
