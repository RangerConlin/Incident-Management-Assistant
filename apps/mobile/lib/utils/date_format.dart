/// Formats a timestamp as `MM/DD HH:mm` in local time, hand-rolled to avoid
/// pulling in the `intl` package for one format string.
String formatTimestamp(DateTime? dt) {
  if (dt == null) return '—';
  final local = dt.toLocal();
  final mm = local.month.toString().padLeft(2, '0');
  final dd = local.day.toString().padLeft(2, '0');
  final hh = local.hour.toString().padLeft(2, '0');
  final min = local.minute.toString().padLeft(2, '0');
  return '$mm/$dd $hh:$min';
}

/// Formats a timestamp as just `HH:mm` local time, for compact narrative rows.
String formatTimeOnly(DateTime? dt) {
  if (dt == null) return '—';
  final local = dt.toLocal();
  final hh = local.hour.toString().padLeft(2, '0');
  final min = local.minute.toString().padLeft(2, '0');
  return '$hh:$min';
}

/// Formats how long ago [dt] was ("Just now", "5m ago", "3h ago") for
/// compact list rows, falling back to [formatTimestamp] past a day.
String relativeTime(DateTime dt) {
  final diff = DateTime.now().difference(dt);
  if (diff.inSeconds < 60) return 'Just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  return formatTimestamp(dt);
}
