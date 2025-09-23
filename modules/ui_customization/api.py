from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .models import LayoutTemplate, ThemeProfile, CustomizationBundle
from .repository import UICustomizationRepository


router = APIRouter(prefix="/api/ui/customization", tags=["ui-customization"])


class LayoutTemplateIn(BaseModel):
    name: str
    perspective_name: Optional[str] = None
    description: Optional[str] = ""
    ads_state: str = Field(default="", description="Base64 encoded ADS perspective state")
    dashboard_widgets: list[str] = Field(default_factory=list)


class LayoutTemplateOut(LayoutTemplateIn):
    id: str

    @classmethod
    def from_model(cls, model: LayoutTemplate) -> "LayoutTemplateOut":
        return cls(
            id=model.id,
            name=model.name,
            perspective_name=model.perspective_name,
            description=model.description,
            ads_state=model.ads_state,
            dashboard_widgets=list(model.dashboard_widgets),
        )


class ThemeProfileIn(BaseModel):
    name: str
    base_theme: str = Field(default="light")
    description: Optional[str] = ""
    tokens: dict[str, str] = Field(default_factory=dict)


class ThemeProfileOut(ThemeProfileIn):
    id: str

    @classmethod
    def from_model(cls, model: ThemeProfile) -> "ThemeProfileOut":
        return cls(
            id=model.id,
            name=model.name,
            base_theme=model.base_theme,
            description=model.description,
            tokens=dict(model.tokens),
        )


class BundlePayload(BaseModel):
    layouts: list[LayoutTemplateOut] = Field(default_factory=list)
    themes: list[ThemeProfileOut] = Field(default_factory=list)
    active_layout_id: Optional[str] = None
    active_theme_id: Optional[str] = None

    @classmethod
    def from_bundle(cls, bundle: CustomizationBundle) -> "BundlePayload":
        return cls(
            layouts=[LayoutTemplateOut.from_model(model) for model in bundle.layouts],
            themes=[ThemeProfileOut.from_model(model) for model in bundle.themes],
            active_layout_id=bundle.active_layout_id,
            active_theme_id=bundle.active_theme_id,
        )

    def to_bundle(self) -> CustomizationBundle:
        layouts = [LayoutTemplate(**layout.model_dump()) for layout in self.layouts]
        themes = [ThemeProfile(**theme.model_dump()) for theme in self.themes]
        return CustomizationBundle(
            layouts=layouts,
            themes=themes,
            active_layout_id=self.active_layout_id,
            active_theme_id=self.active_theme_id,
        )


def get_repo() -> UICustomizationRepository:
    return UICustomizationRepository()


@router.get("/layouts", response_model=list[LayoutTemplateOut])
def list_layouts(repo: UICustomizationRepository = Depends(get_repo)):
    return [LayoutTemplateOut.from_model(layout) for layout in repo.list_layouts()]


@router.post("/layouts", response_model=LayoutTemplateOut)
def create_layout(payload: LayoutTemplateIn, repo: UICustomizationRepository = Depends(get_repo)):
    layout = LayoutTemplate(
        id="",
        name=payload.name,
        perspective_name=payload.perspective_name or "",
        description=payload.description or "",
        ads_state=payload.ads_state,
        dashboard_widgets=payload.dashboard_widgets,
    )
    layout = repo.upsert_layout(layout)
    return LayoutTemplateOut.from_model(layout)


@router.put("/layouts/{layout_id}", response_model=LayoutTemplateOut)
def update_layout(layout_id: str, payload: LayoutTemplateIn, repo: UICustomizationRepository = Depends(get_repo)):
    existing = repo.get_layout(layout_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Layout not found")
    updated = LayoutTemplate(
        id=layout_id,
        name=payload.name,
        perspective_name=payload.perspective_name or existing.perspective_name,
        description=payload.description or "",
        ads_state=payload.ads_state,
        dashboard_widgets=payload.dashboard_widgets,
    )
    layout = repo.upsert_layout(updated)
    return LayoutTemplateOut.from_model(layout)


@router.delete("/layouts/{layout_id}")
def delete_layout(layout_id: str, repo: UICustomizationRepository = Depends(get_repo)):
    repo.delete_layout(layout_id)
    return {"status": "ok"}


@router.post("/layouts/{layout_id}/activate")
def activate_layout(layout_id: str, repo: UICustomizationRepository = Depends(get_repo)):
    repo.set_active_layout(layout_id)
    return {"status": "ok"}


@router.get("/themes", response_model=list[ThemeProfileOut])
def list_themes(repo: UICustomizationRepository = Depends(get_repo)):
    return [ThemeProfileOut.from_model(theme) for theme in repo.list_themes()]


@router.post("/themes", response_model=ThemeProfileOut)
def create_theme(payload: ThemeProfileIn, repo: UICustomizationRepository = Depends(get_repo)):
    theme = ThemeProfile(
        id="",
        name=payload.name,
        base_theme=payload.base_theme,
        description=payload.description or "",
        tokens=payload.tokens,
    )
    theme = repo.upsert_theme(theme)
    return ThemeProfileOut.from_model(theme)


@router.put("/themes/{theme_id}", response_model=ThemeProfileOut)
def update_theme(theme_id: str, payload: ThemeProfileIn, repo: UICustomizationRepository = Depends(get_repo)):
    existing = repo.get_theme(theme_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Theme not found")
    updated = ThemeProfile(
        id=theme_id,
        name=payload.name,
        base_theme=payload.base_theme,
        description=payload.description or "",
        tokens=payload.tokens,
    )
    theme = repo.upsert_theme(updated)
    return ThemeProfileOut.from_model(theme)


@router.delete("/themes/{theme_id}")
def delete_theme(theme_id: str, repo: UICustomizationRepository = Depends(get_repo)):
    repo.delete_theme(theme_id)
    return {"status": "ok"}


@router.post("/themes/{theme_id}/activate")
def activate_theme(theme_id: str, repo: UICustomizationRepository = Depends(get_repo)):
    repo.set_active_theme(theme_id)
    return {"status": "ok"}


@router.get("/bundle/export", response_model=BundlePayload)
def export_bundle(repo: UICustomizationRepository = Depends(get_repo)):
    bundle = repo.export_bundle()
    return BundlePayload.from_bundle(bundle)


@router.post("/bundle/import")
def import_bundle(payload: BundlePayload, replace: bool = False, repo: UICustomizationRepository = Depends(get_repo)):
    repo.import_bundle(payload.to_bundle(), replace=replace)
    return {"status": "ok"}
