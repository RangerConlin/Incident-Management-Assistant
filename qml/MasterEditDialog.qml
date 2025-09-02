import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Dialog {
    id: root
    property string titleText: "Edit"
    property var columns: []           // array of {key,label,type,editable,required,options?}
    property var data: ({})            // existing row map
    // onSubmit(map) should return true on success (or a promise-like bool); close if true
    property var onSubmit: function(map) { return false }

    modal: true
    // Ensure dialog is large enough and buttons remain visible
    width: Math.min((parent ? parent.width : Screen.width) - 80, 900)
    height: Math.min((parent ? parent.height : Screen.height) - 120, 640)
    x: (parent ? parent.width : Screen.width) / 2 - width/2
    y: (parent ? parent.height : Screen.height) / 2 - height/2
    title: titleText
    standardButtons: Dialog.NoButton

    signal saved()

    property var _editables: columns.filter(function(c){ return c.editable === true })

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
                        Label { text: col.label || col.key; Layout.preferredWidth: 140 }

                Loader {
                    Layout.fillWidth: true
                    sourceComponent: (col && col.valueMap) ? enumDelegate : (
                        (function(){
                            switch ((col.type || "text")) {
                                case "multiline": return areaDelegate;
                                case "int": return intDelegate;
                                case "float": return floatDelegate;
                                case "enum": return enumDelegate;
                                case "tel": return textDelegate;
                                case "email": return textDelegate;
                                default: return textDelegate;
                            }
                        })()
                    )
                    onLoaded: {
                        if (!item) return;
                        if (item.hasOwnProperty('col')) { item.col = col; }
                        var has = root.data && root.data.hasOwnProperty(col.key);
                        if (has) {
                            if (item.hasOwnProperty('prefill')) {
                                item.prefill(root.data[col.key]);
                            } else {
                                if (item.hasOwnProperty('text')) item.text = String(root.data[col.key] ?? "");
                                if (item.hasOwnProperty('value')) item.value = root.data[col.key];
                            }
                        }
                        if (item && item.rebuild) { item.rebuild(); }
                        item.objectName = "field::" + col.key
                    }
                }
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Button { text: "Cancel"; onClicked: root.close() }
            Button {
                text: "Save"
                onClicked: {
                    var map = {};
                    var ok = true;
                    for (var i=0; i < fieldsColumn.children.length; i++) {
                        var row = fieldsColumn.children[i];
                        if (!row || !row.hasOwnProperty('col')) continue;
                        var k = row.col.key;
                        var required = !!row.col.required;
                        // find editor by objectName (loader items or direct children)
                        var editor = null;
                        for (var j = 0; j < row.children.length; j++) {
                            var ch = row.children[j];
                            if (ch.item && ch.item.objectName === 'field::' + k) { editor = ch.item; break; }
                            if (ch.objectName && ch.objectName === 'field::' + k) { editor = ch; break; }
                        }
                        var v = editor && (editor.value !== undefined ? editor.value : editor.text);
                        // Treat blank strings in enums as null (for optional fields)
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

    // Editors
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
            // receive column config from loader
            property var col: null
            property var _keys: []
            property var _labels: []
            property var value: null
            function rebuild() {
                if (col && col.valueMap) {
                    _keys = Object.keys(col.valueMap).map(function(k){ return parseInt(k) });
                    _labels = _keys.map(function(k){ return String(col.valueMap[k]) });
                    model = _labels;
                    if (currentIndex < 0) currentIndex = 0;
                    value = _keys.length > 0 ? _keys[currentIndex] : null;
                } else if (col && col.options) {
                    model = col.options;
                    if (currentIndex < 0) currentIndex = 0;
                    value = (model && model.length > 0) ? model[currentIndex] : null;
                }
            }
            function prefill(v) {
                if (col && col.valueMap) {
                    _keys = Object.keys(col.valueMap).map(function(k){ return parseInt(k) });
                    _labels = _keys.map(function(k){ return String(col.valueMap[k]) });
                    model = _labels;
                    var idx = _keys.indexOf(Number(v));
                    currentIndex = (idx >= 0 ? idx : 0);
                    value = _keys[currentIndex];
                } else if (col && col.options) {
                    model = col.options;
                    var ix = (typeof v === 'string') ? model.indexOf(v) : -1;
                    currentIndex = (ix >= 0 ? ix : 0);
                    value = model[currentIndex];
                }
            }
            Component.onCompleted: {
                rebuild();
            }
            onColChanged: rebuild()
            onCurrentIndexChanged: {
                if (col && col.valueMap) {
                    value = (_keys && _keys.length > currentIndex && currentIndex >= 0) ? _keys[currentIndex] : null;
                } else if (col && col.options) {
                    value = (model && model.length > currentIndex && currentIndex >= 0) ? model[currentIndex] : null;
                }
            }
        }
    }
}

