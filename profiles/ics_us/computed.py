from datetime import datetime

def now_iso_seconds(context):
    return datetime.now().isoformat(timespec="seconds")

def us_specific(context):
    return "US"

computed_map = {
    "timestamp.iso": now_iso_seconds,
    "region.code": us_specific,
}
