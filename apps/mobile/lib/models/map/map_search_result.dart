import 'package:latlong2/latlong.dart';

enum MapSearchResultKind { team, myLocation, coordinate, geocode, feature }

class MapSearchResult {
  const MapSearchResult({
    required this.title,
    required this.subtitle,
    required this.point,
    required this.kind,
  });

  final String title;
  final String subtitle;
  final LatLng point;
  final MapSearchResultKind kind;
}
