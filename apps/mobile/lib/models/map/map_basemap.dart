/// A raster tile basemap available in the mobile incident map.
class MapBasemap {
  const MapBasemap({
    required this.id,
    required this.label,
    required this.description,
    required this.urlTemplate,
    required this.attribution,
    this.subdomains = const [],
    required this.maxNativeZoom,
  });

  final String id;
  final String label;
  final String description;
  final String urlTemplate;
  final String attribution;
  final List<String> subdomains;
  final int maxNativeZoom;
}

class MapBasemaps {
  MapBasemaps._();

  static const osm = MapBasemap(
    id: 'osm',
    label: 'OSM Standard',
    description: 'General street map from OpenStreetMap.',
    urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
    maxNativeZoom: 19,
  );

  static const openTopo = MapBasemap(
    id: 'open_topo',
    label: 'OpenTopo',
    description: 'Terrain-focused map with contours and relief.',
    urlTemplate: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution:
        'Map data © OpenStreetMap contributors, SRTM | Style © OpenTopoMap',
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom: 17,
  );

  static const usgsTopo = MapBasemap(
    id: 'usgs_topo',
    label: 'USGS Topo',
    description: 'The National Map topographic basemap.',
    urlTemplate:
        'https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',
    attribution: 'USGS The National Map',
    maxNativeZoom: 16,
  );

  static const usgsImagery = MapBasemap(
    id: 'usgs_imagery',
    label: 'USGS Imagery',
    description: 'The National Map orthoimagery basemap.',
    urlTemplate:
        'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
    attribution: 'USGS The National Map imagery',
    maxNativeZoom: 16,
  );

  static const usgsImageryTopo = MapBasemap(
    id: 'usgs_imagery_topo',
    label: 'USGS Hybrid',
    description: 'USGS imagery with topo labels and reference features.',
    urlTemplate:
        'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}',
    attribution: 'USGS The National Map imagery/topo',
    maxNativeZoom: 16,
  );

  static const all = [osm, openTopo, usgsTopo, usgsImagery, usgsImageryTopo];

  static MapBasemap byId(String? id) {
    return all.firstWhere((basemap) => basemap.id == id, orElse: () => osm);
  }
}
