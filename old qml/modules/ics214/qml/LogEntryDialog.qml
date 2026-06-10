// LogEntryDialog.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dlg
    modal: false
    title: isEdit ? "Edit 214 Entry" : "New 214 Entry"
    standardButtons: Dialog.NoButton

    // --- Preset by the opener, but user-editable ---
    // scope: section | team | person | task
    property string scope: "section"
    property string scopeLabel: "Section"
    // scopeTargetId: e.g., team_id/person_id/task_id or empty for section
    property string scopeTargetId: ""
    property string scopeTargetName: "Operations"

    // Data providers injected from Python (models or arrays)
    // Expect a list of objects: [{ id: "ops", name: "Operations" }, ...]
    property var sectionOptions: []
    property var teamOptions: []
    property var personOptions: []
    property var taskOptions: []

    // Entry fields
    property bool isEdit: false
    property string enteredBy: ""
    property string whenLocal: ""   // prefilled from app (string)
    property bool critical: false
    property string tagsText: ""     // comma-separated
    property string entryText: ""

    // Signals to the controller
    signal saveRequested(string whenLocal, string enteredBy, bool critical,
                         string tagsText, string entryText,
                         string scope, string scopeTargetId)
    signal cancelRequested()

    width: 720; contentHeight: col.implicitHeight + 24

    function currentOptions() {
        if (scope === "team") return teamOptions;
        if (scope === "person") return personOptions;
        if (scope === "task") return taskOptions;
        return sectionOptions; // default Section
    }

    function indexOfId(list, id) {
        for (var i = 0; i < list.length; i++) if (list[i].id === id) return i;
        return -1;
    }

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // --- Destination picker row ---
        GroupBox {
            title: "Log Destination"
            Layout.fillWidth: true
            GridLayout {
                columns: 6; columnSpacing: 12; rowSpacing: 8

                Label { text: "Scope" }
                ComboBox {
                    id: cboScope
                    Layout.preferredWidth: 160
                    model: [ {key:"section", label:"Section"},
                             {key:"team", label:"Team"},
                             {key:"person", label:"Person"},
                             {key:"task", label:"Task"} ]
                    textRole: "label"
                    onCurrentIndexChanged: {
                        dlg.scope = model[currentIndex].key
                        // update target to first available option for new scope
                        var opts = dlg.currentOptions();
                        if (opts.length > 0) {
                            dlg.scopeTargetId = opts[0].id
                            dlg.scopeTargetName = opts[0].name
                        } else {
                            dlg.scopeTargetId = ""
                            dlg.scopeTargetName = ""
                        }
                    }
                    Component.onCompleted: {
                        // select by current dlg.scope
                        for (var i=0; i<model.length; ++i) if (model[i].key === dlg.scope) { currentIndex = i; break; }
                    }
                }

                Label { text: "Target" }
                ComboBox {
                    id: cboTarget
                    Layout.fillWidth: true
                    model: dlg.currentOptions()
                    textRole: "name"
                    onActivated: (idx) => {
                        if (idx >= 0 && idx < model.length) {
                            dlg.scopeTargetId = model[idx].id
                            dlg.scopeTargetName = model[idx].name
                        }
                    }
                    Component.onCompleted: {
                        var opts = dlg.currentOptions();
                        var idx = dlg.indexOfId(opts, dlg.scopeTargetId)
                        currentIndex = idx >= 0 ? idx : 0
                    }
                }

                // Spacer
                Item { Layout.columnSpan: 2; Layout.fillWidth: true }
            }
        }

        // --- Meta row ---
        GridLayout {
            columns: 2; columnSpacing: 12; rowSpacing: 8
            Layout.fillWidth: true

            Label { text: "Date/Time" }
            TextField { text: dlg.whenLocal; onTextChanged: dlg.whenLocal = text }
            Label { text: "Entered By" }
            TextField { text: dlg.enteredBy; onTextChanged: dlg.enteredBy = text }
            Label { text: "Critical" }
            CheckBox { checked: dlg.critical; onToggled: dlg.critical = checked }
            Label { text: "Tags" }
            TextField { placeholderText: "comma,separated"; text: dlg.tagsText; onTextChanged: dlg.tagsText = text }
        }

        Label { text: "Entry" }
        TextArea {
            id: entry
            Layout.fillWidth: true
            Layout.preferredHeight: 200
            wrapMode: TextArea.Wrap
            text: dlg.entryText
            onTextChanged: dlg.entryText = text
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Button { text: "Cancel"; onClicked: { dlg.cancelRequested(); dlg.close(); } }
            Button {
                text: dlg.isEdit ? "Save" : "Add Entry"
                enabled: entry.text.trim().length > 0 && (dlg.scope === "section" || dlg.scopeTargetId.length > 0)
                onClicked: dlg.saveRequested(dlg.whenLocal, dlg.enteredBy, dlg.critical, dlg.tagsText, dlg.entryText, dlg.scope, dlg.scopeTargetId)
            }
        }
    }
}
