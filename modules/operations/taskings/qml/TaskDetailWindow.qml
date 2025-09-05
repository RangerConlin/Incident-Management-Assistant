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
    property var lookups: ({ categories: [], priorities: [], task_statuses: [] })
    property var taskDetail: null
    property var taskTeams: []
    property bool editMode: false
    ListModel { id: narrativeModel }

    signal requestClose()

    function isNewTask() {
        try { return taskDetail && taskDetail.task && taskDetail.task.category === "<New Task>"; } catch(e) { return false }
    }
    function metadataEditable() { return editMode || isNewTask() }
    function primaryTeamName() {
        if (taskTeams && taskTeams.length > 0) {
            for (var i=0;i<taskTeams.length;i++) if (taskTeams[i].primary === true) return taskTeams[i].team_name;
            return taskTeams[0].team_name;
        }
        return "";
    }
    function titleText() {
        var idtxt = taskDetail && taskDetail.task ? taskDetail.task.task_id : "";
        var ttitle = taskDetail && taskDetail.task ? taskDetail.task.title : "";
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

    Component.onCompleted: {
        if (typeof taskingsBridge !== 'undefined' && taskingsBridge) {
            lookupsLoader.load()
            if (taskId > 0) { taskLoader.load(taskId); teamsLoader.load(taskId); narrativeLoader.load(taskId) }
        }
    }

    // --- Header: Responsive Metadata (GridLayout) ---
    header: C.ToolBar {
        GridLayout {
            id: metaGrid
            anchors.fill: parent
            columns: (width > 980 ? 5 : (width > 760 ? 4 : (width > 580 ? 3 : 2)))
            rowSpacing: 6; columnSpacing: 10

            C.ComboBox { id: categoryBox; Layout.fillWidth: true; enabled: metadataEditable(); model: root.lookups.categories }
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

        // Primary Assignment (read-only)
        ColumnLayout { Layout.fillWidth: true
            RowLayout { Layout.fillWidth: true; spacing: 18
                C.Label { text: "Primary Team"; color: "#666" }
                C.Label { text: "Team Leader"; color: "#666" }
                C.Label { text: "Team Contact"; color: "#666" }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                C.TextField { readOnly: true; text: primaryTeamName(); Layout.preferredWidth: 220 }
                C.TextField { readOnly: true; text: (taskTeams && taskTeams.length>0 ? (taskTeams[0].team_leader||"") : ""); Layout.preferredWidth: 240 }
                C.TextField { readOnly: true; text: (taskTeams && taskTeams.length>0 ? (taskTeams[0].team_leader_phone||"") : ""); Layout.preferredWidth: 160 }
                Item { Layout.fillWidth: true }
            }
        }

        // Title Field
        C.TextField { id: titleField; Layout.fillWidth: true; placeholderText: "Task Title"; readOnly: !metadataEditable() }

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
                // 1. Narrative
                Item { Layout.fillWidth: true; Layout.fillHeight: true
                    C.ScrollView { anchors.fill: parent
                        ListView {
                            id: narrativeList
                            anchors.fill: parent
                            model: narrativeModel
                            header: Rectangle { height: 32; color: "#000"; width: parent.width
                                Row { anchors.fill: parent; anchors.margins: 6; spacing: 12
                                    C.Label { text: "Date/Time"; color: "#fff"; width: 100 }
                                    C.Label { text: "Entry"; color: "#fff"; Layout.fillWidth: true }
                                    C.Label { text: "Entered By"; color: "#fff"; width: 140 }
                                    C.Label { text: "Team"; color: "#fff"; width: 120 }
                                    C.Label { text: "Critical"; color: "#fff"; width: 70 }
                                }
                            }
                            delegate: Rectangle {
                                width: ListView.view.width; height: 36
                                color: (model.critical_flag===true || model.critical===true) ? "#d32f2f" : "#ffffff"
                                border.color: "#c0c0c0"
                                Row { anchors.fill: parent; anchors.margins: 6; spacing: 12
                                    C.Label { text: (model.timestamp || model.time || ""); width: 100; color: (parent.color==="#d32f2f"?"#fff":"#000") }
                                    C.Label { text: (model.entry_text || model.text || ""); Layout.fillWidth: true; color: (parent.color==="#d32f2f"?"#fff":"#000") }
                                    C.Label { text: (model.entered_by || model.by || ""); width: 140; color: (parent.color==="#d32f2f"?"#fff":"#000") }
                                    C.Label { text: (model.team_name || model.team || ""); width: 120; color: (parent.color==="#d32f2f"?"#fff":"#000") }
                                    C.Label { text: ((model.critical_flag || model.critical) ? "Yes" : "No"); width: 70; horizontalAlignment: Text.AlignHCenter; color: (parent.color==="#d32f2f"?"#fff":"#000") }
                                }
                            }
                        }
                    }
                }

                // 2. Teams
                Item { Layout.fillWidth: true; Layout.fillHeight: true
                    ColumnLayout { anchors.fill: parent
                        RowLayout { Layout.fillWidth: true; spacing: 8
                            C.Button { text: "Add Team" }
                            C.Button { text: "Edit Team" }
                            C.Button { text: "Change Status" }
                            C.Button { text: "Set Primary" }
                            Item { Layout.fillWidth: true }
                        }
                        C.ScrollView { Layout.fillWidth: true; Layout.fillHeight: true
                            ListView {
                                id: teamList
                                anchors.fill: parent
                                model: root.taskTeams
                                delegate: Rectangle {
                                    width: teamList.width; height: 32
                                    color: index % 2 ? "#fafafa" : "#ffffff"; border.color: "#ddd"
                                    Row { anchors.fill: parent; anchors.margins: 6; spacing: 10
                                        C.Label { text: (model.sortie_number || ""); width: 100 }
                                        C.Label { text: (model.primary ? "*" : ""); width: 24; horizontalAlignment: Text.AlignHCenter }
                                        C.Label { text: (model.team_name || ""); width: 160 }
                                        C.Label { text: (model.team_leader || ""); width: 180 }
                                        C.Label { text: (model.team_leader_phone || ""); width: 120 }
                                        C.Label { text: (model.status || ""); width: 120 }
                                        C.Label { text: (model.assigned_ts || ""); width: 120 }
                                        C.Label { text: (model.briefed_ts || ""); width: 120 }
                                        C.Label { text: (model.enroute_ts || ""); width: 120 }
                                        C.Label { text: (model.arrival_ts || ""); width: 120 }
                                        C.Label { text: (model.discovery_ts || ""); width: 120 }
                                        C.Label { text: (model.complete_ts || ""); width: 120 }
                                    }
                                    MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton
                                        onPressed: function(m){ if(m.button===Qt.RightButton){ teamMenu.rowIndex=index; teamMenu.popup() } }
                                    }
                                }
                            }
                        }
                        C.Menu { id: teamMenu; property int rowIndex: -1
                            C.MenuItem { text: "Change Status" }
                            C.MenuItem { text: "Open Team Detail Window" }
                            C.MenuItem { text: "Set as Primary" }
                        }
                    }
                }

                // 3. Personnel
                Item { C.Label { anchors.centerIn: parent; text: "Personnel table placeholder" } }

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
        var payload = { timestamp: new Date().toISOString(), entry_text: narrativeEntry.text, entered_by: "", team_name: "", critical_flag: false };
        dataApi.post(`/api/operations/taskings/${taskId}/narrative`, payload, function(saved){
            // Append to model optimistically
            var obj = saved || payload
            narrativeModel.append(obj)
            narrativeEntry.text = ""
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
        }
    }

    onVisibleChanged: {
        if (visible && root.taskId && root.taskId > 0) {
            // Refresh on show in case data changed while hidden
            taskLoader.load(root.taskId);
            teamsLoader.load(root.taskId);
            narrativeLoader.load(root.taskId);
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
            var pi = _indexOfInsensitive(root.lookups.priorities||[], t.priority||""); if (pi >= 0) priorityBox.currentIndex = pi;
            var si = _indexOfInsensitive(root.lookups.task_statuses||[], t.status||""); if (si >= 0) statusBox.currentIndex = si;
        } catch (e) { console.log('syncHeaderFromTask error', e) }
    }
    onTaskDetailChanged: syncHeaderFromTask()
}
