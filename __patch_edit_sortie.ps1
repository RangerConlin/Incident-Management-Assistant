$path = 'modules/operations/taskings/task_detail_widget.py'
$content = Get-Content $path -Raw
# 1) Enable editing on Teams table (DoubleClick/Selected/EditKey)
$content = $content -replace "self._teams_table.setEditTriggers\(QAbstractItemView.NoEditTriggers\)", "self._teams_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)"
# 2) After creating _teams_model/_teams_table, connect itemChanged once
$hook = "self._teams_table.setColumnHidden(0, True)"
$inject = @"
        self._teams_table.setColumnHidden(0, True)
        try:
            # Persist edits in the Sortie column
            self._teams_model.itemChanged.connect(self._on_team_item_changed)
        except Exception:
            pass
"@
$content = $content -replace [regex]::Escape($hook), [regex]::Escape($inject)
# 3) In load_teams(), mark only Sortie editable and others read-only; block signals during populate
$loadSig = "def load_teams\(self\) -> None:\n"
$blockStart = @"
    def load_teams(self) -> None:
        try:
            self._teams_model.blockSignals(True)
        except Exception:
            pass
"@
$content = $content -replace $loadSig, $blockStart
# After appending each row, set editables
$rowAppendRegex = "self\._teams_model\.appendRow\(row\)"
$rowAppendInject = @"
            # Only allow editing Sortie column; others read-only
            try:
                for _c, _it in enumerate(row):
                    _it.setEditable(True if _c == 2 else False)
            except Exception:
                pass
            self._teams_model.appendRow(row)
"@
$content = [regex]::Replace($content, $rowAppendRegex, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $rowAppendInject })
# At end of load_teams, unblock signals
$tailHook = "except Exception:\n            pass\n"
$tailInject = @"
        try:
            self._teams_model.blockSignals(False)
        except Exception:
            pass
        
        try:
            vh = self._teams_table.verticalHeader()
            for r in range(self._teams_model.rowCount()):
                vh.resizeSection(r, 44)
        except Exception:
            pass
"@
# Replace the specific section where vh resize exists to include unblock before it.
$content = $content -replace [regex]::Escape("        try:`r`n            vh = self._teams_table.verticalHeader()`r`n            for r in range(self._teams_model.rowCount()):`r`n                vh.resizeSection(r, 44)`r`n        except Exception:`r`n            pass`r`n"), $tailInject
# 4) Add handler method _on_team_item_changed if not present
if ($content -notmatch "def _on_team_item_changed\(") {
    $handler = @"
    def _on_team_item_changed(self, item) -> None:
        try:
            # Only handle Sortie column edits
            idx = item.index()
            if idx.column() != 2:
                return
            row = idx.row()
            # task_teams id stored in hidden column 0
            try:
                tt_id = int(self._teams_model.item(row, 0).text())
            except Exception:
                return
            new_val = item.text().strip()
            from modules.operations.taskings.repository import update_sortie_id
            update_sortie_id(int(tt_id), str(new_val) if new_val else None)
        except Exception:
            pass
        finally:
            try:
                # Refresh to reflect any formatting or repo-driven changes
                self.load_teams()
            except Exception:
                pass
"@
    # Insert the handler near other Teams ops; place after load_teams definition end
    $insertAfter = "def _selected_team_row\(self\) -> int:\n"  # We'll append after that method block by simple concat near the top of teams ops
    # If that marker not found, just append at end
    if ($content -match [regex]::Escape($insertAfter)) {
        $content = $content + "`n" + $handler
    } else {
        $content = $content + "`n" + $handler
    }
}
Set-Content $path -Value $content -Encoding UTF8
