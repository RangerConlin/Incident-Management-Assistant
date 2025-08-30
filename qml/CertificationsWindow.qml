import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "./" as Shared
import "./components" as C

Shared.MasterTableWindow {
  id: root
  windowTitle: "Edit Certification Types"
  searchPlaceholder: "Search certifications"
  primaryKey: "id"
  defaultSort: ({ key: "code", order: "asc" })
  model: CertificationsModel
  columns: [
    { key: "id", label: "ID", type: "int", editable: false, width: 60 },
    { key: "code", label: "Code", type: "text", editable: true, required: true, width: 120 },
    { key: "name", label: "Name", type: "text", editable: true, required: true, width: 240 },
    { key: "description", label: "Description", type: "multiline", editable: true, width: 300 },
    { key: "category", label: "Category", type: "text", editable: true, width: 150 },
    { key: "issuing_organization", label: "Issuing Org", type: "text", editable: true, width: 180 },
    { key: "parent_certification_id", label: "Parent ID", type: "int", editable: true, width: 100 }
  ]
  // actions still use catalogBridge; viewing uses Qt model

  header: ToolBar {
    RowLayout {
      anchors.fill: parent
      spacing: 8
      C.SearchBar {
        id: searchBar
        placeholder: searchPlaceholder
        Layout.fillWidth: true
        onSearchChanged: refresh(text)
      }
      Button { text: "Add"; onClicked: addRow() }
      Button { text: "Edit"; enabled: selectedRow >= 0; onClicked: editRow() }
      Button { text: "Delete"; enabled: selectedRow >= 0; onClicked: deleteRow() }
      Button { text: "Assign to Personnel"; enabled: selectedRow >= 0; onClicked: assignDlg.open() }
    }
  }

  Dialog {
    id: assignDlg
    modal: true
    title: "Assign Certification"
    standardButtons: Dialog.NoButton
    property var people: []
    x: root.x + 80
    y: root.y + 80

    ColumnLayout {
      anchors.margins: 16
      anchors.fill: parent
      spacing: 10
      RowLayout {
        spacing: 10
        Label { text: "Personnel"; Layout.preferredWidth: 100 }
        ComboBox {
          id: personBox
          Layout.preferredWidth: 280
          textRole: "name"
          valueRole: "id"
          model: assignDlg.people
        }
      }
      RowLayout {
        spacing: 10
        Label { text: "Level"; Layout.preferredWidth: 100 }
        SpinBox { id: levelBox; from: 0; to: 3; value: 0 }
      }
      RowLayout {
        Layout.alignment: Qt.AlignRight
        spacing: 8
        Button { text: "Cancel"; onClicked: assignDlg.close() }
        Button { text: "Assign"; onClicked: {
            if (selectedRow < 0) return;
            var certId = root.selectedId;
            var pid = personBox.currentValue;
            var lvl = levelBox.value;
            var ok = catalogBridge.assignCertificationToPersonnel(certId, pid, lvl);
            if (ok) assignDlg.close();
        } }
      }
    }

    onOpened: {
      try { people = catalogBridge.listPersonnel(""); } catch (e) { people = []; }
    }
  }
}
