from pathlib import Path
p=Path('modules/logistics/checkin/widgets/checkin_window.py')
s=p.read_text(encoding='utf-8')
s=s.replace(
    '        if not query:\n            self._records = []\n            self._populate_table(select_id=None)\n            return',
    '        if not query:\n            try:\n                self._records = self.service.list_master_records(self.config.key)\n            except Exception:\n                self._records = []\n            self._populate_table(select_id=select_id)\n            return')
s=s.replace(
    '            tab = EntityTab(config, self.service, self)\n            self.tabs.addTab(tab, config.title)',
    '            tab = EntityTab(config, self.service, self)\n            self.tabs.addTab(tab, config.title)\n            try:\n                tab.refresh()\n            except Exception:\n                pass')
p.write_text(s,encoding='utf-8')
print('PATCHED')
