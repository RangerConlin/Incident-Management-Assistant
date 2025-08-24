"""Communications module exposing API router and GUI panel entry point."""

from .api import router


def get_comms_panel(parent=None):
    """Return the default communications panel widget.

    Parameters
    ----------
    parent: QWidget | None
        Optional parent widget.
    """
    from .panels.ChannelsPanel import ChannelsPanel

    return ChannelsPanel(parent)
