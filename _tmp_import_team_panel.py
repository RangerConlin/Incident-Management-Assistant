import importlib.util, sys
p='modules/operations/panels/team_status_panel.py'
spec=importlib.util.spec_from_file_location('tpanel', p)
m=importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)  # type: ignore
    print('TeamStatusPanel import OK')
except Exception as e:
    print('IMPORT ERROR:', e)
