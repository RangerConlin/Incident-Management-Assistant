import io
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
marker='class AddTeamMemberDialog('
idx=s.find(marker)
if idx==-1:
    print('MARKER_NOT_FOUND')
else:
    header='''from __future__ import annotations

from typing import Any, Dict, Optional, List
from datetime import datetime

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPalette, QTextOption, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableView,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

'''
    ns=header+s[idx:]
    io.open(p,'w',encoding='utf-8',newline='').write(ns)
    print('HEADER_FIXED')
