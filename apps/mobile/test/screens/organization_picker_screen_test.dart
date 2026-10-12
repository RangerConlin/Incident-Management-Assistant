import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/organizations.dart';
import 'package:ics_mobile_app/screens/organization_picker_screen.dart';

const _entries = [
  OrgEntry(key: 'cap', name: 'Civil Air Patrol', shortName: 'CAP'),
  OrgEntry(
    key: 'cap_mi_wing',
    name: 'Michigan Wing',
    shortName: 'MIWG',
    parentKey: 'cap',
  ),
  OrgEntry(
    key: 'cap_mi_655',
    name: 'Maj Kevin A Adams Memorial Composite Squadron',
    shortName: 'MI-655',
    location: 'Ann Arbor',
    parentKey: 'cap_mi_wing',
  ),
  OrgEntry(key: 'mi_state', name: 'State of Michigan'),
  OrgEntry(
    key: 'mi_state_police',
    name: 'Michigan State Police',
    shortName: 'MSP',
    parentKey: 'mi_state',
  ),
];

/// Holds the `Future` from the picker's `Navigator.push` so callers can
/// `await nav.future` only when a test actually expects a selection.
///
/// Returning that future directly from an `async` helper would auto-await
/// it (Dart's future-flattening for `async` functions), which hangs forever
/// in any test that never selects anything — this holder avoids that.
class _Nav {
  Future<String?>? future;
}

Future<void> _pump(WidgetTester tester, _Nav nav) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) {
          return ElevatedButton(
            onPressed: () {
              nav.future = Navigator.of(context).push<String>(
                MaterialPageRoute(
                  builder: (context) =>
                      const OrganizationPickerScreen(entries: _entries),
                ),
              );
            },
            child: const Text('open'),
          );
        },
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows top-level roots only, not nested entries', (
    tester,
  ) async {
    await _pump(tester, _Nav());

    expect(find.text('Civil Air Patrol'), findsOneWidget);
    expect(find.text('State of Michigan'), findsOneWidget);
    expect(find.text('Michigan Wing'), findsNothing);
    expect(find.text('Michigan State Police'), findsNothing);
  });

  testWidgets('drilling into a tier shows its children and a "use this" row', (
    tester,
  ) async {
    await _pump(tester, _Nav());

    await tester.tap(find.text('Civil Air Patrol'));
    await tester.pumpAndSettle();

    expect(find.text("Use 'Civil Air Patrol'"), findsOneWidget);
    expect(find.text('Michigan Wing'), findsOneWidget);
    expect(find.text('State of Michigan'), findsNothing);
  });

  testWidgets('selecting a leaf pops with its key', (tester) async {
    final nav = _Nav();
    await _pump(tester, nav);

    await tester.tap(find.text('State of Michigan'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Michigan State Police'));
    await tester.pumpAndSettle();

    expect(await nav.future, 'mi_state_police');
  });

  testWidgets("using a tier directly pops with that tier's key", (
    tester,
  ) async {
    final nav = _Nav();
    await _pump(tester, nav);

    await tester.tap(find.text('Civil Air Patrol'));
    await tester.pumpAndSettle();
    await tester.tap(find.text("Use 'Civil Air Patrol'"));
    await tester.pumpAndSettle();

    expect(await nav.future, 'cap');
  });

  testWidgets('search finds a deeply nested entry with its ancestor chain', (
    tester,
  ) async {
    final nav = _Nav();
    await _pump(tester, nav);

    await tester.enterText(find.byType(TextField), 'Adams');
    await tester.pumpAndSettle();

    expect(
      find.text('Maj Kevin A Adams Memorial Composite Squadron'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Civil Air Patrol › Michigan Wing'),
      findsOneWidget,
    );

    await tester.tap(
      find.text('Maj Kevin A Adams Memorial Composite Squadron'),
    );
    await tester.pumpAndSettle();

    expect(await nav.future, 'cap_mi_655');
  });

  testWidgets('"not listed" pops with the shared otherOrgKey sentinel', (
    tester,
  ) async {
    final nav = _Nav();
    await _pump(tester, nav);

    await tester.tap(find.text('Not listed — type it in'));
    await tester.pumpAndSettle();

    expect(await nav.future, otherOrgKey);
  });

  testWidgets('back button goes up one tier instead of closing the screen', (
    tester,
  ) async {
    await _pump(tester, _Nav());

    await tester.tap(find.text('Civil Air Patrol'));
    await tester.pumpAndSettle();
    expect(find.text('Michigan Wing'), findsOneWidget);

    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(find.text('Civil Air Patrol'), findsOneWidget);
    expect(find.text('State of Michigan'), findsOneWidget);
  });
}
