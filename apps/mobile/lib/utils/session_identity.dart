/// Resolves who the signed-in operator is from a stored login session.
///
/// The server's session response carries the person's login id in `person_id`
/// and their name in `person_fullname`. Both are computed from the linked
/// personnel record on every response; they are display-only and never stored.
class SessionIdentity {
  SessionIdentity._();

  /// The raw login/person id used as the operator's identifier.
  static String personId(Map<String, dynamic> session) {
    for (final key in const ['person_id']) {
      final value = _clean(session[key]);
      if (value != null) return value;
    }
    return '';
  }

  /// The operator's real name, or null when the session doesn't carry one.
  static String? operatorName(Map<String, dynamic> session) =>
      _clean(session['person_fullname']);

  /// Name suitable for showing to users, falling back to the raw id (or
  /// [fallback] when there is no id either) when no name is available.
  static String displayName(
    Map<String, dynamic> session, {
    String fallback = '',
  }) {
    final name = operatorName(session);
    if (name != null) return name;
    final id = personId(session);
    return id.isEmpty ? fallback : id;
  }

  static String? _clean(Object? value) {
    if (value == null) return null;
    final text = '$value'.trim();
    return text.isEmpty ? null : text;
  }
}
