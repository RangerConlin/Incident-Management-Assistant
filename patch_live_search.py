from pathlib import Path
p=Path('modules/logistics/checkin/widgets/checkin_window.py')
s=p.read_text(encoding='utf-8')
# 1) Ensure QTimer is imported
s=s.replace('from PySide6.QtCore import Qt','from PySide6.QtCore import Qt, QTimer')
# 2) After creating search_edit, wire textChanged and add timer fields
marker='self.search_edit.setObjectName("SearchBox")\n        self.search_edit.returnPressed.connect(self._on_search_requested)'
inject='self.search_edit.setObjectName("SearchBox")\n        # Live search as you type\n        try:\n            self.search_edit.textChanged.connect(self._on_search_text_changed)\n        except Exception:\n            pass\n        self._search_timer = QTimer(self)\n        try:\n            self._search_timer.setSingleShot(True); self._search_timer.setInterval(250)\n            self._search_timer.timeout.connect(self._on_search_requested)\n        except Exception:\n            pass\n        self.search_edit.returnPressed.connect(self._on_search_requested)'
if marker in s:
    s=s.replace(marker, inject)
# 3) Add handler method if not present
if '_on_search_text_changed' not in s:
    add_after='def _on_search_requested(self) -> None:  # pragma: no cover - UI signal\n        self._run_search()\n'
    repl=add_after+"\n    def _on_search_text_changed(self, _text: str) -> None:  # pragma: no cover - UI signal\n        try:\n            self._search_timer.start()\n        except Exception:\n            self._run_search()\n\n"
    s=s.replace(add_after, repl)
p.write_text(s,encoding='utf-8')
print('PATCHED')
