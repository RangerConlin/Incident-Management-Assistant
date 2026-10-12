import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/geocode_result.dart';

void main() {
  group('GeocodeResult.fromJson', () {
    test('parses backend geocoding response', () {
      final result = GeocodeResult.fromJson({
        'address': '1 Main St',
        'latitude': '38.8951',
        'longitude': -106.7621,
      });

      expect(result.address, '1 Main St');
      expect(result.latitude, 38.8951);
      expect(result.longitude, -106.7621);
    });

    test('rejects responses without coordinates', () {
      expect(
        () => GeocodeResult.fromJson({'address': 'Nope'}),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
