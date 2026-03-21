import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
s=re.sub(r"\n\s*self\._add_from_master_button = QPushButton\(\"Add From Master\"\)\s*\n\s*member_buttons\.addWidget\(self\._add_from_master_button\)\s*\n","\n",s)
s=re.sub(r"\n\s*self\._add_from_master_button\.clicked\.connect\(self\._handle_add_member_from_master\)\s*\n","\n",s)
s=re.sub(r"\n\s*def _handle_add_member_from_master\([\s\S]*?\)\s*\n","\n",s)
io.open(p,'w',encoding='utf-8',newline='').write(s)
print('CLEANED')
