import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Persists the logged-in session locally so the app doesn't force a
/// fresh login every time it's relaunched.
class SessionStore {
  SessionStore._();

  static const _incidentIdKey = 'session.incident_id';
  static const _incidentNameKey = 'session.incident_name';
  static const _incidentTypeKey = 'session.incident_type';
  static const _teamIdKey = 'session.team_id';
  static const _teamNameKey = 'session.team_name';
  static const _sessionJsonKey = 'session.session_json';

  static Future<void> save({
    required String incidentId,
    required String incidentName,
    required String teamId,
    required String teamName,
    required Map<String, dynamic> session,
    String? incidentType,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_incidentIdKey, incidentId);
    await prefs.setString(_incidentNameKey, incidentName);
    if (incidentType == null) {
      await prefs.remove(_incidentTypeKey);
    } else {
      await prefs.setString(_incidentTypeKey, incidentType);
    }
    await prefs.setString(_teamIdKey, teamId);
    await prefs.setString(_teamNameKey, teamName);
    await prefs.setString(_sessionJsonKey, jsonEncode(session));
  }

  /// Returns the saved session, or null if none was saved.
  static Future<StoredSession?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final incidentId = prefs.getString(_incidentIdKey);
    final incidentName = prefs.getString(_incidentNameKey);
    final teamId = prefs.getString(_teamIdKey);
    final teamName = prefs.getString(_teamNameKey);
    final sessionJson = prefs.getString(_sessionJsonKey);
    if (incidentId == null ||
        incidentName == null ||
        teamId == null ||
        teamName == null ||
        sessionJson == null) {
      return null;
    }
    return StoredSession(
      incidentId: incidentId,
      incidentName: incidentName,
      incidentType: prefs.getString(_incidentTypeKey),
      teamId: teamId,
      teamName: teamName,
      session: Map<String, dynamic>.from(jsonDecode(sessionJson) as Map),
    );
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_incidentIdKey);
    await prefs.remove(_incidentNameKey);
    await prefs.remove(_incidentTypeKey);
    await prefs.remove(_teamIdKey);
    await prefs.remove(_teamNameKey);
    await prefs.remove(_sessionJsonKey);
  }
}

class StoredSession {
  const StoredSession({
    required this.incidentId,
    required this.incidentName,
    required this.teamId,
    required this.teamName,
    required this.session,
    this.incidentType,
  });

  final String incidentId;
  final String incidentName;
  final String teamId;
  final String teamName;
  final Map<String, dynamic> session;

  /// The incident's free-text type (see `IncidentCategory`), best-effort
  /// fetched at login. Null if the profile fetch failed or hasn't happened
  /// for this saved session yet.
  final String? incidentType;
}
