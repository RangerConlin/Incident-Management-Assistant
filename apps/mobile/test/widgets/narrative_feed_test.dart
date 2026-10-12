import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/narrative_entry.dart';
import 'package:ics_mobile_app/widgets/narrative_feed.dart';

NarrativeEntry _entry(String id, DateTime timestamp, String text, {bool critical = false}) {
  return NarrativeEntry(
    id: id,
    taskId: 1,
    timestamp: timestamp,
    narrative: text,
    enteredBy: 'Tester',
    critical: critical,
  );
}

void main() {
  testWidgets('renders entries in the order given (screen sorts newest-first before passing in)',
      (tester) async {
    // NarrativeFeed itself does not sort — FieldDashboardScreen._load()
    // sorts newest-first before handing entries to this widget. Feed it
    // pre-sorted, newest-first data and confirm it preserves that order.
    final entries = [
      _entry('3', DateTime(2026, 7, 10, 9, 51), 'Possible wreckage sighted', critical: true),
      _entry('2', DateTime(2026, 7, 10, 9, 47), 'Beginning search sweep #2'),
      _entry('1', DateTime(2026, 7, 10, 9, 35), 'Assignment created'),
    ];

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: SizedBox(height: 400, child: NarrativeFeed(entries: entries))),
      ),
    );

    final wreckageY = tester.getTopLeft(find.text('Possible wreckage sighted')).dy;
    final sweepY = tester.getTopLeft(find.text('Beginning search sweep #2')).dy;
    final assignmentY = tester.getTopLeft(find.text('Assignment created')).dy;
    expect(wreckageY, lessThan(sweepY));
    expect(sweepY, lessThan(assignmentY));
  });

  testWidgets('shows an empty state when there are no entries', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: SizedBox(height: 400, child: NarrativeFeed(entries: []))),
      ),
    );
    expect(find.text('No narrative entries yet for this task.'), findsOneWidget);
  });

  testWidgets('scrolls independently of content outside its bounded ancestor', (tester) async {
    final entries = List.generate(
      30,
      (i) => _entry('$i', DateTime(2026, 7, 10, 9, i), 'Entry number $i'),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              const Text('Header stays put'),
              Expanded(child: NarrativeFeed(entries: entries)),
            ],
          ),
        ),
      ),
    );

    final headerPositionBefore = tester.getTopLeft(find.text('Header stays put'));
    await tester.drag(find.byType(NarrativeFeed), const Offset(0, -300));
    await tester.pumpAndSettle();
    final headerPositionAfter = tester.getTopLeft(find.text('Header stays put'));

    expect(headerPositionAfter, headerPositionBefore);
    expect(find.text('Entry number 0'), findsNothing);
  });
}
