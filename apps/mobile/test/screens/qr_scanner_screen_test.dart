import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/qr_scanner_screen.dart';

const _args = HomeNavArgs(
  incidentId: 'incident-1',
  incidentName: 'Test Incident',
  teamId: 'team-1',
  teamName: 'Team One',
  session: <String, dynamic>{},
);

void main() {
  testWidgets('shows an exact QR payload and can scan another code', (
    tester,
  ) async {
    late ValueChanged<String> reportScan;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerScreen(
          args: _args,
          scannerBuilder: (context, onScan) {
            reportScan = onScan;
            return const ColoredBox(
              color: Colors.black,
              child: Center(child: Text('Camera preview')),
            );
          },
        ),
      ),
    );

    expect(find.text('Camera preview'), findsOneWidget);
    expect(find.textContaining('Center a QR code'), findsOneWidget);

    reportScan('SARAPP:CHECKIN:v1:405021');
    await tester.pump();

    expect(find.text('QR code scanned'), findsOneWidget);
    expect(find.text('SARAPP:CHECKIN:v1:405021'), findsOneWidget);
    expect(find.text('Copy contents'), findsOneWidget);

    await tester.tap(find.text('Scan another'));
    await tester.pump();

    expect(find.text('Camera preview'), findsOneWidget);
    expect(find.text('SARAPP:CHECKIN:v1:405021'), findsNothing);
  });

  testWidgets('ignores empty and duplicate scan callbacks', (tester) async {
    late ValueChanged<String> reportScan;

    await tester.pumpWidget(
      MaterialApp(
        home: QrScannerScreen(
          args: _args,
          scannerBuilder: (context, onScan) {
            reportScan = onScan;
            return const SizedBox.expand();
          },
        ),
      ),
    );

    reportScan('');
    await tester.pump();
    expect(find.byKey(const Key('qr-scan-result')), findsNothing);

    reportScan('first');
    reportScan('second');
    await tester.pump();
    expect(find.text('first'), findsOneWidget);
    expect(find.text('second'), findsNothing);
  });
}
