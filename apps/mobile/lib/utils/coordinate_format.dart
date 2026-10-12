import 'package:latlong2/latlong.dart';

String formatDecimalDegrees(LatLng point, {int precision = 6}) {
  return '${point.latitude.toStringAsFixed(precision)}, ${point.longitude.toStringAsFixed(precision)}';
}

String formatDms(LatLng point) {
  return '${_formatDmsValue(point.latitude, positive: 'N', negative: 'S')} '
      '${_formatDmsValue(point.longitude, positive: 'E', negative: 'W')}';
}

LatLng? parseDecimalCoordinate(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return null;

  final match = RegExp(
    r'^\s*([+-]?\d+(?:\.\d+)?)\s*[, ]\s*([+-]?\d+(?:\.\d+)?)\s*$',
  ).firstMatch(trimmed);
  if (match == null) return null;

  final lat = double.tryParse(match.group(1)!);
  final lon = double.tryParse(match.group(2)!);
  if (lat == null || lon == null) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return LatLng(lat, lon);
}

String _formatDmsValue(
  double value, {
  required String positive,
  required String negative,
}) {
  final direction = value >= 0 ? positive : negative;
  final absolute = value.abs();
  final degrees = absolute.floor();
  final minutesFull = (absolute - degrees) * 60;
  final minutes = minutesFull.floor();
  final seconds = (minutesFull - minutes) * 60;
  return '$degrees°${minutes.toString().padLeft(2, '0')}′${seconds.toStringAsFixed(1).padLeft(4, '0')}″$direction';
}
