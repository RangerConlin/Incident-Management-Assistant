# Forms Renderer

Utility package for converting ICS JSON form exports into PDF documents. This
implementation is intentionally small and focuses on the minimal features needed
for tests. Templates are discovered via ``data/templates/registry.json`` and
mapped using a small YAML based DSL.

Example:

```python
from modules.forms import render_form
from modules.forms.examples import ics_205_example

pdf_bytes = render_form(
    form_id="ics_205",
    form_version="2023.10",
    data=ics_205_example,
)
```
