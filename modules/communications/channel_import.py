"""CSV to master library importer."""

import csv
from pathlib import Path
from typing import Iterable

from .models.schemas import ChannelCreate
from . import services


def read_csv(path: Path) -> Iterable[ChannelCreate]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield ChannelCreate(
                name=row.get("name", ""),
                rx_freq=float(row.get("rx_freq", 0)),
                tx_freq=float(row.get("tx_freq", 0)),
                mode=row.get("mode", "analog"),
                tone=row.get("tone"),
                nac=row.get("nac"),
                band=row.get("band"),
                call_sign=row.get("call_sign"),
                usage=row.get("usage"),
                encrypted=row.get("encrypted", "").lower() == "true",
            )


def import_csv(path: Path) -> int:
    """Import channels from a CSV file into the master library."""
    channels = read_csv(path)
    return services.import_channels(channels)
