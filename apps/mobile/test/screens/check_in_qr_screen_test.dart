import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/screens/check_in_qr_screen.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/utils/check_in_qr.dart';
import 'package:qr_flutter/qr_flutter.dart';

void main() {
  test('payload is the prefixed person ID the desktop desk parses', () {
    expect(CheckInQr.payload('405021'), 'SARAPP:CHECKIN:v1:405021');
    expect(CheckInQr.payload(' CAP-405021 '), 'SARAPP:CHECKIN:v1:CAP-405021');
  });

  testWidgets('shows a scannable code for the profile', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: CheckInQrScreen(
          profile: LocalProfile(
            personId: '405021',
            firstName: 'Jane',
            lastName: 'Doe',
          ),
        ),
      ),
    );

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('ID 405021'), findsOneWidget);
    expect(find.byType(QrImageView), findsOneWidget);
  });
}
