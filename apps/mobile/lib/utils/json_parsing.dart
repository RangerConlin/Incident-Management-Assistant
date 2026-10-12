/// Small defensive JSON-value coercions shared by the model `fromJson`
/// factories, since the backend returns loosely-typed numeric/date fields.
int? parseInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value');
}

DateTime? parseDateTime(dynamic value) {
  if (value == null) return null;
  final text = '$value'.trim();
  if (text.isEmpty) return null;
  return DateTime.tryParse(text);
}

bool parseIntBool(dynamic value) {
  if (value == null) return false;
  if (value is bool) return value;
  if (value is num) return value != 0;
  final text = '$value'.trim().toLowerCase();
  return text == '1' || text == 'true';
}

String? nullIfBlank(dynamic value) {
  final text = value as String?;
  if (text == null || text.trim().isEmpty) return null;
  return text;
}
