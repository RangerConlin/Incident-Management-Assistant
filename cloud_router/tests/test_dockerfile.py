from pathlib import Path


def test_dockerfile_vendors_master_gui_admin_models() -> None:
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    contents = dockerfile.read_text(encoding="utf-8")

    assert "modules/admin/resource_types/models/resource_type_models.py" in contents
    assert "modules/admin/hazard_types/models/hazard_type_models.py" in contents
