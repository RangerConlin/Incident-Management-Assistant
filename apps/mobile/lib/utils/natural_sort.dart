final _chunkPattern = RegExp(r'\d+|\D+');

/// Compares strings the way people expect for names with embedded numbers
/// (e.g. team names) — "Team 2" before "Team 11" — instead of plain
/// lexicographic order, which sorts digit-by-digit ("Team 1" < "Team 11" <
/// "Team 2").
int naturalCompare(String a, String b) {
  final aChunks = _chunkPattern.allMatches(a).map((m) => m.group(0)!).toList();
  final bChunks = _chunkPattern.allMatches(b).map((m) => m.group(0)!).toList();

  final length = aChunks.length < bChunks.length ? aChunks.length : bChunks.length;
  for (var i = 0; i < length; i++) {
    final aChunk = aChunks[i];
    final bChunk = bChunks[i];
    final aNum = int.tryParse(aChunk);
    final bNum = int.tryParse(bChunk);
    final comparison =
        (aNum != null && bNum != null) ? aNum.compareTo(bNum) : aChunk.compareTo(bChunk);
    if (comparison != 0) return comparison;
  }
  return aChunks.length.compareTo(bChunks.length);
}
