import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/screens/check_in_qr_screen.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/utils/check_in_qr.dart';
import 'package:qr_flutter/qr_flutter.dart';

void main() {
  test('payload carries the canonical mobile personnel profile', () {
    const profile = LocalProfile(
      personId: 'CAP-405021',
      firstName: 'Jane',
      lastName: 'Doe',
      organization: 'County SAR',
      homeUnit: 'Unit 7',
      primaryRole: 'Ground Team Member',
      rank: 'Captain',
      callsign: 'Rescue 7',
      title: 'Team Lead',
      phone: '555-0100',
      email: 'jane@example.test',
      radioId: 'R-7',
      isMedic: true,
      status: 'available',
      notes: 'Night operations qualified',
      photoUrl: 'https://example.test/jane.jpg',
      emergencyInfo: {
        'primary_name': 'John Doe',
        'primary_relationship': 'Spouse',
        'primary_phone': '555-0199',
        'secondary_name': 'Jamie Doe',
        'secondary_relationship': 'Sibling',
        'secondary_phone': '555-0188',
        'medical': 'No known allergies',
      },
      contactInfo: {
        'address1': '100 Main St',
        'address2': 'Apt 2',
        'city': 'Example',
        'state': 'MI',
        'zip': '49000',
        'work_phone': '555-0111',
        'secondary_phone': '555-0122',
        'pager_id': 'P-7',
        'notes': 'Use SMS first',
      },
      certifications: [
        {'cert_type_id': 2003, 'level': 2},
        {'cert_type_id': 6050, 'level': 1},
      ],
    );

    final payload = CheckInQr.payload(profile);
    expect(payload, startsWith(CheckInQr.prefix));
    expect(payload, isNot(contains('{')));
    final decoded = CheckInQr.decode(payload);
    expect(decoded, profile.toPersonnelJson());
    expect(decoded?.keys.toSet(), {
      'person_id',
      'name',
      'first_name',
      'last_name',
      'organization',
      'home_unit',
      'primary_role',
      'rank',
      'callsign',
      'title',
      'phone',
      'email',
      'radio_id',
      'is_medic',
      'status',
      'notes',
      'photo_url',
      'emergency_info',
      'contact_info',
      'certifications',
    });
  });

  test('invalid profile payloads are rejected', () {
    expect(CheckInQr.decode('SARAPP:CHECKIN:v1:405021'), isNull);
    expect(CheckInQr.decode('${CheckInQr.prefix}not-base64'), isNull);
  });

  testWidgets('shows a scannable code for the profile', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: CheckInQrScreen(
          profile: LocalProfile(
            personId: '405021',
            firstName: 'Jane',
            lastName: 'Doe',
            organization: 'County SAR',
            primaryRole: 'Ground Team Member',
            callsign: 'Rescue 7',
          ),
        ),
      ),
    );

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('ID 405021'), findsOneWidget);
    expect(find.text('County SAR'), findsOneWidget);
    expect(find.textContaining('load your profile'), findsOneWidget);
    expect(find.byType(QrImageView), findsOneWidget);
  });
}
