"""Communications module exposing API router and GUI panel entry point.

Also exposes a small helper to notify the rest of the app when a
communications message is logged so boards can react immediately.
"""

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


def notify_message_logged(sender: str, recipient: str) -> None:
    """Emit a global signal that a comms message was logged.

    Call this from any place that stores a new message log entry to
    immediately update UI timers.
    """
    try:
        from utils.app_signals import app_signals
        app_signals.messageLogged.emit(str(sender or ""), str(recipient or ""))
    except Exception:
        pass
