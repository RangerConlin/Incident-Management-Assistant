import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
# 1) Ensure AddTeamMemberDialog.__init__ sets a reference holder
s = re.sub(r"(def __init__\(self, parent: QWidget \| None = None\) -> None:\n\s*super\(\).__init__\(parent\)[\s\S]*?# Initial\n\s*self\._reload\(\)\n)",
           r"\1        self._checkin_window = None\n",
           s)
# 2) Replace _open_checkin to keep a persistent window and refresh on close
s = re.sub(r"def _open_checkin\(self\) -> None:\n[\s\S]*?\n\s*def _fetch\(self, query: str\) -> list:",
           (
            "def _open_checkin(self) -> None:\n"
            "        try:\n"
            "            from modules.logistics.checkin.widgets.checkin_window import CheckInWindow\n"
            "            if getattr(self, '_checkin_window', None) is None:\n"
            "                self._checkin_window = CheckInWindow(self)\n"
            "                try:\n"
            "                    self._checkin_window.destroyed.connect(lambda *_: (setattr(self, '_checkin_window', None), self._reload()))\n"
            "                except Exception:\n"
            "                    pass\n"
            "            w = self._checkin_window\n"
            "            try:\n"
            "                w.setWindowModality(Qt.ApplicationModal)\n"
            "            except Exception:\n"
            "                pass\n"
            "            try:\n"
            "                w.raise_(); w.activateWindow()\n"
            "            except Exception:\n"
            "                pass\n"
            "            w.show()\n"
            "        except Exception:\n"
            "            try:\n"
            "                QMessageBox.information(self, 'Check-In', 'Open Logistics -> Check-In to add people.')\n"
            "            except Exception:\n"
            "                pass\n\n"
            "    def _fetch(self, query: str) -> list:\n"
           ),
           s, flags=re.S)
io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(s)
print('PATCHED_CHECKIN_BUTTON')
