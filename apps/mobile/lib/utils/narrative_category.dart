import '../models/narrative_entry.dart';

/// Presentation-only narrative categories. The backend narrative document
/// has no stored category/entry-type field (only a `critical` flag), so
/// this is a client-side heuristic computed at render time — never
/// persisted, and deliberately simpler than a real taxonomy would be.
enum NarrativeCategory { assignment, safety, update }

extension NarrativeCategoryLabel on NarrativeCategory {
  String get label => switch (this) {
        NarrativeCategory.assignment => 'Assignment',
        NarrativeCategory.safety => 'Safety',
        NarrativeCategory.update => 'Update',
      };
}

/// Categorizes [entry] given the full set of entries for its task: the
/// earliest entry is treated as the originating assignment instruction,
/// `critical` entries are treated as safety/alert items, everything else
/// is a general update.
NarrativeCategory categorizeNarrative(
  NarrativeEntry entry,
  List<NarrativeEntry> allEntriesForTask,
) {
  if (entry.critical) return NarrativeCategory.safety;
  if (allEntriesForTask.isEmpty) return NarrativeCategory.update;
  final earliest = allEntriesForTask.reduce(
    (a, b) => a.timestamp.isBefore(b.timestamp) ? a : b,
  );
  if (earliest.id == entry.id) return NarrativeCategory.assignment;
  return NarrativeCategory.update;
}
