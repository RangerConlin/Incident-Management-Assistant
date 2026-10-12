import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/utils/natural_sort.dart';

void main() {
  group('naturalCompare', () {
    test('sorts embedded numbers numerically, not digit-by-digit', () {
      final names = ['Team 11', 'Team 2', 'Team 1', 'Team 3'];
      names.sort(naturalCompare);
      expect(names, ['Team 1', 'Team 2', 'Team 3', 'Team 11']);
    });

    test('falls back to lexicographic order for names without numbers', () {
      final names = ['GT Charlie', 'GT Alpha', 'GT Bravo'];
      names.sort(naturalCompare);
      expect(names, ['GT Alpha', 'GT Bravo', 'GT Charlie']);
    });

    test('a shorter string sorts before a longer one that starts with it', () {
      expect(naturalCompare('Team 1', 'Team 1A'), lessThan(0));
    });

    test('equal strings compare as equal', () {
      expect(naturalCompare('Team 4', 'Team 4'), 0);
    });

    test('compares by the first differing number, wherever it falls in the string', () {
      // First numeric chunk (31 vs 4) already decides the order, regardless
      // of what comes after or where the numbers sit in each string.
      expect(naturalCompare('31-Alpha 2', '4-Bravo-6'), greaterThan(0));

      final names = ['31-Alpha 2', '4-Bravo-6', '4-Alpha 12', '4-Alpha 3'];
      names.sort(naturalCompare);
      expect(names, ['4-Alpha 3', '4-Alpha 12', '4-Bravo-6', '31-Alpha 2']);
    });
  });
}
