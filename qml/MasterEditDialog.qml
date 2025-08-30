import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: root
    property string titleText: "Edit"
    property var columns: []           // array of {key,label,type,editable,required,options?}
    property var data: ({})            // existing row map
    // onSubmit(map) should return true on success (or a promise-like bool); close if true
    property var onSubmit: function(map) { return false }

    modal: true
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

        Repeater {
            model: root._editables
            delegate: RowLayout {
                spacing: 10
                property var col: modelData
                Label { text: col.label || col.key; Layout.preferredWidth: 140 }

                Loader {
                    Layout.fillWidth: true
                    sourceComponent: {
                        switch ((col.type || "text")) {
                        case "multiline": return areaDelegate
                        case "int": return intDelegate
                        case "float": return floatDelegate
                        case "enum": return enumDelegate
                        case "tel": return textDelegate
                        case "email": return textDelegate
                        default: return textDelegate
                        }
                    }
                    onLoaded: {
                        if (item && root.data && root.data.hasOwnProperty(col.key)) {
                            if (item.hasOwnProperty('text')) item.text = String(root.data[col.key] ?? "");
                            if (item.hasOwnProperty('value')) item.value = root.data[col.key];
                        }
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
                    for (var i=0;i<form.children.length;i++) {
                        var row = form.children[i];
                        if (!row || !row.hasOwnProperty('col')) continue;
                        var k = row.col.key;
                        var required = !!row.col.required;
                        // find editor by objectName
                        var editor = null;
                        for (var j=0;j<row.children.length;j++) {
                            var ch = row.children[j];
                            if (ch.objectName && ch.objectName === 'field::' + k) { editor = ch; break;}
                        }
                        var v = editor && (editor.value !== undefined ? editor.value : editor.text);
                        if (required && (!v || String(v).trim().length === 0)) {
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
        ComboBox { Layout.fillWidth: true; model: col && col.options ? col.options : [] }
    }
}

