from datetime import datetime

def now_iso_seconds(context):
    return datetime.now().isoformat(timespec="seconds")

# mapping of names to functions (optional)
computed_map = {
    "timestamp.iso": now_iso_seconds,
}
