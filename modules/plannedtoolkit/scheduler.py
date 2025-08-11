from __future__ import annotations

import datetime as dt
from typing import List

from . import planned_models as models
from .repository import with_event_session


def generate_op_periods(event_id: str, start: dt.datetime, end: dt.datetime, hours: int) -> List[models.OpsPeriod]:
    periods = []
    op_number = 1
    current = start
    while current < end:
        period_end = min(current + dt.timedelta(hours=hours), end)
        op = models.OpsPeriod(
            event_id=1,
            op_number=op_number,
            start_datetime=current,
            end_datetime=period_end,
        )
        periods.append(op)
        current = period_end
        op_number += 1
    with with_event_session(event_id) as session:
        session.add_all(periods)
    return periods
