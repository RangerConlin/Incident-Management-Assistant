import 'package:latlong2/latlong.dart';

import '../utils/json_parsing.dart';

class GeocodeResult {
  const GeocodeResult({
    required this.address,
    required this.latitude,
    required this.longitude,
  });

  final String address;
  final double latitude;
  final double longitude;

  LatLng get point => LatLng(latitude, longitude);

  factory GeocodeResult.fromJson(Map<String, dynamic> json) {
    final lat = _parseDouble(json['latitude'] ?? json['lat']);
    final lon = _parseDouble(json['longitude'] ?? json['lon'] ?? json['lng']);
    if (lat == null || lon == null) {
      throw const FormatException('Geocode result is missing coordinates');
    }
    return GeocodeResult(
      address:
          nullIfBlank(json['address'] ?? json['display_name']) ??
          '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}',
      latitude: lat,
      longitude: lon,
    );
  }

  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse('$value');
  }
}
