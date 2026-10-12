import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// The operator's own profile, kept on this device so it can be created and
/// edited with no server connection. It mirrors the identifying fields of the
/// desktop's master personnel record and is shared with an incident server
/// the first time the user loads an incident there (see
/// `IncidentSessionStarter`).
class LocalProfile {
  const LocalProfile({
    required this.personId,
    required this.firstName,
    required this.lastName,
    this.organization = '',
    this.title = '',
    this.phone = '',
    this.email = '',
    this.radioId = '',
  });

  factory LocalProfile.fromJson(Map<String, dynamic> json) {
    String text(String key) => '${json[key] ?? ''}'.trim();
    return LocalProfile(
      personId: text('person_id'),
      firstName: text('first_name'),
      lastName: text('last_name'),
      organization: text('organization'),
      title: text('title'),
      phone: text('phone'),
      email: text('email'),
      radioId: text('radio_id'),
    );
  }

  /// The visible ID (badge / member number) that identifies this person on
  /// the server. Not the server's internal record key.
  final String personId;
  final String firstName;
  final String lastName;
  final String organization;
  final String title;
  final String phone;
  final String email;
  final String radioId;

  String get fullName => '$firstName $lastName'.trim();

  /// True when the fields the server requires are present.
  bool get isComplete =>
      personId.isNotEmpty && firstName.isNotEmpty && lastName.isNotEmpty;

  Map<String, dynamic> toJson() => {
    'person_id': personId,
    'first_name': firstName,
    'last_name': lastName,
    'organization': organization,
    'title': title,
    'phone': phone,
    'email': email,
    'radio_id': radioId,
  };
}

class LocalProfileStore {
  LocalProfileStore._();

  static const _key = 'local_profile.json';

  static Future<LocalProfile?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return null;
    try {
      final profile = LocalProfile.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
      return profile.isComplete ? profile : null;
    } catch (_) {
      return null;
    }
  }

  static Future<void> save(LocalProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(profile.toJson()));
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
