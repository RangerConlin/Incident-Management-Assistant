import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    signal submit(string text, bool critical, var tags, var files)
    property bool critical: false

    RowLayout {
        anchors.fill: parent
        CheckBox { id: criticalBox; text: "Critical" }
        TextArea { id: textEdit; Layout.fillWidth: true; placeholderText: "Write note..." }
        Button { text: "Submit"; onClicked: root.submit(textEdit.text, criticalBox.checked, [], []) }
    }
}
