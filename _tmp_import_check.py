import importlib.util
p='modules/operations/data/repository.py'
spec=importlib.util.spec_from_file_location('opsrepo', p)
m=importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)  # type: ignore
    print('IMPORT OK')
    print('Has fetch_task_rows:', hasattr(m,'fetch_task_rows'))
    print('Has fetch_team_assignment_rows:', hasattr(m,'fetch_team_assignment_rows'))
except Exception as e:
    print('IMPORT ERROR:', e)
