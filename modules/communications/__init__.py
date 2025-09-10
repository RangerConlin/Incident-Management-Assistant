from .panels.ics205_window import ICS205Window


def create_ics205_window(parent=None):
    """Return the top-level ICS205 window."""
    return ICS205Window(parent)

__all__ = ['create_ics205_window', 'ICS205Window']
