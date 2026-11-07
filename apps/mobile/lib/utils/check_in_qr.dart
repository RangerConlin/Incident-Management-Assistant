import 'dart:convert';

import '../services/local_profile_store.dart';

/// Versioned mobile profile payload for staff check-in scanners.
///
/// URL-safe base64 keeps punctuation that keyboard-wedge scanners commonly
/// mangle out of the scanned text. The decoded JSON uses the canonical
/// personnel field names shared by master and incident personnel records.
class CheckInQr {
  CheckInQr._();

  static const prefix = 'SARAPP:PROFILE:v2:';

  static String payload(LocalProfile profile) {
    final json = jsonEncode(profile.toPersonnelJson());
    final encoded = base64Url.encode(utf8.encode(json)).replaceAll('=', '');
    return '$prefix$encoded';
  }

  static Map<String, dynamic>? decode(String payload) {
    final value = payload.trim();
    if (!value.startsWith(prefix)) return null;
    try {
      final encoded = value.substring(prefix.length);
      final padded = encoded.padRight((encoded.length + 3) ~/ 4 * 4, '=');
      final decoded = jsonDecode(utf8.decode(base64Url.decode(padded)));
      return decoded is Map ? Map<String, dynamic>.from(decoded) : null;
    } catch (_) {
      return null;
    }
  }
}
