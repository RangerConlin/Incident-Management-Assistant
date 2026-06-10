# GIS Framework First Pass

## What was added
- A new `modules/gis/` package with shared spatial models for geometry types, feature types, layer definitions, spatial features, and feature links.
- Central registries for feature rules (`FeatureRegistry`) and built-in layers (`LayerRegistry`).
- Incident-scoped persistence services (`SpatialRepository`, `SpatialLinkService`) and schema bootstrap support for spatial tables.
- A dependency-light geometry utility service (`GeometryService`) to validate and normalize WKT while avoiding map/GIS dependencies.
- Module adapter stubs for operations tasks/teams plus intel, safety, and communications-owned records.
- Qt Widgets inspection UI:
  - `SpatialObjectsPanel` for feature listing
  - `FeatureInspectorPanel` for read-only details
  - `GeometrySummaryWidget` for reusable geometry summary content

## How module records should link to spatial features
1. Keep module-owned business records in their home module tables.
2. Use `SpatialRepository` and one of the GIS adapters to create a `SpatialFeature` that references:
   - `source_module`
   - `source_record_type`
   - `source_record_id`
3. Use `SpatialLinkService.attach_feature(...)` for additional related records beyond the owner.
4. Query by owner with `list_features_for_record(...)` and by related links with `list_related_features(...)`.

## Next implementation step
- Add a map-engine adapter interface (no UI renderer yet) that consumes `SpatialRepository` records and layer definitions so a future QGIS/web/other map component can be plugged in without changing data ownership or schema.
