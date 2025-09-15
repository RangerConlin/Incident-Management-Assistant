# Forms Renderer

Utility package for working with forms.

Preferred pipeline:
- Use ``FormRegistry`` to load profile-driven templates
- Track user edits with ``FormSession``
- Export deterministically with ``export_form``

Legacy path:
- ``render_form`` and ``templating`` use ``data/templates/registry.json`` and a YAML mapping. These remain for
  backwards-compatibility and dev tooling, but new code should adopt the
  profile-driven pipeline above.

Example:

```python
from modules.forms import FormRegistry, FormSession, export_form

# Example (pseudocode):
# reg = FormRegistry(profiles_dir="profiles", profile_id="ics_us")
# reg.load()
# session = FormSession(instance_id="123", template_uid="ics_us:ICS_205@2025.09")
# out = export_form(session, context={}, registry=reg, out_path=Path("out.pdf"))
```
