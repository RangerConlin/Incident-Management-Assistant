import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/utils/coordinate_format.dart';
import 'package:latlong2/latlong.dart';

void main() {
  group('parseDecimalCoordinate', () {
    test('parses comma-separated decimal degrees', () {
      final point = parseDecimalCoordinate('38.8951, -106.7621');

      expect(point?.latitude, 38.8951);
      expect(point?.longitude, -106.7621);
    });

    test('parses space-separated decimal degrees', () {
      final point = parseDecimalCoordinate('38.8951 -106.7621');

      expect(point?.latitude, 38.8951);
      expect(point?.longitude, -106.7621);
    });

    test('rejects out-of-range coordinates', () {
      expect(parseDecimalCoordinate('123, -106'), isNull);
      expect(parseDecimalCoordinate('38, -206'), isNull);
    });
  });

  test('formats decimal degrees', () {
    expect(
      formatDecimalDegrees(const LatLng(38.8951234, -106.7621987)),
      '38.895123, -106.762199',
    );
  });

  test('formats DMS', () {
    expect(
      formatDms(const LatLng(38.8951, -106.7621)),
      '38°53′42.4″N 106°45′43.6″W',
    );
  });
}
