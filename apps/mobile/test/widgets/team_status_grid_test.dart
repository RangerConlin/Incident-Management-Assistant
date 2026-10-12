import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/theme/app_theme.dart';
import 'package:ics_mobile_app/widgets/team_status_grid.dart';

Material _buttonMaterial(WidgetTester tester, String label) {
  final materials = tester.widgetList<Material>(
    find.ancestor(of: find.text(label), matching: find.byType(Material)),
  );
  return materials.first;
}

void main() {
  testWidgets('tapping a primary status button invokes onSelect with that option', (tester) async {
    TeamStatusOption? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TeamStatusGrid(
            currentStatusKey: 'available',
            busy: false,
            onSelect: (option) => selected = option,
          ),
        ),
      ),
    );

    await tester.tap(find.text('En Route'));
    await tester.pump();

    expect(selected?.key, 'enroute');
    expect(selected?.label, 'En Route');
  });

  testWidgets('overflow "More" statuses are selectable via the bottom sheet', (tester) async {
    TeamStatusOption? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TeamStatusGrid(
            currentStatusKey: 'available',
            busy: false,
            onSelect: (option) => selected = option,
          ),
        ),
      ),
    );

    await tester.tap(find.text('More'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Out of Service'));
    await tester.pumpAndSettle();

    expect(selected?.key, 'oos');
  });

  testWidgets('busy disables status taps (no double-submit)', (tester) async {
    var tapCount = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TeamStatusGrid(
            currentStatusKey: 'available',
            busy: true,
            onSelect: (_) => tapCount++,
          ),
        ),
      ),
    );

    await tester.tap(find.text('En Route'));
    await tester.pump();

    expect(tapCount, 0);
  });

  testWidgets('primary buttons use the desktop status colors even when not selected', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TeamStatusGrid(
            currentStatusKey: 'arrival',
            busy: false,
            onSelect: (_) {},
          ),
        ),
      ),
    );

    expect(
      _buttonMaterial(tester, 'On Scene').color,
      TeamStatusColors.forKey('arrival').background,
    );
    expect(
      _buttonMaterial(tester, 'Available').color,
      TeamStatusColors.forKey('available').background,
    );
  });

  testWidgets('More button adopts the desktop color for a selected overflow status', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TeamStatusGrid(
            currentStatusKey: 'oos',
            busy: false,
            onSelect: (_) {},
          ),
        ),
      ),
    );

    expect(
      _buttonMaterial(tester, 'More').color,
      TeamStatusColors.forKey('oos').background,
    );
  });
}
