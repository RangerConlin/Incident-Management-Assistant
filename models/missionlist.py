from PySide6.QtCore import QAbstractListModel, Qt, QModelIndex

class MissionListModel(QAbstractListModel):
    def __init__(self, missions=None):
        super().__init__()
        self._missions = missions or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._missions)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._missions):
            return None

        mission = self._missions[index.row()]
        if role == Qt.UserRole:
            return mission["id"]
        elif role == Qt.UserRole + 1:
            return mission["name"]
        elif role == Qt.UserRole + 2:
            return mission["number"]
        elif role == Qt.UserRole + 3:
            return mission["type"]
        elif role == Qt.UserRole + 4:
            return mission["status"]
        elif role == Qt.UserRole + 5:
            return mission["icp_location"]
        return None

    def roleNames(self):
        return {
            Qt.UserRole: b"id",
            Qt.UserRole + 1: b"name",
            Qt.UserRole + 2: b"number",
            Qt.UserRole + 3: b"type",
            Qt.UserRole + 4: b"status",
            Qt.UserRole + 5: b"icp_location",
        }

    def get_mission_number(self, row):
        if 0 <= row < len(self._missions):
            return self._missions[row]['number']
        return None
