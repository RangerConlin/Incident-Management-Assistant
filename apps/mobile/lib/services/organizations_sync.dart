import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/organizations.dart';
import 'sarapp_api_client.dart';

/// Caches the server's organization hierarchy on-device (single JSON blob
/// under one `shared_preferences` key, same pattern as
/// [LocalProfileStore]), so the profile screen's organization picker can use
/// an up-to-date roster without a network round trip on every open, while
/// still falling back to the bundled [Organizations.bundled] mirror if the
/// device has never synced (first run, no connectivity).
class OrganizationsSync {
  OrganizationsSync._();

  static const _key = 'organizations_cache.json';

  /// Fetches the current organization list from the server and caches it.
  /// Safe to call opportunistically whenever the app has a server
  /// connection (e.g. alongside other startup/connectivity checks) — never
  /// throws; a failure just leaves the previous cache (or the bundled
  /// fallback) in place.
  static Future<void> syncFromServer(SarAppApiClient api) async {
    try {
      final rows = await api.fetchMasterOrganizations();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key, jsonEncode(rows));
    } catch (_) {
      // Offline, or server too old to have this endpoint yet — keep
      // whatever is already cached.
    }
  }

  /// The cached server copy of the organization list, or
  /// [Organizations.bundled] if nothing has ever synced successfully.
  static Future<List<OrgEntry>> loadOrganizations() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key);
      if (raw == null) return Organizations.bundled;
      final decoded = jsonDecode(raw);
      if (decoded is! List || decoded.isEmpty) return Organizations.bundled;
      return decoded
          .whereType<Map>()
          .map((row) => OrgEntry.fromJson(Map<String, dynamic>.from(row)))
          .toList();
    } catch (_) {
      return Organizations.bundled;
    }
  }
}
