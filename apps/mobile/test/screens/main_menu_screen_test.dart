import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/screens/check_in_qr_screen.dart';
import 'package:ics_mobile_app/screens/main_menu_screen.dart';
import 'package:ics_mobile_app/services/local_profile_store.dart';
import 'package:ics_mobile_app/services/sarapp_api_client.dart';
import 'package:ics_mobile_app/services/server_connection_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _profile = LocalProfile(
  personId: '405021',
  firstName: 'Jane',
  lastName: 'Doe',
  organization: 'CAP',
);

const _connection = ServerConnection(
  code: 'ABCD-1234',
  routerUrl: 'https://test.local',
);

Future<void> _pumpMenu(WidgetTester tester, {required int healthStatus}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: MainMenuScreen(
        clientFactory: () => SarAppApiClient(
          baseUrl: 'https://test.local',
          httpClient: MockClient((_) async => http.Response('', healthStatus)),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

FilledButton _loadButton(WidgetTester tester) => tester.widget<FilledButton>(
  find.ancestor(
    of: find.text('Load incident'),
    matching: find.byWidgetPredicate((w) => w is FilledButton),
  ),
);

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await ServerConnectionStore.initialize();
  });

  testWidgets('works offline with nothing set up: prompts for a profile', (
    tester,
  ) async {
    await _pumpMenu(tester, healthStatus: 503);

    expect(find.text('Create profile'), findsOneWidget);
    expect(find.text('No connection set'), findsOneWidget);
    expect(find.text('Create your profile first.'), findsOneWidget);
    expect(_loadButton(tester).onPressed, isNull);
  });

  testWidgets('with a profile but no connection, asks for a connect code', (
    tester,
  ) async {
    await LocalProfileStore.save(_profile);
    await _pumpMenu(tester, healthStatus: 200);

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('ID 405021 · CAP'), findsOneWidget);
    expect(
      find.text('Add a connection code to load incidents.'),
      findsOneWidget,
    );
    expect(_loadButton(tester).onPressed, isNull);
  });

  testWidgets('an unreachable server keeps the menu usable and offers retry', (
    tester,
  ) async {
    await LocalProfileStore.save(_profile);
    await ServerConnectionStore.addAndActivate(_connection);
    await _pumpMenu(tester, healthStatus: 503);

    expect(find.text('Unreachable'), findsOneWidget);
    expect(find.text('Connect code ABCD-1234'), findsOneWidget);
    expect(find.textContaining('be reached right now'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(_loadButton(tester).onPressed, isNull);
  });

  testWidgets('profile + reachable server enables loading an incident', (
    tester,
  ) async {
    await LocalProfileStore.save(_profile);
    await ServerConnectionStore.addAndActivate(_connection);
    await _pumpMenu(tester, healthStatus: 200);

    expect(find.text('Connected'), findsOneWidget);
    expect(_loadButton(tester).onPressed, isNotNull);
  });

  Future<void> sizeForMenu(WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }

  testWidgets('the check-in QR is unavailable until a profile exists', (
    tester,
  ) async {
    await sizeForMenu(tester);
    await _pumpMenu(tester, healthStatus: 503);

    final button = tester.widget<OutlinedButton>(
      find.ancestor(
        of: find.text('My check-in QR'),
        matching: find.byWidgetPredicate((w) => w is OutlinedButton),
      ),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('the check-in QR opens from the profile alone, with no server', (
    tester,
  ) async {
    await sizeForMenu(tester);
    await LocalProfileStore.save(_profile);
    await _pumpMenu(tester, healthStatus: 503);

    await tester.tap(find.text('My check-in QR'));
    await tester.pumpAndSettle();

    expect(find.byType(CheckInQrScreen), findsOneWidget);
  });
}
