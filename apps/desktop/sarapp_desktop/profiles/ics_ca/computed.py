from datetime import datetime

def now_iso_seconds(context):
    return datetime.now().isoformat(timespec="seconds")

def ca_specific(context):
    return "CA"

computed_map = {
    "timestamp.iso": now_iso_seconds,
    "region.code": ca_specific,
}
