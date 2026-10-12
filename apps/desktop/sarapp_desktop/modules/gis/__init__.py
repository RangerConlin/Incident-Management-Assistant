"""Shared GIS/spatial framework for incident-scoped records."""

from .services.feature_registry import FeatureRegistry, get_default_feature_registry
from .services.layer_registry import LayerRegistry, get_default_layer_registry
from .services.spatial_repository import SpatialRepository
from .services.spatial_link_service import SpatialLinkService

__all__ = [
    "FeatureRegistry",
    "LayerRegistry",
    "SpatialRepository",
    "SpatialLinkService",
    "get_default_feature_registry",
    "get_default_layer_registry",
]
