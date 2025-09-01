from ui.actions.quick_entry_actions import dispatch, execute_cli, PermissionError


def test_quick_entry_dispatch_known_actions():
    for action in [
        "tasks.create",
        "logs.createActivity",
        "comms.createLogEntry",
        "logistics.createResourceRequest",
        "comms.createMessage",
        "safety.createReport",
        "files.upload",
    ]:
        assert dispatch(action, {}) is True


def test_quick_entry_dispatch_unknown_action():
    try:
        dispatch("unknown.action", {})
        assert False, "Expected PermissionError"
    except PermissionError:
        pass


def test_cli_exec_parses_examples():
    r1 = execute_cli('task new "Ground Sweep Alpha" priority=High team=G-2')
    assert "Task created" in r1
    r2 = execute_cli('log new "Team B departed ICP"')
    assert "Log entry created" in r2
    r3 = execute_cli('comms add "CH5 secure traffic"')
    assert "Comms log entry created" in r3

