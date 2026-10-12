import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/screens/main_menu_screen.dart';
import 'package:ics_mobile_app/screens/splash_screen.dart';
import 'package:ics_mobile_app/theme/app_theme.dart';
import 'package:ics_mobile_app/widgets/arc_horizon_mark.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('with no incident loaded the splash opens the main menu', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        home: const SplashScreen(minDisplay: Duration.zero),
      ),
    );
    expect(find.byType(ArcHorizonFullLogo), findsOneWidget);

    await tester.pumpAndSettle();

    expect(find.byType(MainMenuScreen), findsOneWidget);
    expect(find.text('Create profile'), findsOneWidget);
    expect(find.text('Add connection'), findsOneWidget);
  });
}
