import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Dialog {
    id: root
    property string titleText: "Edit"
    // array of objects: { key, label, type, editable, required, options?, valueMap? }
    property var columns: []
    // existing row map
    property var data: ({})
    // onSubmit(map) should return true on success (or a truthy value); dialog closes if true
    property var onSubmit: function(map) { return false }

    modal: true
    // size & centering
    width: Math.min((parent ? parent.width : Screen.width) - 80, 900)
    height: Math.min((parent ? parent.height : Screen.height) - 120, 640)
    x: (parent ? parent.width : Screen.width) / 2 - width/2
    y: (parent ? parent.height : Screen.height) / 2 - height/2
    title: titleText
    standardButtons: Dialog.NoButton

    signal saved()

    // guard against null/undefined columns
    property var _editables: (columns || []).filter(function(c){ return c && c.editable === true })

    // ---------- CONTENT ----------
    ColumnLayout {
        id: form
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        // Scrollable field area
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                id: fieldsColumn
                width: parent ? parent.width : undefined
                spacing: 10

                Repeater {
                    model: root._editables
                    delegate: RowLayout {
                        spacing: 10
                        property var col: modelData

                        Label {
                            text: (col && col.label) ? col.label : (col ? col.key : "")
                            Layout.preferredWidth: 140
                        }

                        Loader {
                            Layout.fillWidth: true
                            sourceComponent: (col && (col.type === "enum" || col.valueMap || col.options)) ? enumDelegate
                                              : (col && col.type === "multiline") ? areaDelegate
                                              : (col && col.type === "int") ? intDelegate
                                              : (col && col.type === "float") ? floatDelegate
                                              : textDelegate
                            function _apply() {
                                if (!item) return;
                                if (item.hasOwnProperty('col')) { item.col = col; }

                                var has = root.data && col && root.data.hasOwnProperty(col.key);
                                if (has) {
                                    if (item.hasOwnProperty('prefill')) {
                                        item.prefill(root.data[col.key]);
                                    } else {
                                        if (item.hasOwnProperty('text')) item.text = String(root.data[col.key] === undefined ? "" : root.data[col.key]);
                                        if (item.hasOwnProperty('value')) item.value = root.data[col.key];
                                    }
                                } else {
                                    if (item.hasOwnProperty('text')) item.text = "";
                                    if (item.hasOwnProperty('value')) item.value = null;
                                }
                                if (item && item.rebuild) { item.rebuild(); }
                                item.objectName = "field::" + col.key;
                            }
                            onLoaded: _apply()
                            Connections {
                                target: root
                                function onDataChanged() { parent._apply() }
                            }
                        }
                    }
                }
            }
        }

        // Footer buttons
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Button { text: "Cancel"; onClicked: root.close() }
            Button {
                text: "Save"
                onClicked: {
                    var map = {};
                    var ok = true;

                    // iterate over rows created by the Repeater
                    for (var i = 0; i < fieldsColumn.children.length; i++) {
                        var row = fieldsColumn.children[i];
                        if (!row || row.col === undefined) continue;
                        var k = row.col.key;
                        var required = !!row.col.required;

                        // find editor by objectName (Loader's item or direct child)
                        var editor = null;
                        for (var j = 0; j < row.children.length; j++) {
                            var ch = row.children[j];
                            if (ch && ch.item && ch.item.objectName === 'field::' + k) { editor = ch.item; break; }
                            if (ch && ch.objectName && ch.objectName === 'field::' + k) { editor = ch; break; }
                        }

                        var v = null;
                        if (editor) {
                            if (editor.value !== undefined) v = editor.value;
                            else if (editor.text !== undefined) v = editor.text;
                        }

                        // Treat blank strings as null (useful for optional enums)
                        if (v === "") v = null;

                        if (required && (v === null || v === undefined || (typeof v === 'string' && String(v).trim().length === 0))) {
                            ok = false;
                            editor && editor.forceActiveFocus && editor.forceActiveFocus();
                            break;
                        }
                        map[k] = v;
                    }

                    if (!ok) return;

                    try {
                        var res = root.onSubmit(map);
                        if (res === true || res === 1) {
                            root.saved();
                            root.close();
                        }
                    } catch (e) {
                        console.log('Save error:', e);
                    }
                }
            }
        }
    }

    // ---------- EDITOR COMPONENTS ----------
    Component { id: textDelegate
        TextField { Layout.fillWidth: true; selectByMouse: true }
    }
    Component { id: areaDelegate
        TextArea { Layout.fillWidth: true; Layout.preferredHeight: 100; wrapMode: Text.WordWrap }
    }
    Component { id: intDelegate
        SpinBox { Layout.preferredWidth: 140; from: -2147483648; to: 2147483647 }
    }
    Component { id: floatDelegate
        TextField { Layout.fillWidth: true; inputMethodHints: Qt.ImhFormattedNumbersOnly }
    }
    Component { id: enumDelegate
        ComboBox {
            id: cb
            Layout.fillWidth: true
            // column config from Loader
            property var col: null
            property var _keys: []
            property var _labels: []
            property var value: null

            function rebuild() {
                if (col && col.valueMap) {
                    _keys = Object.keys(col.valueMap).map(function(k){ return parseInt(k) });
                    _labels = _keys.map(function(k){ return String(col.valueMap[k]) });
                    cb.model = _labels;
                    if (cb.currentIndex < 0) cb.currentIndex = 0;
                    cb.value = _keys.length > 0 ? _keys[cb.currentIndex] : null;
                } else if (col && col.options) {
                    cb.model = col.options;
                    if (cb.currentIndex < 0) cb.currentIndex = 0;
                    cb.value = (cb.model && cb.model.length > 0) ? cb.model[cb.currentIndex] : null;
                } else {
                    cb.model = [];
                    cb.value = null;
                }
            }
            function prefill(v) {
                if (col && col.valueMap) {
                    _keys = Object.keys(col.valueMap).map(function(k){ return parseInt(k) });
                    _labels = _keys.map(function(k){ return String(col.valueMap[k]) });
                    cb.model = _labels;
                    var idx = _keys.indexOf(Number(v));
                    cb.currentIndex = (idx >= 0 ? idx : 0);
                    cb.value = _keys.length > 0 ? _keys[cb.currentIndex] : null;
                } else if (col && col.options) {
                    cb.model = col.options;
                    var ix = (typeof v === 'string') ? cb.model.indexOf(v) : -1;
                    cb.currentIndex = (ix >= 0 ? ix : 0);
                    cb.value = (cb.model && cb.model.length > 0) ? cb.model[cb.currentIndex] : null;
                } else {
                    cb.model = [];
                    cb.value = null;
                }
            }
            Component.onCompleted: rebuild()
            onColChanged: rebuild()
            onCurrentIndexChanged: {
                if (col && col.valueMap) {
                    cb.value = (_keys && _keys.length > cb.currentIndex && cb.currentIndex >= 0) ? _keys[cb.currentIndex] : null;
                } else if (col && col.options) {
                    cb.value = (cb.model && cb.model.length > cb.currentIndex && cb.currentIndex >= 0) ? cb.model[cb.currentIndex] : null;
                }
            }
        }
    }
}
