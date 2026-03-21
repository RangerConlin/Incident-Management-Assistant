import py_compile,sys
try:
    py_compile.compile('modules/operations/teams/panels/team_detail_window.py', doraise=True)
    print('COMPILES')
except Exception as e:
    print('COMPILE_ERROR:', e)
