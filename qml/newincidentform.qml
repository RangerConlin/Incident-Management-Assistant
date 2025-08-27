import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts

Item {
    width:400
    height:250
    signal createIncident(string number, string name, string type, string description, string location, bool isTraining)

Rectangle {
    id: rectangle
    width: parent.width
    height: parent.height
    color: "#f0f0f0"

    Column {
        id: column
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 20
        spacing: 10

        TextField { id: nameField; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 0; anchors.rightMargin: 0; placeholderText: "Incident Name" }
        TextField { id: nnumberField; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 0; anchors.rightMargin: 0; placeholderText: "Incident Number" }
        ComboBox {
            id: comboBox
            model:["SAR", "Disaster Response"]
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 0
            anchors.rightMargin: 0
            currentIndex: -1
            displayText: currentIndex === -1 ? "Incident Type" : model[currentIndex]
            editable: false
        }

        TextField { id: descriptionField; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 0; anchors.rightMargin: 0; placeholderText: "Description" }
        TextField { id: locationField; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 0; anchors.rightMargin: 0; placeholderText: "Incident Command Post Location" }
        CheckBox  { id: trainingCheck; text: "Training Incident?" ; anchors.left: parent.left; anchors.right: parent.right;anchors.leftMargin: 0 ;anchors.rightMargin: 0 }

        RowLayout {
            id: rowLayout
            y: 300
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 0
            anchors.rightMargin: 0
            Button {
                id: cancelbutton
                text: qsTr("Cancel")
                Layout.fillWidth: true
            }

            Button {
                id: createbutton
                text: "Create Incident"
                Layout.fillWidth: true
                onClicked: {

                    incidentHandler.create_incident(nnumberField.text, nameField.text, comboBox.currentText, descriptionField.text, locationField.text, trainingCheck.checked)
                }
            }
        }

    }
}
}
