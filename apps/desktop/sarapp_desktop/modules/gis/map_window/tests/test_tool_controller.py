from modules.gis.map_window.tools.tool_controller import ToolController


def test_default_tool_is_pan():
    controller = ToolController()
    assert controller.active_tool == "pan"


def test_activating_a_tool_deactivates_previous():
    controller = ToolController()
    events = []
    controller.subscribe(lambda new, prev: events.append((new, prev)))

    controller.activate("select")
    assert controller.active_tool == "select"
    assert events == [("select", "pan")]

    controller.activate("draw_line")
    assert controller.active_tool == "draw_line"
    assert events[-1] == ("draw_line", "select")


def test_activating_same_tool_is_a_noop():
    controller = ToolController()
    events = []
    controller.subscribe(lambda new, prev: events.append((new, prev)))
    controller.activate("pan")
    assert events == []


def test_reset_returns_to_default():
    controller = ToolController(default_tool="pan")
    controller.activate("zoom_in_box")
    controller.reset()
    assert controller.active_tool == "pan"


def test_is_active():
    controller = ToolController()
    controller.activate("select")
    assert controller.is_active("select")
    assert not controller.is_active("pan")


def test_unsubscribe_stops_notifications():
    controller = ToolController()
    events = []

    def listener(new, prev):
        events.append((new, prev))

    controller.subscribe(listener)
    controller.activate("select")
    controller.unsubscribe(listener)
    controller.activate("pan")
    assert events == [("select", "pan")]
