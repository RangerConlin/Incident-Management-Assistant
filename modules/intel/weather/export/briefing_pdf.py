"""Weather briefing PDF export — mirrors modules/safety/orm/pdf_export.py's
build_pdf pattern exactly: BytesIO + SimpleDocTemplate, no file I/O inside
(the caller saves via QFileDialog)."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..services.weather_manager import WeatherManager


def build_weather_briefing_pdf(*, incident_name: Optional[str], manager: WeatherManager) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title="Weather Briefing",
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    elements = []

    title = "Weather Briefing"
    if incident_name:
        title = f"{incident_name}: {title}"
    elements.append(Paragraph(title, styles["Heading1"]))
    elements.append(Spacer(1, 12))

    for location in manager.locations():
        elements.append(Paragraph(location.label, styles["Heading2"]))
        reading = manager.normalized_current(location.location_id)
        snap = manager.snapshot(location.location_id)

        current_rows = [["Field", "Value"]]
        current_rows.append(["Temperature", f"{reading.get('temperature_f', '—')}°F"])
        current_rows.append(["Wind", f"{reading.get('wind_speed_kt', '—')} kt, gust {reading.get('wind_gust_kt', '—')} kt"])
        current_rows.append(["Visibility", f"{reading.get('visibility_sm', '—')} sm"])
        current_rows.append(["Ceiling", f"{reading.get('ceiling_ft', '—')} ft"])
        table = Table(current_rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 8))

        if snap:
            forecast_rows = [["Period", "Conditions", "Temp °F"]]
            for period in snap.forecast[:5]:
                forecast_rows.append([period.name, period.detailed_text or "", str(period.temperature or "—")])
            if len(forecast_rows) > 1:
                forecast_table = Table(forecast_rows, repeatRows=1)
                forecast_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ]
                    )
                )
                elements.append(forecast_table)
                elements.append(Spacer(1, 8))

            if snap.advisories:
                adv_rows = [["Event", "Severity", "Headline"]]
                for advisory in snap.advisories:
                    adv_rows.append([advisory.event, advisory.severity or "—", advisory.headline or ""])
                adv_table = Table(adv_rows, repeatRows=1)
                adv_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.mistyrose),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ]
                    )
                )
                elements.append(adv_table)
            else:
                elements.append(Paragraph("No active advisories.", styles["Normal"]))

        elements.append(Spacer(1, 16))

    doc.build(elements)
    return buffer.getvalue()


__all__ = ["build_weather_briefing_pdf"]
