from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from modules.forms_creator.services.pdf_fields import _resolve_full_field_name
from modules.forms_creator.services.template_importer import _sanitise_field_name


def test_resolve_full_field_name_uses_acroform_parent_chain():
    root = DictionaryObject({NameObject("/T"): TextStringObject("personnel")})
    child = DictionaryObject({
        NameObject("/T"): TextStringObject("name"),
        NameObject("/Parent"): root,
    })
    widget = DictionaryObject({
        NameObject("/T"): TextStringObject("1"),
        NameObject("/Parent"): child,
    })

    assert _resolve_full_field_name(widget) == "personnel.name.1"


def test_resolve_full_field_name_uses_parent_name_for_unnamed_widget():
    parent = DictionaryObject({NameObject("/T"): TextStringObject("maps_attached")})
    widget = DictionaryObject({NameObject("/Parent"): parent})

    assert _resolve_full_field_name(widget) == "maps_attached"


def test_imported_field_name_sanitiser_preserves_pdf_dot_paths():
    assert _sanitise_field_name("personnel.name.1") == "personnel.name.1"
    assert _sanitise_field_name("chan desc.command") == "chan_desc.command"
