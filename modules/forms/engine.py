"""Form generation engine — single entry point for filling and writing a PDF form."""

from __future__ import annotations

from pathlib import Path

from .resolver import FormResolver
from .context import FormDataContext
from .pdf_filler.pdf_filler import PDFFiller


def generate(
    form_id: str,
    output_path: str | Path,
    incident_id: str | None = None,
    form_set_id: str | None = None,
    extra_data: dict | None = None,
) -> Path:
    """Fill *form_id* with incident data and write the result to *output_path*.

    Parameters
    ----------
    form_id:
        Catalog ID of the form to generate (e.g. ``"ics_205"``).
    output_path:
        Where to write the filled PDF.
    incident_id:
        Incident to use as the data source.  Defaults to the active incident.
    form_set_id:
        Form set to use (e.g. ``"fema"``, ``"uscg"``).  Defaults to the
        configured default set, then walks the fallback chain.
    extra_data:
        Optional dict merged into the data context at the top level.  Use this
        to supply runtime values such as ``message`` fields for ICS 213.

    Returns
    -------
    Path
        The path of the written PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolver = FormResolver()
    template_pdf, mapping_json = resolver.resolve(form_id, form_set_id)

    ctx = FormDataContext().build(incident_id)
    if extra_data:
        ctx.update(extra_data)

    filler = PDFFiller(mapping_json)
    warnings = filler.fill(ctx, template_pdf, output_path, strict=False)

    if warnings:
        import logging
        log = logging.getLogger(__name__)
        for w in warnings:
            log.warning("Form %s: %s", form_id, w)

    return output_path
