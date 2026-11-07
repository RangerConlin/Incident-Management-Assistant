import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ics_mobile_app/models/app_notification.dart';
import 'package:ics_mobile_app/services/app_navigation.dart';
import 'package:ics_mobile_app/services/notification_presenter.dart';

void main() {
  testWidgets('foreground banner waits for the root navigator', (tester) async {
    final notification = AppNotification(
      id: 'foreground-1',
      title: 'Resource update',
      body: 'Team 2 is returning to base.',
      severity: NotificationSeverity.priority,
      category: NotificationCategory.administrative,
      receivedAt: DateTime(2026, 11, 7, 9),
    );

    NotificationPresenter.present(notification);

    await tester.pumpWidget(
      MaterialApp(
        navigatorKey: AppNavigation.navigatorKey,
        home: const Scaffold(body: Text('Dashboard')),
      ),
    );
    await tester.pump(const Duration(milliseconds: 150));

    expect(find.text('Resource update'), findsOneWidget);
    expect(find.text('Team 2 is returning to base.'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.close));
    await tester.pump();
    expect(find.text('Resource update'), findsNothing);
  });
}
